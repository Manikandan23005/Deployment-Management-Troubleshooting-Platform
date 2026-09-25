variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones for multi-AZ subnet distribution"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (must match AZ count)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (must match AZ count)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "cluster_name" {
  description = "EKS cluster name used for Kubernetes subnet tagging"
  type        = string
  default     = "devops-nexus-prod"
}

variable "enable_single_nat_gateway" {
  description = "Set to true to provision a single NAT Gateway (cost optimization for lab), or false for one per AZ (high availability)"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Resource tags applied to networking infrastructure"
  type        = map(string)
  default     = {}
}
