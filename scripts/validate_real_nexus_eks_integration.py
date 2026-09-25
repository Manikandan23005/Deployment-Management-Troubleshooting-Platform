#!/usr/bin/env python3
"""
DevOps Nexus — Phase 6 Real AWS & EKS Live Integration Validation
Executes real AWS STS AssumeRole, EKS discovery, dynamic k8s-aws-v1 token auth,
Kubernetes API queries, ToolRegistry executions, and AgentRuntime live investigation.
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Add backend and platform directory to sys.path
root_path = Path(__file__).resolve().parent.parent
platform_path = root_path / "platform"
backend_path = platform_path / "backend"
sys.path.insert(0, str(platform_path))
sys.path.insert(0, str(backend_path))

import boto3
from app.aws.models import AWSAccountRegistrationRequest, AWSAccountStatus
from app.aws.account_registry import aws_account_registry
from app.clients.k8s_factory import k8s_client_factory
from app.agent.tools.registry import tool_registry
from app.agent.models import ScopeContext


def print_banner(title: str):
    print(f"\n{'=' * 75}\n>>> {title}\n{'=' * 75}")


async def run_live_validation():
    print_banner("PHASE 6 LIVE VALIDATION — REAL AWS & EKS INTEGRATION")
    
    cluster_name = "devops-nexus-prod"
    region = "ap-south-1"
    
    # -------------------------------------------------------------
    # 1. Real AWS & IAM Identity Validation
    # -------------------------------------------------------------
    print("\n[1] Validating Local AWS Credentials and Caller Identity...")
    sts_client = boto3.client("sts", region_name=region)
    local_identity = sts_client.get_caller_identity()
    account_id = local_identity.get("Account")
    caller_arn = local_identity.get("Arn")
    print(f"    AWS Account ID : {account_id}")
    print(f"    Caller ARN     : {caller_arn}")
    
    role_arn = f"arn:aws:iam::{account_id}:role/DevOpsNexusAccessRole"
    
    # -------------------------------------------------------------
    # 2. Real EKS Cluster & Node Group Validation
    # -------------------------------------------------------------
    print("\n[2] Validating Real EKS Cluster & Managed Node Groups...")
    eks_client = boto3.client("eks", region_name=region)
    cluster_desc = eks_client.describe_cluster(name=cluster_name)["cluster"]
    cluster_status = cluster_desc.get("status")
    cluster_endpoint = cluster_desc.get("endpoint")
    cluster_arn = cluster_desc.get("arn")
    k8s_version = cluster_desc.get("version")
    print(f"    Cluster Name     : {cluster_name}")
    print(f"    Cluster Status   : {cluster_status}")
    print(f"    Cluster Version  : {k8s_version}")
    print(f"    Cluster Endpoint : {cluster_endpoint}")
    print(f"    Cluster ARN      : {cluster_arn}")
    assert cluster_status == "ACTIVE", f"Cluster status is {cluster_status}, expected ACTIVE"

    nodegroups = eks_client.list_nodegroups(clusterName=cluster_name).get("nodegroups", [])
    print(f"    Managed Node Groups ({len(nodegroups)}): {nodegroups}")
    for ng in nodegroups:
        ng_desc = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng)["nodegroup"]
        print(f"      - {ng}: status={ng_desc.get('status')}, desired={ng_desc.get('scalingConfig', {}).get('desiredSize')}, amiType={ng_desc.get('amiType')}")

    # Add-ons
    addons = eks_client.list_addons(clusterName=cluster_name).get("addons", [])
    print(f"    Configured Add-ons ({len(addons)}):")
    for addon in addons:
        addon_desc = eks_client.describe_addon(clusterName=cluster_name, addonName=addon)["addon"]
        print(f"      - {addon:20}: {addon_desc.get('status')} (v{addon_desc.get('addonVersion')})")

    # Access Entries
    access_entries = eks_client.list_access_entries(clusterName=cluster_name).get("accessEntries", [])
    print(f"    Access Entries ({len(access_entries)}):")
    for ae in access_entries:
        print(f"      - {ae}")

    # -------------------------------------------------------------
    # 3. Real DevOps Nexus AWS Account Registration
    # -------------------------------------------------------------
    print("\n[3] Registering AWS Account in DevOps Nexus AWSAccountRegistryService...")
    reg_req = AWSAccountRegistrationRequest(
        name="DevOpsNexus-Production-AWS",
        account_id=account_id,
        role_arn=role_arn,
        external_id=None,
        default_region=region
    )
    account_record = aws_account_registry.register_account(reg_req)
    print(f"    Registered Account Name : {account_record.name}")
    print(f"    Registered Account ID   : {account_record.account_id}")
    print(f"    Assumed Role ARN        : {account_record.role_arn}")
    print(f"    Initial Status          : {account_record.status}")

    # -------------------------------------------------------------
    # 4. Real STS AssumeRole Verification via Nexus Backend
    # -------------------------------------------------------------
    print("\n[4] Testing STS AssumeRole via aws_account_registry.test_connection...")
    conn_result = aws_account_registry.test_connection(account_id)
    print(f"    Assumed Account ID      : {conn_result.account_id}")
    print(f"    Assumed Role Principal  : {conn_result.assumed_role_arn}")
    print(f"    Connection Status       : {conn_result.status}")
    print(f"    Validation Message      : {conn_result.message}")
    assert conn_result.status == AWSAccountStatus.CONNECTED, "Connection test did not return CONNECTED status"

    # -------------------------------------------------------------
    # 5. Real EKS Discovery via Nexus Backend
    # -------------------------------------------------------------
    print("\n[5] Discovering EKS Clusters via aws_account_registry.discover_clusters...")
    discovered_clusters = aws_account_registry.discover_clusters(account_id, region=region)
    print(f"    Discovered {len(discovered_clusters)} EKS Cluster(s):")
    for c in discovered_clusters:
        print(f"      - Name: {c.name}, Status: {c.status}, Version: {c.version}, Endpoint: {c.endpoint[:45]}...")

    # Register EKS cluster as active Nexus target
    registered_target = aws_account_registry.register_eks_cluster_as_target(
        account_identifier=account_id,
        cluster_name=cluster_name,
        region=region,
        is_default=True
    )
    target_cluster_id = registered_target.get("id")
    print(f"    Registered Nexus Target : ID={target_cluster_id}, Name={registered_target.get('name')}")

    # -------------------------------------------------------------
    # 6. Real Kubernetes API Connection & Dynamic STS Token Auth
    # -------------------------------------------------------------
    print("\n[6] Initializing Real Kubernetes API Client via k8s_client_factory...")
    clients = k8s_client_factory.get_clients(cluster_id=target_cluster_id)
    core_v1 = clients["v1"]
    apps_v1 = clients["apps_v1"]

    print("    Querying Live K8s Namespaces...")
    ns_list = core_v1.list_namespace()
    namespaces = [ns.metadata.name for ns in ns_list.items]
    print(f"    Live Namespaces ({len(namespaces)}): {namespaces}")

    print("    Querying Live K8s Nodes...")
    node_list = core_v1.list_node()
    for node in node_list.items:
        ready_status = any(c.type == "Ready" and c.status == "True" for c in node.status.conditions)
        print(f"      - Node: {node.metadata.name} | Ready={ready_status} | Version={node.status.node_info.kubelet_version} | OS={node.status.node_info.os_image}")

    print("    Querying Live K8s Pods...")
    pod_list = core_v1.list_pod_for_all_namespaces()
    print(f"    Total Live Pods Running: {len(pod_list.items)}")
    for pod in pod_list.items:
        print(f"      - [{pod.metadata.namespace}] {pod.metadata.name} ({pod.status.phase}) | Node: {pod.spec.node_name}")

    print("    Querying Live K8s Deployments...")
    deploy_list = apps_v1.list_deployment_for_all_namespaces()
    print(f"    Total Live Deployments: {len(deploy_list.items)}")
    for dep in deploy_list.items:
        print(f"      - [{dep.metadata.namespace}] {dep.metadata.name} (replicas: {dep.status.ready_replicas}/{dep.spec.replicas})")

    # -------------------------------------------------------------
    # 7. Real ToolRegistry Execution
    # -------------------------------------------------------------
    print("\n[7] Executing Live Read-Only Kubernetes Tool via ToolRegistry & AgentRuntime...")
    from app.agent.agent_runtime import agent_runtime

    scope = ScopeContext(
        environment="AWS_EKS",
        cluster=f"eks-{cluster_name}",
        cluster_id=target_cluster_id,
        aws_account_id=account_id,
        region=region,
        namespace="kube-system",
        workload="coredns"
    )

    tool_result = agent_runtime.execute_tool(
        tool_name="k8s.list_pods",
        input_data={"namespace": "kube-system", "cluster_id": target_cluster_id},
        user_info={"username": "admin", "role": "Admin", "permissions": ["*:*"]}
    )
    print(f"    Tool Execution Status  : {tool_result.status.value}")
    print(f"    Tool Execution Success : {tool_result.success}")
    print(f"    Tool Execution Data    : Found {len(tool_result.data or [])} pods in kube-system")
    for p in (tool_result.data or []):
        print(f"      - Pod: {p.get('name')} | Phase: {p.get('status')} | Node: {p.get('node')}")

    # -------------------------------------------------------------
    # 8. Real AgentRuntime Live Investigation
    # -------------------------------------------------------------
    print("\n[8] Executing Real AI Agent Investigation against Live EKS...")
    investigation_prompt = "Check the health of the gateway workload in the EKS cluster."
    
    agent_inv = agent_runtime.execute_investigation(
        prompt=investigation_prompt,
        resource_name="gateway",
        namespace="kube-system",
        cluster_id=target_cluster_id,
        scope=scope
    )
    print(f"    Intent Classified    : {agent_inv.get('intent')}")
    print(f"    Target Resolved      : {agent_inv.get('target')}")
    print(f"    Evidence Quality     : {agent_inv.get('evidence_quality')}")
    print(f"    Executive Summary    : {agent_inv.get('executive_summary')}")
    print(f"    Root Cause           : {agent_inv.get('root_cause')}")
    print("    Verified Live Evidence Items:")
    for item in agent_inv.get("verified_evidence", []):
        print(f"      * {item}")

    print_banner("PHASE 6 LIVE VALIDATION COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    asyncio.run(run_live_validation())
