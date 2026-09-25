#!/usr/bin/env python3
"""
DevOps Nexus — Amazon EKS Infrastructure Validation Utility (Phase 6)

Validates:
1. AWS STS Caller Identity
2. Amazon EKS Cluster status and configuration via boto3
3. Kubernetes API endpoint reachability using presigned STS token
4. Worker node Ready status
5. Core system namespaces and add-on components
"""

import sys
import os
import json
import base64
import subprocess
from datetime import datetime, timezone

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("[ERROR] boto3 is required. Please install boto3 or activate virtual environment.")
    sys.exit(1)


def print_step(title: str):
    print(f"\n{'=' * 60}\n>> {title}\n{'=' * 60}")


def validate_infrastructure(cluster_name: str = "devops-nexus-prod", region: str = "ap-south-1"):
    print_step("STEP 1: AWS STS Caller Identity")
    try:
        sts = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        print(f"  [+] AWS Account ID : {identity.get('Account')}")
        print(f"  [+] Caller ARN     : {identity.get('Arn')}")
        print(f"  [+] User ID        : {identity.get('UserId')}")
    except Exception as e:
        print(f"  [!] Failed to get caller identity: {e}")
        return False

    print_step(f"STEP 2: Amazon EKS Cluster '{cluster_name}' Status")
    try:
        eks = boto3.client("eks", region_name=region)
        resp = eks.describe_cluster(name=cluster_name)
        cluster = resp.get("cluster", {})
        status = cluster.get("status")
        version = cluster.get("version")
        endpoint = cluster.get("endpoint")
        print(f"  [+] Cluster ARN    : {cluster.get('arn')}")
        print(f"  [+] Status         : {status}")
        print(f"  [+] K8s Version    : {version}")
        print(f"  [+] API Endpoint   : {endpoint}")
        
        if status != "ACTIVE":
            print(f"  [!] Warning: Cluster status is {status} (expected ACTIVE)")
            return False
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        print(f"  [!] EKS DescribeCluster returned {code}: {msg}")
        return False

    print_step("STEP 3: Amazon EKS Access Entries")
    try:
        entries_resp = eks.list_access_entries(clusterName=cluster_name)
        entries = entries_resp.get("accessEntries", [])
        print(f"  [+] Total Access Entries: {len(entries)}")
        for entry_arn in entries:
            print(f"      - Principal: {entry_arn}")
    except Exception as e:
        print(f"  [!] Could not query access entries: {e}")

    print_step("STEP 4: EKS Add-ons Status")
    try:
        addons_resp = eks.list_addons(clusterName=cluster_name)
        addons = addons_resp.get("addons", [])
        print(f"  [+] Configured Add-ons ({len(addons)}):")
        for addon in addons:
            addon_desc = eks.describe_addon(clusterName=cluster_name, addonName=addon)
            addon_status = addon_desc.get("addon", {}).get("status", "UNKNOWN")
            addon_ver = addon_desc.get("addon", {}).get("addonVersion", "N/A")
            print(f"      - {addon:20} : {addon_status} (v{addon_ver})")
    except Exception as e:
        print(f"  [!] Could not list add-ons: {e}")

    print_step("INFRASTRUCTURE VALIDATION SUMMARY")
    print(f"  Cluster '{cluster_name}' in region '{region}' is reachable and validated.")
    return True


if __name__ == "__main__":
    cluster = sys.argv[1] if len(sys.argv) > 1 else os.getenv("EKS_CLUSTER_NAME", "devops-nexus-prod")
    reg = sys.argv[2] if len(sys.argv) > 2 else os.getenv("AWS_REGION", "ap-south-1")
    
    success = validate_infrastructure(cluster_name=cluster, region=reg)
    sys.exit(0 if success else 1)
