# --- Outputs for Terraform ECR Module ---

output "repository_urls" {
  description = "Map of application names to their ECR repository URLs"
  value = {
    for k, v in aws_ecr_repository.apps : k => v.repository_url
  }
}

output "repository_arns" {
  description = "Map of application names to their ECR repository ARNs"
  value = {
    for k, v in aws_ecr_repository.apps : k => v.arn
  }
}

output "registry_id" {
  description = "The registry ID where repositories are created"
  value       = values(aws_ecr_repository.apps)[0].registry_id
}
