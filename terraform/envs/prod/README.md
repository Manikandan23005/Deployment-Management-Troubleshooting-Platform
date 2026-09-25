# Production EKS Environment Deployment Guide

This directory contains the production environment configuration for DevOps Nexus Amazon EKS infrastructure.

## Prerequisites

1. **AWS CLI** installed and configured with credentials for target account (`ap-south-1`).
2. **Terraform CLI** `>= 1.5.0` installed.
3. **kubectl** installed for Kubernetes validation.

## Deployment Steps

```bash
cd terraform

# 1. Initialize Terraform with optional remote backend (or local state for test)
terraform init

# 2. Validate HCL Syntax and Configuration
terraform validate

# 3. Generate Plan
terraform plan -var-file="envs/prod/terraform.tfvars.example" -out="prod.tfplan"

# 4. Apply Infrastructure (When ready)
terraform apply "prod.tfplan"

# 5. Extract Cluster Outputs for DevOps Nexus Phase 5
terraform output -json > /tmp/eks-outputs.json
```

## Cleanup

To decommission the cluster and VPC networking:

```bash
terraform destroy -var-file="envs/prod/terraform.tfvars.example"
```
