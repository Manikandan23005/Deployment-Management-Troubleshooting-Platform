# --- Amazon ECR Repositories & Lifecycle Policies ---

resource "aws_ecr_repository" "apps" {
  for_each = toset(var.repositories)

  name                 = "devops-nexus/${each.value}"
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    var.tags,
    {
      Name        = "devops-nexus/${each.value}"
      Application = each.value
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  )
}

resource "aws_ecr_lifecycle_policy" "apps_lifecycle" {
  for_each = aws_ecr_repository.apps

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 14 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Retain max 30 tagged release images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "release", "1.", "2."]
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
