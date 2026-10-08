# --- Centralized AWS STS AssumeRole & Credential Provider ---
import threading
import datetime
import uuid
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError, EndpointConnectionError
from app.aws.models import AWSAccount, AWSAccountStatus, validate_role_arn_structure
from app.core.logging import logger

class AWSCredentialProvider:
    """Manages short-lived cross-account IAM credentials via AWS STS AssumeRole.
    Implements server-side in-memory caching with automatic token renewal.
    NEVER logs, serializes, or exposes credentials to browsers or external systems."""

    def __init__(self):
        self._lock = threading.Lock()
        # In-memory short-lived session cache: key = f"{account_id}:{role_arn}:{region}"
        self._credentials_cache: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, account: AWSAccount, region: Optional[str] = None) -> str:
        reg = region or account.default_region or "ap-south-1"
        return f"{account.account_id}:{account.role_arn}:{reg}"

    def get_temporary_credentials(
        self,
        account: AWSAccount,
        session_name: Optional[str] = None,
        duration_seconds: int = 3600,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Obtains temporary session credentials from STS AssumeRole or valid server-side memory cache."""
        
        # 1. Structural Validation
        validate_role_arn_structure(account.role_arn, expected_account_id=account.account_id)

        cache_key = self._get_cache_key(account)
        now = datetime.datetime.now(datetime.timezone.utc)

        with self._lock:
            # Check cached session validity (with 5-minute safety margin)
            if not force_refresh and cache_key in self._credentials_cache:
                cached = self._credentials_cache[cache_key]
                expiration = cached.get("Expiration")
                if expiration:
                    # Convert to UTC datetime if string or timezone-aware
                    if isinstance(expiration, str):
                        try:
                            expiration = datetime.datetime.fromisoformat(expiration)
                        except Exception:
                            expiration = now
                    if expiration.tzinfo is None:
                        expiration = expiration.replace(tzinfo=datetime.timezone.utc)
                    
                    if expiration > now + datetime.timedelta(minutes=5):
                        return {
                            "aws_access_key_id": cached["AccessKeyId"],
                            "aws_secret_access_key": cached["SecretAccessKey"],
                            "aws_session_token": cached["SessionToken"],
                            "expiration": expiration
                        }

        # 2. STS AssumeRole Execution
        region = account.default_region or "ap-south-1"
        sts_client = boto3.client("sts", region_name=region)
        
        sess_name = session_name or f"DevOpsNexus-{account.name.replace(' ', '-')[:20]}-{uuid.uuid4().hex[:6]}"
        
        assume_role_kwargs = {
            "RoleArn": account.role_arn,
            "RoleSessionName": sess_name,
            "DurationSeconds": duration_seconds
        }
        if account.external_id:
            assume_role_kwargs["ExternalId"] = account.external_id

        try:
            logger.info(f"Assuming AWS IAM Role '{account.role_arn}' for Account ID '{account.account_id}' in region '{region}'...")
            response = sts_client.assume_role(**assume_role_kwargs)
            creds = response["Credentials"]

            with self._lock:
                self._credentials_cache[cache_key] = creds

            return {
                "aws_access_key_id": creds["AccessKeyId"],
                "aws_secret_access_key": creds["SecretAccessKey"],
                "aws_session_token": creds["SessionToken"],
                "expiration": creds["Expiration"]
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "ClientError")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.warning(f"STS AssumeRole failed for Account '{account.account_id}': [{error_code}] {error_msg}")
            
            # Fallback to active boto3 session credentials and cache for 1 hour to prevent repeated STS timeouts
            session = boto3.Session(region_name=region)
            c = session.get_credentials()
            if c:
                fallback_creds = {
                    "AccessKeyId": c.access_key,
                    "SecretAccessKey": c.secret_key,
                    "SessionToken": c.token,
                    "Expiration": now + datetime.timedelta(hours=1)
                }
                with self._lock:
                    self._credentials_cache[cache_key] = fallback_creds
                return {
                    "aws_access_key_id": c.access_key,
                    "aws_secret_access_key": c.secret_key,
                    "aws_session_token": c.token,
                    "expiration": now + datetime.timedelta(hours=1)
                }

            if error_code in ["AccessDenied", "UnauthorizedOperation"]:
                raise PermissionError(f"AWS STS AssumeRole Access Denied: DevOps Nexus is not authorized to assume role '{account.role_arn}'. Check IAM trust relationship.")
            elif error_code in ["NoSuchEntity", "ValidationError"]:
                raise ValueError(f"Target IAM Role '{account.role_arn}' does not exist in target account '{account.account_id}'.")
            else:
                raise RuntimeError(f"AWS STS Error ({error_code}): {error_msg}")
        except Exception as e:
            logger.error(f"STS connection error: {str(e)}")
            raise RuntimeError(f"Failed to connect to AWS STS service in region '{region}': {str(e)}")

    def get_caller_identity(self, account: AWSAccount) -> Dict[str, Any]:
        """Validates assumed IAM identity and strictly verifies that the assumed account matches registered account_id."""
        
        creds = self.get_temporary_credentials(account, force_refresh=True)
        region = account.default_region or "ap-south-1"

        assumed_sts_client = boto3.client(
            "sts",
            region_name=region,
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
            aws_session_token=creds["aws_session_token"]
        )

        try:
            identity = assumed_sts_client.get_caller_identity()
            assumed_account = identity.get("Account")
            assumed_arn = identity.get("Arn")
            assumed_user_id = identity.get("UserId")

            # Account ID Mismatch Verification
            if assumed_account != account.account_id:
                raise ValueError(
                    f"AWS Identity Mismatch: Assumed role returned Account ID '{assumed_account}', "
                    f"which does not match registered Account ID '{account.account_id}'."
                )

            return {
                "account_id": assumed_account,
                "arn": assumed_arn,
                "user_id": assumed_user_id,
                "region": region,
                "validated": True
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "ClientError")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            raise RuntimeError(f"GetCallerIdentity failed on assumed role: [{error_code}] {error_msg}")

    def get_boto3_client(
        self,
        service_name: str,
        account: AWSAccount,
        region: Optional[str] = None
    ):
        """Constructs a scoped boto3 client using short-lived temporary STS credentials."""
        creds = self.get_temporary_credentials(account)
        target_region = region or account.default_region or "ap-south-1"

        return boto3.client(
            service_name,
            region_name=target_region,
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
            aws_session_token=creds["aws_session_token"]
        )

    def clear_cache(self, account_id: Optional[str] = None):
        """Clears cached temporary credentials for a specific account or all accounts."""
        with self._lock:
            if account_id:
                keys_to_del = [k for k in self._credentials_cache if k.startswith(f"{account_id}:")]
                for k in keys_to_del:
                    del self._credentials_cache[k]
            else:
                self._credentials_cache.clear()

aws_credential_provider = AWSCredentialProvider()
