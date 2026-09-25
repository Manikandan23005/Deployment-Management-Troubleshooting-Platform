variable "cluster_name" {
  description = "Name of the Amazon EKS cluster"
  type        = string
  default     = "devops-nexus-prod"
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS control plane"
  type        = string
  default     = "1.30"
}

variable "vpc_id" {
  description = "ID of the VPC where the cluster will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for EKS control plane network interfaces (public + private subnets)"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private Subnet IDs where EKS Managed Node Groups will run"
  type        = list(string)
}

variable "cluster_role_arn" {
  description = "IAM Role ARN for EKS Cluster Control Plane"
  type        = string
}

variable "node_role_arn" {
  description = "IAM Role ARN for EKS Managed Node Groups"
  type        = string
}

variable "devops_nexus_role_arn" {
  description = "IAM Role ARN for DevOps Nexus Access Entry integration"
  type        = string
  default     = ""
}

variable "enable_devops_nexus_access_entry" {
  description = "Whether to configure EKS Access Entry for DevOps Nexus"
  type        = bool
  default     = true
}

variable "cluster_endpoint_private_access" {
  description = "Enable private API server endpoint access"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access" {
  description = "Enable public API server endpoint access"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "List of CIDR blocks that can access the Amazon EKS public API server endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enabled_cluster_log_types" {
  description = "List of desired control plane log types to enable"
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

variable "node_group_name" {
  description = "Name of the primary Managed Node Group"
  type        = string
  default     = "general-compute"
}

variable "node_instance_types" {
  description = "EC2 instance types for the Managed Node Group"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "Capacity type for Node Group: ON_DEMAND or SPOT"
  type        = string
  default     = "ON_DEMAND"
}

variable "ami_type" {
  description = "AMI Type for EKS Node Group (AL2023_x86_64_STANDARD for EKS 1.30+)"
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "desired_size" {
  description = "Desired number of worker nodes"
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

variable "enable_ebs_csi_addon" {
  description = "Whether to enable the aws-ebs-csi-driver add-on"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Resource tags applied to EKS resources"
  type        = map(string)
  default     = {}
}
