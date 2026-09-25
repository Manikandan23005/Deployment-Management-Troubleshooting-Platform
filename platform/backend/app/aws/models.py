# --- Strongly-Typed AWS Account & EKS Integration Domain Models ---
import re
import uuid
import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict

class AWSAccountStatus(str, Enum):
    NOT_TESTED = "NOT_TESTED"
    VALIDATING = "VALIDATING"
    CONNECTED = "CONNECTED"
    FAILED = "FAILED"
    ACCESS_DENIED = "ACCESS_DENIED"
    ROLE_NOT_FOUND = "ROLE_NOT_FOUND"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    EKS_ACCESS_DENIED = "EKS_ACCESS_DENIED"
    DISABLED = "DISABLED"

ROLE_ARN_REGEX = re.compile(r"^arn:aws:iam::(?P<account_id>\d{12}):role/(?P<role_name>[\w+=,.@\-_/]+)$")

def validate_role_arn_structure(role_arn: str, expected_account_id: Optional[str] = None) -> Dict[str, str]:
    """Validates AWS IAM Role ARN format, service, resource type, and 12-digit account ID."""
    if not role_arn or not isinstance(role_arn, str):
        raise ValueError("Role ARN must be a non-empty string.")
    
    match = ROLE_ARN_REGEX.match(role_arn.strip())
    if not match:
        raise ValueError(f"Invalid IAM Role ARN format: '{role_arn}'. Expected format: 'arn:aws:iam::<12-digit-account-id>:role/<role-name>'.")
    
    arn_account_id = match.group("account_id")
    role_name = match.group("role_name")

    if len(arn_account_id) != 12 or not arn_account_id.isdigit():
        raise ValueError(f"Invalid AWS Account ID in ARN '{arn_account_id}'. Must be exactly 12 numeric digits.")

    if expected_account_id:
        clean_expected = expected_account_id.strip()
        if arn_account_id != clean_expected:
            raise ValueError(f"Role ARN Account ID '{arn_account_id}' does not match registered Account ID '{clean_expected}'. Cross-account role ARN mismatch.")

    return {
        "account_id": arn_account_id,
        "role_name": role_name,
        "role_arn": role_arn.strip()
    }

class AWSAccountRegistrationRequest(BaseModel):
    """Payload for registering a target AWS account with an STS cross-account IAM role ARN."""
    name: str = Field(..., min_length=2, max_length=100, description="Human-readable AWS account display name.")
    account_id: str = Field(..., min_length=12, max_length=12, description="12-digit AWS Account ID.")
    role_arn: str = Field(..., description="Target IAM Role ARN for cross-account STS AssumeRole.")
    default_region: str = Field("ap-south-1", description="Default AWS Region (e.g. ap-south-1, us-east-1, eu-west-1).")
    external_id: Optional[str] = Field(None, description="Optional STS External ID for trust policy enforcement.")

    @field_validator("account_id")
    @classmethod
    def validate_account_id_digits(cls, v: str) -> str:
        v_clean = v.strip()
        if len(v_clean) != 12 or not v_clean.isdigit():
            raise ValueError("AWS Account ID must be exactly 12 numeric digits.")
        return v_clean

    @field_validator("role_arn")
    @classmethod
    def validate_role_arn_field(cls, v: str, values: Any) -> str:
        # Pydantic v2 validation
        return v.strip()

class AWSAccount(BaseModel):
    """Registered AWS Account metadata and connection state. (NEVER persists access/secret keys)."""
    id: str = Field(default_factory=lambda: f"aws-{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Account display name.")
    account_id: str = Field(..., description="12-digit AWS Account ID.")
    role_arn: str = Field(..., description="Target IAM Role ARN.")
    default_region: str = Field("ap-south-1", description="Default AWS Region.")
    external_id: Optional[str] = Field(None, description="Optional STS External ID.")
    status: AWSAccountStatus = Field(AWSAccountStatus.NOT_TESTED, description="Current connection validation status.")
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    last_validated_at: Optional[str] = Field(None, description="Timestamp of last successful STS validation.")
    last_error: Optional[str] = Field(None, description="Safe error message if validation failed.")
    caller_identity: Optional[Dict[str, Any]] = Field(None, description="Safe STS caller identity snapshot.")

    model_config = ConfigDict(arbitrary_types_allowed=True)

class EKSClusterStatus(str, Enum):
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    DELETING = "DELETING"
    FAILED = "FAILED"
    UPDATING = "UPDATING"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"

class EKSCluster(BaseModel):
    """Discovered Amazon EKS cluster metadata."""
    name: str = Field(..., description="EKS cluster name.")
    arn: str = Field(..., description="EKS cluster ARN.")
    status: EKSClusterStatus = Field(EKSClusterStatus.ACTIVE, description="EKS cluster status.")
    version: str = Field(..., description="Kubernetes version (e.g. '1.29', '1.30').")
    endpoint: str = Field(..., description="Kubernetes API server HTTPS endpoint URL.")
    region: str = Field(..., description="AWS region where the cluster is located.")
    account_id: str = Field(..., description="Parent AWS Account ID.")
    certificate_authority_data: Optional[str] = Field(None, description="Base64-encoded cluster CA certificate.")
    certificate_authority_available: bool = Field(True, description="Whether CA data is present.")
    platform_version: Optional[str] = Field(None, description="EKS platform version (e.g. 'eks.7').")
    role_arn: Optional[str] = Field(None, description="EKS cluster IAM service role ARN.")
    created_at: Optional[str] = Field(None, description="Cluster creation timestamp.")

class AWSConnectionTestResult(BaseModel):
    """Safe connection and caller identity result returned to users without credentials."""
    account_id: str = Field(..., description="Verified AWS Account ID.")
    assumed_role_arn: str = Field(..., description="Assumed IAM Role ARN.")
    user_id: str = Field(..., description="Assumed STS User/Session ID.")
    region: str = Field(..., description="AWS Region tested.")
    status: AWSAccountStatus = Field(..., description="Connection status outcome.")
    message: str = Field(..., description="Human-readable connection summary.")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
