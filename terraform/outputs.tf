data "aws_caller_identity" "current" {}

output "aws_account_id" {
  description = "Target AWS Account ID where EKS infrastructure is provisioned"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS Region hosting the infrastructure"
  value       = var.aws_region
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.networking.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of private subnet IDs hosting EKS worker nodes"
  value       = module.networking.private_subnet_ids
}

output "eks_cluster_name" {
  description = "Name of the Amazon EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_arn" {
  description = "ARN of the Amazon EKS cluster"
  value       = module.eks.cluster_arn
}

output "eks_cluster_endpoint" {
  description = "Kubernetes API endpoint for the Amazon EKS cluster"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_certificate_authority_data" {
  description = "Base64 encoded CA certificate data for TLS validation"
  value       = module.eks.cluster_certificate_authority_data
}

output "eks_cluster_security_group_id" {
  description = "Security Group ID attached to the EKS control plane"
  value       = module.eks.cluster_security_group_id
}

output "node_group_names" {
  description = "List of Managed Node Group names"
  value       = [module.eks.node_group_name]
}

output "devops_nexus_access_role_arn" {
  description = "ARN of the IAM Role for DevOps Nexus Phase 5 cross-account STS AssumeRole"
  value       = module.iam.devops_nexus_access_role_arn
}

output "oidc_provider_arn" {
  description = "ARN of the IAM OIDC Provider for Kubernetes IRSA"
  value       = module.eks.oidc_provider_arn
}

output "oidc_provider_url" {
  description = "URL of the IAM OIDC Provider without https://"
  value       = module.eks.oidc_provider_url
}

output "ecr_repository_urls" {
  description = "Map of microservice names to Amazon ECR repository URLs"
  value       = module.ecr.repository_urls
}

output "ecr_repository_arns" {
  description = "Map of microservice names to Amazon ECR repository ARNs"
  value       = module.ecr.repository_arns
}

