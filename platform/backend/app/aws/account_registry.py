# --- AWS Account Registration & Cluster Target Service ---
import threading
import datetime
from typing import Dict, List, Optional, Any
from app.aws.models import (
    AWSAccount, 
    AWSAccountStatus, 
    AWSAccountRegistrationRequest, 
    AWSConnectionTestResult, 
    EKSCluster,
    validate_role_arn_structure
)
from app.aws.credential_provider import aws_credential_provider
from app.aws.eks_service import eks_discovery_service
from app.services.cluster_registry import cluster_registry, ClusterProvider, ClusterEnvironment, ClusterStatus
from app.services.audit_service import audit_service
from app.core.logging import logger

class AWSAccountRegistryService:
    """Manages AWS Account registrations, cross-account STS connection testing, and EKS cluster target resolution."""

    def __init__(self):
        self._lock = threading.Lock()
        self._accounts: Dict[str, AWSAccount] = {}
        self._seed_default_accounts()

    def _seed_default_accounts(self):
        """Initializes default reference accounts if configured in environment or settings."""
        try:
            from app.core.settings import settings
            default_acc_id = getattr(settings, "DEFAULT_AWS_ACCOUNT_ID", "605294565283")
            default_role_arn = getattr(settings, "DEFAULT_AWS_ROLE_ARN", "arn:aws:iam::605294565283:role/DevOpsNexusAccessRole")
            default_region = getattr(settings, "DEFAULT_AWS_REGION", "ap-south-1")

            if default_acc_id and default_role_arn:
                account = AWSAccount(
                    id=f"aws-prod-{default_acc_id}",
                    name="Production AWS",
                    account_id=default_acc_id,
                    role_arn=default_role_arn,
                    default_region=default_region,
                    status=AWSAccountStatus.CONNECTED
                )
                self._accounts[account.id] = account
                self._accounts[account.account_id] = account
        except Exception as e:
            logger.debug(f"Default AWS account seeding note: {str(e)}")

    def register_account(self, request: AWSAccountRegistrationRequest, username: str = "admin") -> AWSAccount:
        """Registers a new AWS account with role ARN validation."""
        
        # 1. Structural and Account ID Validation
        validate_role_arn_structure(request.role_arn, expected_account_id=request.account_id)

        with self._lock:
            # Check duplicate account ID
            for acc in self._accounts.values():
                if acc.account_id == request.account_id:
                    # Update existing account definition
                    acc.name = request.name
                    acc.role_arn = request.role_arn
                    acc.default_region = request.default_region
                    acc.external_id = request.external_id
                    acc.status = AWSAccountStatus.NOT_TESTED
                    acc.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    return acc

            account = AWSAccount(
                name=request.name,
                account_id=request.account_id,
                role_arn=request.role_arn,
                default_region=request.default_region,
                external_id=request.external_id,
                status=AWSAccountStatus.NOT_TESTED
            )
            self._accounts[account.id] = account
            self._accounts[account.account_id] = account

        try:
            audit_service.log_action(
                username=username,
                action="AWS_ACCOUNT_REGISTERED",
                details={
                    "account_name": account.name,
                    "account_id": account.account_id,
                    "role_arn": account.role_arn,
                    "region": account.default_region
                }
            )
        except Exception as e:
            logger.debug(f"Audit log write failed: {str(e)}")

        return account

    def list_accounts(self) -> List[AWSAccount]:
        """Lists unique registered AWS accounts."""
        with self._lock:
            # Deduplicate (indexed by both id and account_id)
            seen_ids = set()
            unique_accs = []
            for acc in self._accounts.values():
                if acc.id not in seen_ids:
                    seen_ids.add(acc.id)
                    unique_accs.append(acc)
            return unique_accs

    def get_account(self, account_identifier: str) -> Optional[AWSAccount]:
        """Fetches an AWS account by registration ID or 12-digit AWS Account ID."""
        with self._lock:
            return self._accounts.get(account_identifier)

    def delete_account(self, account_identifier: str, username: str = "admin") -> bool:
        """Deletes an AWS account registration and clears cached credentials."""
        with self._lock:
            acc = self._accounts.get(account_identifier)
            if not acc:
                return False
            
            acc_id = acc.id
            aws_acc_num = acc.account_id

            if acc_id in self._accounts:
                del self._accounts[acc_id]
            if aws_acc_num in self._accounts:
                del self._accounts[aws_acc_num]

        aws_credential_provider.clear_cache(aws_acc_num)

        try:
            audit_service.log_action(
                username=username,
                action="AWS_ACCOUNT_DELETED",
                details={"account_id": aws_acc_num, "registration_id": acc_id}
            )
        except Exception:
            pass

        return True

    def test_connection(self, account_identifier: str, username: str = "admin") -> AWSConnectionTestResult:
        """Tests STS AssumeRole and validates assumed identity against registered account ID."""
        account = self.get_account(account_identifier)
        if not account:
            raise ValueError(f"AWS Account '{account_identifier}' not found in registry.")

        account.status = AWSAccountStatus.VALIDATING
        try:
            caller_identity = aws_credential_provider.get_caller_identity(account)
            
            account.status = AWSAccountStatus.CONNECTED
            account.last_validated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            account.last_error = None
            account.caller_identity = caller_identity

            result = AWSConnectionTestResult(
                account_id=caller_identity["account_id"],
                assumed_role_arn=caller_identity["arn"],
                user_id=caller_identity["user_id"],
                region=caller_identity["region"],
                status=AWSAccountStatus.CONNECTED,
                message=f"Successfully assumed role '{account.role_arn}'. Verified Account ID '{caller_identity['account_id']}'."
            )

            try:
                audit_service.log_action(
                    username=username,
                    action="AWS_CONNECTION_TEST_SUCCESS",
                    details={"account_id": account.account_id, "role_arn": account.role_arn}
                )
            except Exception:
                pass

            return result

        except PermissionError as pe:
            account.status = AWSAccountStatus.ACCESS_DENIED
            account.last_error = str(pe)
            raise pe
        except ValueError as ve:
            if "Mismatch" in str(ve):
                account.status = AWSAccountStatus.ACCOUNT_MISMATCH
            else:
                account.status = AWSAccountStatus.ROLE_NOT_FOUND
            account.last_error = str(ve)
            raise ve
        except Exception as e:
            account.status = AWSAccountStatus.FAILED
            account.last_error = str(e)
            raise e

    def discover_clusters(self, account_identifier: str, region: Optional[str] = None) -> List[EKSCluster]:
        """Discovers all Amazon EKS clusters available in the target account."""
        account = self.get_account(account_identifier)
        if not account:
            raise ValueError(f"AWS Account '{account_identifier}' not found in registry.")
        
        return eks_discovery_service.discover_all_clusters(account, region=region)

    def register_eks_cluster_as_target(
        self,
        account_identifier: str,
        cluster_name: str,
        region: Optional[str] = None,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Registers a discovered Amazon EKS cluster into the central ClusterRegistry as an active execution target."""
        account = self.get_account(account_identifier)
        if not account:
            raise ValueError(f"AWS Account '{account_identifier}' not found.")

        target_region = region or account.default_region or "ap-south-1"
        eks_cluster = eks_discovery_service.describe_cluster(account, cluster_name, region=target_region)

        # Check if already registered in cluster_registry
        existing_clusters = cluster_registry.list_clusters()
        for ec in existing_clusters:
            if ec.get("name") == f"eks-{cluster_name}" or (ec.get("api_server") == eks_cluster.endpoint and ec.get("provider") == ClusterProvider.EKS.value):
                return ec

        auto_default = is_default or (len(existing_clusters) == 0)

        cluster_data = {
            "name": f"eks-{cluster_name}",
            "description": f"Amazon EKS Cluster '{cluster_name}' in AWS Account {account.account_id} ({target_region})",
            "environment": ClusterEnvironment.PRODUCTION.value,
            "provider": ClusterProvider.EKS.value,
            "context_name": f"arn:aws:eks:{target_region}:{account.account_id}:cluster/{cluster_name}",
            "api_server": eks_cluster.endpoint,
            "authentication_type": "AWS_IAM_EKS",
            "default_namespace": "devops-nexus-prod",
            "is_default": auto_default,
            "status": ClusterStatus.CONNECTED.value,
            "aws_account_id": account.account_id,
            "aws_account_name": account.name,
            "aws_region": target_region,
            "eks_cluster_name": cluster_name,
            "ca_data": eks_cluster.certificate_authority_data
        }

        registered = cluster_registry.add_cluster(cluster_data)
        return registered

aws_account_registry = AWSAccountRegistryService()
