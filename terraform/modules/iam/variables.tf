variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "devops-nexus-prod"
}

variable "trusted_principal_arns" {
  description = "List of IAM Principal ARNs allowed to assume the DevOpsNexusAccessRole (e.g. CI/CD or backend identity)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Resource tags applied to IAM roles and policies"
  type        = map(string)
  default     = {}
}
