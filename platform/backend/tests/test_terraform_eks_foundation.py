"""
Phase 6 — Terraform EKS Infrastructure & Network Foundation Automated Tests
Validates:
1. Terraform module files and HCL syntax
2. Networking architecture (VPC, public/private subnets, NAT, IGW)
3. IAM roles, least privilege policies, and DevOpsNexusAccessRole
4. EKS cluster, managed node group, and Access Entry specifications
5. Phase 5 required output compatibility
"""

import os
import re
import subprocess
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
TERRAFORM_DIR = os.path.join(REPO_ROOT, "terraform")


def test_terraform_directory_structure():
    """Verify clean, production-oriented Terraform directory structure exists."""
    assert os.path.isdir(TERRAFORM_DIR), "terraform directory must exist"
    
    expected_root_files = [
        "versions.tf", "provider.tf", "variables.tf", "main.tf", "outputs.tf", "terraform.tfvars.example"
    ]
    for fname in expected_root_files:
        path = os.path.join(TERRAFORM_DIR, fname)
        assert os.path.isfile(path), f"Expected root terraform file {fname} not found"

    expected_modules = ["networking", "eks", "iam"]
    for mod in expected_modules:
        mod_dir = os.path.join(TERRAFORM_DIR, "modules", mod)
        assert os.path.isdir(mod_dir), f"Expected terraform module {mod} not found"
        for mod_file in ["main.tf", "variables.tf", "outputs.tf"]:
            assert os.path.isfile(os.path.join(mod_dir, mod_file)), f"{mod}/{mod_file} not found"

    expected_env_files = [
        os.path.join(TERRAFORM_DIR, "envs/prod/backend.hcl.example"),
        os.path.join(TERRAFORM_DIR, "envs/prod/terraform.tfvars.example"),
        os.path.join(TERRAFORM_DIR, "envs/prod/README.md")
    ]
    for env_file in expected_env_files:
        assert os.path.isfile(env_file), f"Expected env file {env_file} not found"


def test_terraform_fmt_check():
    """Verify all Terraform code is strictly formatted according to HCL conventions."""
    res = subprocess.run(
        ["terraform", "fmt", "-check"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"Terraform formatting failed:\n{res.stdout}\n{res.stderr}"


def test_terraform_validate():
    """Verify Terraform configuration validates successfully with HashiCorp AWS provider."""
    res = subprocess.run(
        ["terraform", "validate"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"Terraform validation failed:\n{res.stdout}\n{res.stderr}"


def test_networking_module_specifications():
    """Verify networking module defines VPC, private/public subnets, and NAT Gateway."""
    net_main = os.path.join(TERRAFORM_DIR, "modules/networking/main.tf")
    with open(net_main, "r") as f:
        content = f.read()

    assert 'resource "aws_vpc" "main"' in content
    assert 'resource "aws_internet_gateway" "main"' in content
    assert 'resource "aws_subnet" "public"' in content
    assert 'resource "aws_subnet" "private"' in content
    assert 'resource "aws_nat_gateway" "main"' in content
    assert '"kubernetes.io/role/elb"' in content
    assert '"kubernetes.io/role/internal-elb"' in content


def test_iam_module_least_privilege():
    """Verify IAM module creates dedicated DevOpsNexusAccessRole without AdministratorAccess."""
    iam_main = os.path.join(TERRAFORM_DIR, "modules/iam/main.tf")
    with open(iam_main, "r") as f:
        content = f.read()

    assert 'resource "aws_iam_role" "devops_nexus_access"' in content
    assert 'resource "aws_iam_policy" "devops_nexus_policy"' in content
    assert '"sts:GetCallerIdentity"' in content
    assert '"eks:ListClusters"' in content
    assert '"eks:DescribeCluster"' in content
    # Invariant: No AdministratorAccess attachment for DevOps Nexus
    assert "AdministratorAccess" not in content


def test_eks_module_access_entry_and_addons():
    """Verify EKS module configures Access Entries and core add-ons."""
    eks_main = os.path.join(TERRAFORM_DIR, "modules/eks/main.tf")
    with open(eks_main, "r") as f:
        content = f.read()

    assert 'resource "aws_eks_cluster" "main"' in content
    assert 'resource "aws_eks_node_group" "main"' in content
    assert 'resource "aws_eks_access_entry" "devops_nexus"' in content
    assert 'resource "aws_eks_access_policy_association" "devops_nexus_cluster_admin"' in content
    assert 'resource "aws_eks_addon" "vpc_cni"' in content
    assert 'resource "aws_eks_addon" "kube_proxy"' in content
    assert 'resource "aws_eks_addon" "coredns"' in content
    assert 'resource "aws_eks_addon" "aws_ebs_csi_driver"' in content


def test_phase5_required_outputs():
    """Verify root outputs.tf provides all outputs required by DevOps Nexus Phase 5 integration."""
    outputs_file = os.path.join(TERRAFORM_DIR, "outputs.tf")
    with open(outputs_file, "r") as f:
        content = f.read()

    required_outputs = [
        "aws_account_id",
        "aws_region",
        "vpc_id",
        "private_subnet_ids",
        "public_subnet_ids",
        "eks_cluster_name",
        "eks_cluster_arn",
        "eks_cluster_endpoint",
        "eks_cluster_certificate_authority_data",
        "eks_cluster_security_group_id",
        "node_group_names",
        "devops_nexus_access_role_arn",
        "oidc_provider_arn"
    ]
    for out in required_outputs:
        pattern = rf'output\s+"{out}"\s+{{'
        assert re.search(pattern, content), f"Required output '{out}' missing from outputs.tf"
