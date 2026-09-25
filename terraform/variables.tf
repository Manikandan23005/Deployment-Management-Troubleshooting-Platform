variable "aws_region" {
  description = "AWS Region where all infrastructure resources will be deployed"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Target environment name (e.g. prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "cluster_name" {
  description = "Name of the Amazon EKS cluster"
  type        = string
  default     = "devops-nexus-prod"
}

variable "kubernetes_version" {
  description = "Kubernetes control plane version for Amazon EKS"
  type        = string
  default     = "1.30"
}

variable "assume_role_arn" {
  description = "Optional IAM Role ARN to assume for Terraform AWS execution"
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated EKS VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones for multi-AZ subnet deployment"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (worker nodes & workloads)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "enable_single_nat_gateway" {
  description = "Set to true for single NAT gateway (cost-effective for lab environments), or false for multi-AZ NAT gateways (HA production)"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "List of CIDRs allowed to reach the EKS public API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "node_instance_types" {
  description = "EC2 instance types for the EKS Managed Node Group"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "Capacity type for worker nodes (ON_DEMAND or SPOT)"
  type        = string
  default     = "ON_DEMAND"
}

variable "ami_type" {
  description = "AMI Type for EKS Node Group (AL2023_x86_64_STANDARD for EKS 1.30+)"
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "desired_size" {
  description = "Desired number of worker nodes in the Managed Node Group"
  type        = number
  default     = 2
}

variable "min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 1
}

variable "max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 4
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
