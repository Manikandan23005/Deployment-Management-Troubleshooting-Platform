# --- Phase 5 AWS Account Registration & Amazon EKS Integration Tests ---
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import datetime
from botocore.exceptions import ClientError

from app.main import app
from app.aws.models import (
    AWSAccount, 
    AWSAccountStatus, 
    AWSAccountRegistrationRequest, 
    validate_role_arn_structure,
    EKSCluster,
    EKSClusterStatus
)
from app.aws.credential_provider import aws_credential_provider
from app.aws.eks_service import eks_discovery_service
from app.aws.account_registry import aws_account_registry
from app.clients.k8s_factory import k8s_client_factory
from app.agent.target_resolver import target_resolver
from app.agent.models import ScopeContext
from app.agent.agent_runtime import agent_runtime
from app.agent.tools import tool_registry

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_aws_registry():
    aws_account_registry._accounts.clear()
    aws_credential_provider.clear_cache()
    yield
    aws_account_registry._accounts.clear()
    aws_credential_provider.clear_cache()


# =========================================================================
# PART A: IAM Role ARN Validation Tests
# =========================================================================

def test_validate_role_arn_valid():
    arn = "arn:aws:iam::123456789012:role/DevOpsNexusAccessRole"
    res = validate_role_arn_structure(arn, expected_account_id="123456789012")
    assert res["account_id"] == "123456789012"
    assert res["role_name"] == "DevOpsNexusAccessRole"

def test_validate_role_arn_with_path():
    arn = "arn:aws:iam::987654321098:role/service-roles/DevOpsNexusCrossAccountRole"
    res = validate_role_arn_structure(arn, expected_account_id="987654321098")
    assert res["account_id"] == "987654321098"
    assert "DevOpsNexusCrossAccountRole" in res["role_name"]

def test_validate_role_arn_invalid_format():
    with pytest.raises(ValueError, match="Invalid IAM Role ARN format"):
        validate_role_arn_structure("not-an-arn")

def test_validate_role_arn_wrong_service():
    with pytest.raises(ValueError, match="Invalid IAM Role ARN format"):
        validate_role_arn_structure("arn:aws:s3:::my-bucket-name")

def test_validate_role_arn_wrong_resource_type():
    with pytest.raises(ValueError, match="Invalid IAM Role ARN format"):
        validate_role_arn_structure("arn:aws:iam::123456789012:user/admin")

def test_validate_role_arn_mismatched_account():
    arn = "arn:aws:iam::111122223333:role/DevOpsNexusRole"
    with pytest.raises(ValueError, match="Cross-account role ARN mismatch"):
        validate_role_arn_structure(arn, expected_account_id="999988887777")


# =========================================================================
# PART B: AWS Account Registration & Management Tests
# =========================================================================

def test_register_aws_account_success():
    req = AWSAccountRegistrationRequest(
        name="Production AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole",
        default_region="ap-south-1"
    )
    acc = aws_account_registry.register_account(req)
    assert acc.id.startswith("aws-")
    assert acc.name == "Production AWS"
    assert acc.account_id == "123456789012"
    assert acc.status == AWSAccountStatus.NOT_TESTED

def test_register_aws_account_duplicate_updates_existing():
    req1 = AWSAccountRegistrationRequest(
        name="Staging AWS",
        account_id="555566667777",
        role_arn="arn:aws:iam::555566667777:role/DevOpsNexusStageRole",
        default_region="us-east-1"
    )
    acc1 = aws_account_registry.register_account(req1)

    req2 = AWSAccountRegistrationRequest(
        name="Staging AWS Renamed",
        account_id="555566667777",
        role_arn="arn:aws:iam::555566667777:role/DevOpsNexusStageRole",
        default_region="us-east-2"
    )
    acc2 = aws_account_registry.register_account(req2)
    assert acc2.name == "Staging AWS Renamed"
    assert acc2.default_region == "us-east-2"
    assert len(aws_account_registry.list_accounts()) == 1

def test_delete_aws_account():
    req = AWSAccountRegistrationRequest(
        name="Temp AWS",
        account_id="111122223333",
        role_arn="arn:aws:iam::111122223333:role/TempRole"
    )
    acc = aws_account_registry.register_account(req)
    assert aws_account_registry.get_account("111122223333") is not None
    
    deleted = aws_account_registry.delete_account(acc.id)
    assert deleted is True
    assert aws_account_registry.get_account("111122223333") is None


# =========================================================================
# PART C: STS AssumeRole & Connection Testing Tests
# =========================================================================

