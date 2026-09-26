# --- Amazon ECR Module for DevOps Nexus Microservices ---

variable "environment" {
  type        = string
  description = "Environment name (e.g., prod)"
  default     = "prod"
}

variable "repositories" {
  type        = list(string)
  description = "List of ECR repository names to create"
  default = [
    "auth",
    "gateway",
    "orders",
    "payment",
    "products",
    "users",
    "notification",
    "frontend"
  ]
}

variable "image_tag_mutability" {
  type        = string
  description = "Image tag mutability (MUTABLE or IMMUTABLE)"
  default     = "MUTABLE"
}

variable "scan_on_push" {
  type        = bool
  description = "Enable vulnerability scanning on image push"
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}
