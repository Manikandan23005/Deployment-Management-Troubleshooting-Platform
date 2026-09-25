output "eks_cluster_role_arn" {
  description = "ARN of the EKS Cluster control plane IAM role"
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_cluster_role_name" {
  description = "Name of the EKS Cluster control plane IAM role"
  value       = aws_iam_role.eks_cluster.name
}

output "eks_node_role_arn" {
  description = "ARN of the EKS Worker Nodes IAM role"
  value       = aws_iam_role.eks_nodes.arn
}

output "eks_node_role_name" {
  description = "Name of the EKS Worker Nodes IAM role"
  value       = aws_iam_role.eks_nodes.name
}

output "devops_nexus_access_role_arn" {
  description = "ARN of the dedicated DevOpsNexusAccessRole assumed by DevOps Nexus backend"
  value       = aws_iam_role.devops_nexus_access.arn
}

output "devops_nexus_access_role_name" {
  description = "Name of the dedicated DevOpsNexusAccessRole"
  value       = aws_iam_role.devops_nexus_access.name
}
