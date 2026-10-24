# =============================================================================
# Multi-Cluster Outputs
# =============================================================================

output "additional_eks_cluster_names" {
  description = "Names of the additional EKS clusters"
  value       = [for k, v in module.eks_additional : v.cluster_name]
}

output "additional_eks_cluster_arns" {
  description = "ARNs of the additional EKS clusters"
  value       = { for k, v in module.eks_additional : k => v.cluster_arn }
}

output "additional_eks_cluster_endpoints" {
  description = "Kubernetes API endpoints for the additional EKS clusters"
  value       = { for k, v in module.eks_additional : k => v.cluster_endpoint }
}

output "all_eks_cluster_names" {
  description = "List of all provisioned EKS clusters including primary and additional"
  value       = concat([module.eks.cluster_name], [for k, v in module.eks_additional : v.cluster_name])
}
