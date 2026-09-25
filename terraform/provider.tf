provider "aws" {
  region = var.aws_region

  dynamic "assume_role" {
    for_each = var.assume_role_arn != "" ? [var.assume_role_arn] : []
    content {
      role_arn     = assume_role.value
      session_name = "DevOpsNexusTerraformSession"
    }
  }

  default_tags {
    tags = merge(
      {
        Project     = "DevOpsNexus"
        Environment = var.environment
        ManagedBy   = "Terraform"
      },
      var.tags
    )
  }
}
