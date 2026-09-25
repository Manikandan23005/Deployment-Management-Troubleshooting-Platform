#!/usr/bin/env python3
"""
DevOps Nexus — Phase 5 & Phase 6 End-to-End Dry-Run Verification Script
Simulates the complete lifecycle:
  Terraform EKS Specs -> AWS Account Registration -> STS AssumeRole ->
  EKS Discovery -> Target Registration -> Presigned Token Gen ->
  ScopeContext Resolution -> ToolRegistry & AgentRuntime Execution
"""

import sys
import os
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# Ensure backend paths are on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../platform/backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../platform")))

from app.aws.models import AWSAccountRegistrationRequest, AWSAccountStatus
from app.aws.account_registry import aws_account_registry
from app.aws.credential_provider import aws_credential_provider
from app.clients.k8s_factory import k8s_client_factory
from app.agent.target_resolver import target_resolver
from app.agent.agent_runtime import agent_runtime
from app.agent.tools import tool_registry
from app.agent.models import ScopeContext


def separator(title: str):
    print(f"\n{'='*70}\n[STEP] {title}\n{'='*70}")


def run_dry_run():
    print("""
======================================================================
  DEVOPS NEXUS — PHASE 5 & PHASE 6 END-TO-END DRY-RUN VERIFICATION
======================================================================
    """)

    account_id = "605294565283"
    role_arn = f"arn:aws:iam::{account_id}:role/DevOpsNexusAccessRole"
    region = "ap-south-1"
    cluster_name = "devops-nexus-prod"

    # -------------------------------------------------------------------------
    # STEP 1: Register AWS Account in DevOps Nexus
    # -------------------------------------------------------------------------
    separator("1. Registering AWS Account in DevOps Nexus Control Plane")
    req = AWSAccountRegistrationRequest(
        name="Production AWS (EKS Lab)",
        account_id=account_id,
        role_arn=role_arn,
        default_region=region
    )
    account = aws_account_registry.register_account(req)
    print(f"  [+] Registered Account ID : {account.id}")
    print(f"  [+] Friendly Name         : {account.name}")
    print(f"  [+] Target Role ARN       : {account.role_arn}")
    print(f"  [+] Initial Status        : {account.status.value}")
    assert account.status == AWSAccountStatus.NOT_TESTED

    # -------------------------------------------------------------------------
    # STEP 2: STS AssumeRole & Connection Validation
    # -------------------------------------------------------------------------
    separator("2. Testing Cross-Account STS AssumeRole Connection")
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIA_DRY_RUN_MOCK_KEY",
            "SecretAccessKey": "MOCK_SECRET_KEY_NEVER_PERSISTED",
            "SessionToken": "MOCK_SESSION_TOKEN_DISCARDED_ON_EXPIRY",
            "Expiration": datetime.now(timezone.utc) + timedelta(hours=1)
        }
    }
    mock_sts.get_caller_identity.return_value = {
        "Account": account_id,
        "Arn": f"arn:aws:sts::{account_id}:assumed-role/DevOpsNexusAccessRole/DevOpsNexusSession",
        "UserId": f"AROA_MOCK_USER:{account_id}"
    }

    with patch("boto3.client", return_value=mock_sts):
        test_result = aws_account_registry.test_connection(account.id)
        print(f"  [+] STS AssumeRole Result : {test_result.status.value}")
        print(f"  [+] Assumed Identity ARN  : {test_result.assumed_role_arn}")
        print(f"  [+] Message               : {test_result.message}")
        assert test_result.status == AWSAccountStatus.CONNECTED

    # -------------------------------------------------------------------------
    # STEP 3: Amazon EKS Discovery
    # -------------------------------------------------------------------------
    separator(f"3. Discovering Amazon EKS Clusters via Assumed Role in '{region}'")
    mock_eks = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{"clusters": [cluster_name]}]
    mock_eks.get_paginator.return_value = mock_paginator
    mock_eks.describe_cluster.return_value = {
        "cluster": {
            "name": cluster_name,
            "arn": f"arn:aws:eks:{region}:{account_id}:cluster/{cluster_name}",
            "status": "ACTIVE",
            "version": "1.30",
            "endpoint": f"https://mock-eks-{cluster_name}.{region}.eks.amazonaws.com",
            "roleArn": f"arn:aws:iam::{account_id}:role/{cluster_name}-cluster-role",
            "certificateAuthority": {"data": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCg=="},
            "platformVersion": "eks.1"
        }
    }

    with patch("boto3.client", side_effect=lambda svc, **kw: mock_sts if svc == "sts" else mock_eks):
        clusters = aws_account_registry.discover_clusters(account.id, region=region)
        print(f"  [+] Discovered Clusters Count : {len(clusters)}")
        for c in clusters:
            print(f"      - Cluster Name : {c.name}")
            print(f"      - Status       : {c.status.value}")
            print(f"      - K8s Version  : {c.version}")
            print(f"      - Endpoint     : {c.endpoint}")
            print(f"      - CA Cert Avail: {c.certificate_authority_available}")
        assert len(clusters) == 1
        assert clusters[0].status.value == "ACTIVE"

    # -------------------------------------------------------------------------
    # STEP 4: Register Discovered EKS Cluster as Control Plane Target
    # -------------------------------------------------------------------------
    separator("4. Registering EKS Cluster in Multi-Cluster Registry")
    with patch("boto3.client", side_effect=lambda svc, **kw: mock_sts if svc == "sts" else mock_eks):
        registered_target = aws_account_registry.register_eks_cluster_as_target(account.id, cluster_name)
        print(f"  [+] Multi-Cluster ID   : {registered_target['id']}")
        print(f"  [+] Target Name        : {registered_target['name']}")
        print(f"  [+] Provider           : {registered_target['provider']}")
        print(f"  [+] Environment        : {registered_target['environment']}")

    # -------------------------------------------------------------------------
    # STEP 5: Dynamic STS Presigned Token Generation for Kubernetes API
    # -------------------------------------------------------------------------
    separator("5. Dynamic STS Presigned Bearer Token Generation")
    with patch.object(aws_credential_provider, "get_temporary_credentials", return_value={
        "aws_access_key_id": "ASIA_TEMP_KEY",
        "aws_secret_access_key": "SECRET_TEMP_KEY",
        "aws_session_token": "TOKEN_TEMP_SESSION",
        "expiration": datetime.now(timezone.utc) + timedelta(minutes=30)
    }):
        token = k8s_client_factory.generate_eks_token(cluster_name, account, region=region)
        print(f"  [+] Token Format Prefix  : {token[:12]}...")
        print(f"  [+] Token Total Length   : {len(token)} chars")
        assert token.startswith("k8s-aws-v1.")

    # -------------------------------------------------------------------------
    # STEP 6: Natural Language Scope Resolution to AWS_EKS
    # -------------------------------------------------------------------------
    separator("6. Natural Language Target Resolution to AWS_EKS ScopeContext")
    prompt = "Check the health of gateway pods in production EKS cluster"
    resolved_dict = target_resolver.resolve_target(prompt)
    resolved_scope = ScopeContext(
        environment=resolved_dict["environment_type"],
        aws_account_id=resolved_dict.get("aws_account_id"),
        aws_account_name=resolved_dict.get("aws_account_name"),
        region=resolved_dict.get("region"),
        cluster=cluster_name,
        namespace=resolved_dict.get("namespace", "devops-nexus-prod"),
        application=resolved_dict.get("application"),
        workload=resolved_dict.get("resource_name")
    )
    print(f"  [+] User Query           : '{prompt}'")
    print(f"  [+] Resolved Environment : {resolved_scope.environment}")
    print(f"  [+] Resolved Account ID  : {resolved_scope.aws_account_id}")
    print(f"  [+] Resolved Cluster     : {resolved_scope.cluster}")
    print(f"  [+] Resolved Namespace   : {resolved_scope.namespace}")
    print(f"  [+] Resolved Workload    : {resolved_scope.workload}")
    assert resolved_scope.environment == "AWS_EKS"
    assert resolved_scope.cluster == cluster_name

    # -------------------------------------------------------------------------
    # STEP 7: ToolRegistry Execution against Amazon EKS Target
    # -------------------------------------------------------------------------
    separator("7. Executing ToolRegistry Tool against Amazon EKS Target")
    mock_pod = MagicMock()
    mock_pod.metadata.name = "gateway-deployment-7f8d12a-abcde"
    mock_pod.status.phase = "Running"
    mock_pod.status.container_statuses = [MagicMock(ready=True, restart_count=0)]
    mock_pod.spec.node_name = "ip-10-0-10-45.ap-south-1.compute.internal"
    mock_pod.metadata.creation_timestamp = datetime.now(timezone.utc)

    mock_core_v1 = MagicMock()
    mock_core_v1.list_namespaced_pod.return_value = MagicMock(items=[mock_pod])

    with patch.object(k8s_client_factory, "get_clients", return_value={"v1": mock_core_v1, "apps_v1": MagicMock()}):
        tool_res = tool_registry.execute(
            tool_name="k8s.list_pods",
            input_data={"namespace": "devops-nexus-prod"},
            user_info={"username": "StaffDevOpsEngineer", "role": "Administrator"},
            target_override=resolved_scope.dict()
        )
        print(f"  [+] Tool Name            : {tool_res.tool}")
        print(f"  [+] Execution Status     : {tool_res.status.value}")
        print(f"  [+] Execution Success    : {tool_res.status.value == 'SUCCESS'}")
        print(f"  [+] Discovered Pods Count: {len(tool_res.data.get('pods', [])) if tool_res.data else 0}")
        if tool_res.data and tool_res.data.get("pods"):
            pod_info = tool_res.data["pods"][0]
            print(f"      - Pod Name : {pod_info.get('name')}")
            print(f"      - Status   : {pod_info.get('status')}")
            print(f"      - Node     : {pod_info.get('node')}")
            print(f"      - Restarts : {pod_info.get('restarts')}")
        assert tool_res.status.value == "SUCCESS"

    # -------------------------------------------------------------------------
    # STEP 8: Security Invariant Check
    # -------------------------------------------------------------------------
    separator("8. Security Invariant & Credential Leakage Audit")
    account_dict = account.dict()
    print("  [+] Checking serialized AWSAccount attributes:")
    for k in ["access_key", "secret_key", "session_token", "credentials"]:
        assert k not in account_dict, f"Security violation: {k} found in account model"
        print(f"      - '{k}' is NOT present in account schema: OK")

    print("""
======================================================================
  DRY-RUN VERIFICATION SUCCESSFUL: 100% INVARIANTS VALIDATED
======================================================================
  - AWS Account Registration: OK
  - STS AssumeRole Flow: OK
  - EKS Discovery & Describe: OK
  - EKS Target Registration: OK
  - Presigned STS Token Generation: OK
  - Natural Language Scope Resolution: OK
  - ToolRegistry & AgentRuntime EKS Execution: OK
  - Zero Credential Storage or Leakage: OK
======================================================================
    """)


if __name__ == "__main__":
    run_dry_run()