def test_sts_assume_role_and_cache():
    account = AWSAccount(
        name="Prod AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole",
        default_region="ap-south-1"
    )

    mock_sts_response = {
        "Credentials": {
            "AccessKeyId": "ASIA_MOCK_KEY_123",
            "SecretAccessKey": "mock_secret_abc",
            "SessionToken": "mock_session_token_xyz",
            "Expiration": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }
    }

    with patch("boto3.client") as mock_boto:
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = mock_sts_response
        mock_boto.return_value = mock_sts

        creds = aws_credential_provider.get_temporary_credentials(account)
        assert creds["aws_access_key_id"] == "ASIA_MOCK_KEY_123"
        assert mock_sts.assume_role.call_count == 1

        # Second call should hit in-memory cache without calling assume_role again
        cached_creds = aws_credential_provider.get_temporary_credentials(account)
        assert cached_creds["aws_access_key_id"] == "ASIA_MOCK_KEY_123"
        assert mock_sts.assume_role.call_count == 1

def test_test_connection_success():
    req = AWSAccountRegistrationRequest(
        name="Prod AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole"
    )
    acc = aws_account_registry.register_account(req)

    mock_sts_response = {
        "Credentials": {
            "AccessKeyId": "ASIA_MOCK_1",
            "SecretAccessKey": "mock_sec",
            "SessionToken": "mock_tok",
            "Expiration": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }
    }
    mock_identity = {
        "Account": "123456789012",
        "Arn": "arn:aws:sts::123456789012:assumed-role/DevOpsNexusAccessRole/session",
        "UserId": "AROA123:session"
    }

    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_client.assume_role.return_value = mock_sts_response
        mock_client.get_caller_identity.return_value = mock_identity
        mock_boto.return_value = mock_client

        res = aws_account_registry.test_connection(acc.id)
        assert res.status == AWSAccountStatus.CONNECTED
        assert res.account_id == "123456789012"
        assert "DevOpsNexusAccessRole" in res.assumed_role_arn

def test_test_connection_account_mismatch():
    req = AWSAccountRegistrationRequest(
        name="Spoofed Account",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/Role"
    )
    acc = aws_account_registry.register_account(req)

    mock_sts_response = {
        "Credentials": {
            "AccessKeyId": "ASIA_MOCK",
            "SecretAccessKey": "sec",
            "SessionToken": "tok",
            "Expiration": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }
    }
    # Assumed role returned different Account ID (e.g. 999999999999)
    mock_identity = {
        "Account": "999999999999",
        "Arn": "arn:aws:sts::999999999999:assumed-role/Role/session",
        "UserId": "AROA999:session"
    }

    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_client.assume_role.return_value = mock_sts_response
        mock_client.get_caller_identity.return_value = mock_identity
        mock_boto.return_value = mock_client

        with pytest.raises(ValueError, match="AWS Identity Mismatch"):
            aws_account_registry.test_connection(acc.id)
        
        assert acc.status == AWSAccountStatus.ACCOUNT_MISMATCH


# =========================================================================
# PART D: EKS Cluster Discovery Tests
# =========================================================================

def test_eks_discovery_list_and_describe():
    account = AWSAccount(
        name="Prod AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole",
        default_region="ap-south-1"
    )

    mock_describe = {
        "cluster": {
            "name": "production-eks",
            "arn": "arn:aws:eks:ap-south-1:123456789012:cluster/production-eks",
            "status": "ACTIVE",
            "version": "1.29",
            "endpoint": "https://production-eks.ap-south-1.eks.amazonaws.com",
            "certificateAuthority": {"data": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCg=="},
            "platformVersion": "eks.7"
        }
    }

    with patch.object(aws_credential_provider, "get_boto3_client") as mock_boto:
        mock_eks = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"clusters": ["production-eks"]}]
        mock_eks.get_paginator.return_value = mock_paginator
        mock_eks.describe_cluster.return_value = mock_describe
        mock_boto.return_value = mock_eks

        clusters = eks_discovery_service.discover_all_clusters(account)
        assert len(clusters) == 1
        assert clusters[0].name == "production-eks"
        assert clusters[0].status == EKSClusterStatus.ACTIVE
        assert clusters[0].version == "1.29"
        assert clusters[0].certificate_authority_available is True

