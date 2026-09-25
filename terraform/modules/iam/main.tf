data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  effective_trusted_principals = length(var.trusted_principal_arns) > 0 ? var.trusted_principal_arns : [data.aws_caller_identity.current.arn]
}

# -----------------------------------------------------------------------------
# 1. EKS Control Plane IAM Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "eks_cluster" {
  name        = "${var.cluster_name}-cluster-role"
  description = "IAM Role for Amazon EKS Control Plane"

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
      Name = "${var.cluster_name}-cluster-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

resource "aws_iam_role_policy_attachment" "eks_vpc_resource_controller" {
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.eks_cluster.name
}

# -----------------------------------------------------------------------------
# 2. EKS Worker Nodes IAM Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "eks_nodes" {
  name        = "${var.cluster_name}-node-role"
  description = "IAM Role for Amazon EKS Managed Node Groups"

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
      Name = "${var.cluster_name}-node-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "node_worker_policy" {
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_nodes.name
}

resource "aws_iam_role_policy_attachment" "node_cni_policy" {
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_nodes.name
}

resource "aws_iam_role_policy_attachment" "node_ecr_policy" {
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_nodes.name
}

# -----------------------------------------------------------------------------
# 3. DevOps Nexus Access Role (Cross-Account / STS AssumeRole Target)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "devops_nexus_access" {
  name        = "DevOpsNexusAccessRole"
  description = "Dedicated IAM Role for DevOps Nexus Platform cross-account EKS management & troubleshooting"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = local.effective_trusted_principals
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name    = "DevOpsNexusAccessRole"
      Purpose = "DevOpsNexusControlPlane"
    }
  )
}

resource "aws_iam_policy" "devops_nexus_policy" {
  name        = "DevOpsNexusEKSAccessPolicy"
  description = "Least-privilege policy for DevOps Nexus AWS STS and EKS discovery APIs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EKSDiscoveryAndTelemetry"
        Effect = "Allow"
        Action = [
          "eks:ListClusters",
          "eks:DescribeCluster",
          "eks:ListAccessEntries",
          "eks:DescribeAccessEntry",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      },
      {
        Sid    = "STSIdentityValidation"
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "devops_nexus_attach" {
  policy_arn = aws_iam_policy.devops_nexus_policy.arn
  role       = aws_iam_role.devops_nexus_access.name
}

