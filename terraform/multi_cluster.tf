# =============================================================================
# Multi-Cluster Architecture: Dev, QA, and Staging Environments
# =============================================================================
# Provisions 3 cost-optimized EKS clusters in ap-south-1 sharing the primary
# VPC and NAT Gateway, running Spot EC2 instances to demonstrate multi-cluster
# discovery, management, and troubleshooting in DevOps Nexus.

locals {
  additional_clusters = toset([
    "devops-nexus-dev",
    "devops-nexus-qa",
    "devops-nexus-stage"
  ])
}

# -----------------------------------------------------------------------------
# 1. IAM Roles & Policy Attachments for Additional EKS Clusters
# -----------------------------------------------------------------------------
resource "aws_iam_role" "cluster_additional" {
  for_each = local.additional_clusters

  name        = "${each.key}-cluster-role"
  description = "IAM Role for EKS Control Plane of cluster ${each.key}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${each.key}-cluster-role"
      Environment = replace(each.key, "devops-nexus-", "")
    }
  )
}

resource "aws_iam_role_policy_attachment" "cluster_policy_additional" {
  for_each   = local.additional_clusters
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster_additional[each.key].name
}

resource "aws_iam_role_policy_attachment" "cluster_vpc_resource_controller_additional" {
  for_each   = local.additional_clusters
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.cluster_additional[each.key].name
}

# -----------------------------------------------------------------------------
# 2. IAM Roles & Policy Attachments for Managed Node Groups
# -----------------------------------------------------------------------------
resource "aws_iam_role" "node_additional" {
  for_each = local.additional_clusters

  name        = "${each.key}-node-role"
  description = "IAM Role for EKS Managed Node Group of cluster ${each.key}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${each.key}-node-role"
      Environment = replace(each.key, "devops-nexus-", "")
    }
  )
}

resource "aws_iam_role_policy_attachment" "node_worker_policy_additional" {
  for_each   = local.additional_clusters
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node_additional[each.key].name
}

resource "aws_iam_role_policy_attachment" "node_cni_policy_additional" {
  for_each   = local.additional_clusters
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node_additional[each.key].name
}

resource "aws_iam_role_policy_attachment" "node_ecr_policy_additional" {
  for_each   = local.additional_clusters
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node_additional[each.key].name
}

# -----------------------------------------------------------------------------
# 3. Amazon EKS Clusters & Managed Spot Node Groups
# -----------------------------------------------------------------------------
module "eks_additional" {
  for_each = local.additional_clusters
  source   = "./modules/eks"

  cluster_name                         = each.key
  kubernetes_version                   = var.kubernetes_version
  vpc_id                               = module.networking.vpc_id
  subnet_ids                           = concat(module.networking.public_subnet_ids, module.networking.private_subnet_ids)
  private_subnet_ids                   = module.networking.private_subnet_ids
  cluster_role_arn                     = aws_iam_role.cluster_additional[each.key].arn
  node_role_arn                        = aws_iam_role.node_additional[each.key].arn
  devops_nexus_role_arn                = module.iam.devops_nexus_access_role_arn
  enable_devops_nexus_access_entry     = true
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  node_instance_types                  = ["t3.medium"]
  node_capacity_type                   = "SPOT"
  ami_type                             = var.ami_type
  desired_size                         = 1
  min_size                             = 1
  max_size                             = 2
  enable_ebs_csi_addon                 = false

  tags = merge(
    var.tags,
    {
      Environment = replace(each.key, "devops-nexus-", "")
      ManagedBy   = "Terraform"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy_additional,
    aws_iam_role_policy_attachment.cluster_vpc_resource_controller_additional,
    aws_iam_role_policy_attachment.node_worker_policy_additional,
    aws_iam_role_policy_attachment.node_cni_policy_additional,
    aws_iam_role_policy_attachment.node_ecr_policy_additional,
    module.networking,
    module.iam
  ]
}