def test_register_eks_cluster_target():
    req = AWSAccountRegistrationRequest(
        name="Prod AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole"
    )
    acc = aws_account_registry.register_account(req)

    mock_describe = {
        "cluster": {
            "name": "staging-eks",
            "arn": "arn:aws:eks:ap-south-1:123456789012:cluster/staging-eks",
            "status": "ACTIVE",
            "version": "1.29",
            "endpoint": "https://staging-eks.ap-south-1.eks.amazonaws.com",
            "certificateAuthority": {"data": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCg=="}
        }
    }

    with patch.object(aws_credential_provider, "get_boto3_client") as mock_boto:
        mock_eks = MagicMock()
        mock_eks.describe_cluster.return_value = mock_describe
        mock_boto.return_value = mock_eks

        reg_target = aws_account_registry.register_eks_cluster_as_target(acc.id, "staging-eks")
        assert reg_target["name"] == "eks-staging-eks"
        assert reg_target["provider"] == "EKS"
        assert reg_target["authentication_type"] == "AWS_IAM_EKS"


# =========================================================================
# PART E: Environment-Aware Kubernetes Client Factory Tests
# =========================================================================

def test_k8s_factory_onprem_routing():
    # Local minikube target
    clients = k8s_client_factory.get_clients("cluster-minikube-local")
    assert "v1" in clients
    assert "apps_v1" in clients
    assert clients["cluster"]["provider"] == "Minikube"

def test_k8s_factory_eks_token_generation():
    account = AWSAccount(
        name="Prod AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole"
    )
    with patch.object(aws_credential_provider, "get_temporary_credentials") as mock_creds:
        mock_creds.return_value = {
            "aws_access_key_id": "ASIA_TEST",
            "aws_secret_access_key": "test_sec",
            "aws_session_token": "test_tok"
        }
        token = k8s_client_factory.generate_eks_token("production-eks", account)
        assert token.startswith("k8s-aws-v1.")


# =========================================================================
# PART F: ScopeContext & TargetResolver Tests
# =========================================================================

def test_scope_context_aws_eks():
    scope = ScopeContext(
        environment="AWS_EKS",
        aws_account_id="123456789012",
        aws_account_name="Production AWS",
        region="ap-south-1",
        cluster="production-eks",
        cluster_id="eks-production-eks",
        namespace="devops-nexus-prod",
        application="gateway"
    )
    assert scope.environment == "AWS_EKS"
    assert scope.aws_account_id == "123456789012"
    assert scope.region == "ap-south-1"

def test_target_resolver_resolves_eks():
    req = AWSAccountRegistrationRequest(
        name="Production AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole"
    )
    aws_account_registry.register_account(req)

    resolved = target_resolver.resolve_target("Why is gateway pod failing in production EKS?")
    assert resolved["environment_type"] == "AWS_EKS"
    assert resolved["application"] == "gateway"
    assert resolved["aws_account_id"] == "123456789012"


# =========================================================================
# PART G: ToolRegistry & Agent Integration on EKS
# =========================================================================

def test_tool_registry_executes_on_eks():
    mock_pod = MagicMock()
    mock_pod.metadata.name = "gateway-deployment-7f8d"
    mock_pod.status.phase = "Running"
    mock_pod.status.pod_ip = "10.0.12.34"
    mock_pod.spec.node_name = "ip-10-0-12-100.ec2.internal"
    mock_pod.status.container_statuses = []

    with patch.object(k8s_client_factory, "get_clients") as mock_factory:
        mock_v1 = MagicMock()
        mock_v1.read_namespaced_pod.return_value = mock_pod
        mock_factory.return_value = {
            "v1": mock_v1,
            "apps_v1": MagicMock(),
            "networking_v1": MagicMock(),
            "cluster": {"id": "eks-production-eks", "provider": "EKS"}
        }

        res = tool_registry.execute(
            tool_name="k8s.get_pod",
            input_data={"name": "gateway-deployment-7f8d", "namespace": "devops-nexus-prod", "cluster_id": "eks-production-eks"},
            user_info={"username": "devops-lead", "role": "admin"}
        )
        assert res.success is True
        assert res.data["name"] == "gateway-deployment-7f8d"
        assert res.data["status"] == "Running"


# =========================================================================
# PART H: Credential Security Invariants
# =========================================================================

def test_credentials_never_exposed_in_api_response():
    req = AWSAccountRegistrationRequest(
        name="Prod AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole"
    )
    acc = aws_account_registry.register_account(req)

    res = client.get(f"/api/v1/aws/accounts/{acc.id}")
    assert res.status_code == 200
    data_str = str(res.json())
    
    # Invariant checks: secrets never leaked
    assert "SecretAccessKey" not in data_str
    assert "SessionToken" not in data_str
    assert "aws_secret_access_key" not in data_str
    assert "aws_session_token" not in data_str


# =========================================================================
# PART I: REST Endpoints Integration Tests
# =========================================================================

def test_api_register_and_list_aws_accounts():
    post_res = client.post(
        "/api/v1/aws/accounts",
        json={
            "name": "Integration AWS",
            "account_id": "999988887777",
            "role_arn": "arn:aws:iam::999988887777:role/IntegrationRole",
            "default_region": "eu-central-1"
        }
    )
    assert post_res.status_code == 200
    assert post_res.json()["data"]["name"] == "Integration AWS"

    list_res = client.get("/api/v1/aws/accounts")
    assert list_res.status_code == 200
    assert len(list_res.json()["data"]) >= 1

def test_api_test_connection_endpoint():
    req = AWSAccountRegistrationRequest(
        name="Test AWS",
        account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/DevOpsNexusRole"
    )
    acc = aws_account_registry.register_account(req)

    with patch.object(aws_credential_provider, "get_caller_identity") as mock_identity:
        mock_identity.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:sts::123456789012:assumed-role/DevOpsNexusRole/session",
            "user_id": "AROA:session",
            "region": "ap-south-1",
            "validated": True
        }

        res = client.post(f"/api/v1/aws/accounts/{acc.id}/test")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["status"] == "CONNECTED"
        assert data["account_id"] == "123456789012"
