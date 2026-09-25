# --- Amazon EKS Discovery & Cluster Metadata Service ---
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
from app.aws.models import AWSAccount, EKSCluster, EKSClusterStatus
from app.aws.credential_provider import aws_credential_provider
from app.core.logging import logger

class EKSDiscoveryService:
    """Discovers and inspects Amazon EKS clusters across AWS regions using assumed STS role credentials."""

    def list_clusters(self, account: AWSAccount, region: Optional[str] = None) -> List[str]:
        """Lists Amazon EKS cluster names within the target AWS account and region."""
        target_region = region or account.default_region or "ap-south-1"
        try:
            eks = aws_credential_provider.get_boto3_client("eks", account, region=target_region)
            paginator = eks.get_paginator("list_clusters")
            cluster_names = []
            for page in paginator.paginate():
                cluster_names.extend(page.get("clusters", []))
            return cluster_names
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "ClientError")
            msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"EKS list_clusters failed for account '{account.account_id}' in '{target_region}': [{code}] {msg}")
            if code == "AccessDeniedException":
                raise PermissionError(f"EKS Access Denied: Assumed role '{account.role_arn}' lacks 'eks:ListClusters' permission in region '{target_region}'.")
            raise RuntimeError(f"EKS Error ({code}): {msg}")

    def describe_cluster(
        self,
        account: AWSAccount,
        cluster_name: str,
        region: Optional[str] = None
    ) -> EKSCluster:
        """Retrieves configuration, endpoint, Kubernetes version, and certificate authority data for an EKS cluster."""
        target_region = region or account.default_region or "ap-south-1"
        try:
            eks = aws_credential_provider.get_boto3_client("eks", account, region=target_region)
            res = eks.describe_cluster(name=cluster_name)
            raw = res.get("cluster", {})

            status_str = raw.get("status", "ACTIVE")
            try:
                status_enum = EKSClusterStatus(status_str)
            except ValueError:
                status_enum = EKSClusterStatus.UNKNOWN

            ca_data = raw.get("certificateAuthority", {}).get("data")
            created_at_val = raw.get("createdAt")
            created_at_str = created_at_val.isoformat() if hasattr(created_at_val, "isoformat") else str(created_at_val) if created_at_val else None

            return EKSCluster(
                name=raw.get("name", cluster_name),
                arn=raw.get("arn", f"arn:aws:eks:{target_region}:{account.account_id}:cluster/{cluster_name}"),
                status=status_enum,
                version=raw.get("version", "1.29"),
                endpoint=raw.get("endpoint", f"https://{cluster_name}.{target_region}.eks.amazonaws.com"),
                region=target_region,
                account_id=account.account_id,
                certificate_authority_data=ca_data,
                certificate_authority_available=bool(ca_data),
                platform_version=raw.get("platformVersion"),
                role_arn=raw.get("roleArn"),
                created_at=created_at_str
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "ClientError")
            msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"EKS describe_cluster failed for '{cluster_name}': [{code}] {msg}")
            if code == "ResourceNotFoundException":
                raise ValueError(f"EKS Cluster '{cluster_name}' not found in account '{account.account_id}' ({target_region}).")
            elif code == "AccessDeniedException":
                raise PermissionError(f"EKS Access Denied: Assumed role lacks 'eks:DescribeCluster' permission for '{cluster_name}'.")
            raise RuntimeError(f"EKS describe_cluster error ({code}): {msg}")

    def discover_all_clusters(
        self,
        account: AWSAccount,
        region: Optional[str] = None
    ) -> List[EKSCluster]:
        """Discovers and describes all Amazon EKS clusters in target region."""
        target_region = region or account.default_region or "ap-south-1"
        cluster_names = self.list_clusters(account, region=target_region)
        results: List[EKSCluster] = []
        for cname in cluster_names:
            try:
                cluster_obj = self.describe_cluster(account, cname, region=target_region)
                results.append(cluster_obj)
            except Exception as e:
                logger.warning(f"Could not describe EKS cluster '{cname}': {str(e)}")
        return results

eks_discovery_service = EKSDiscoveryService()
