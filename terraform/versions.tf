terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote S3 backend with DynamoDB state locking
  # To enable remote state in CI/CD or production:
  #   terraform init -backend-config=envs/prod/backend.hcl
  #
  # backend "s3" {}
}
