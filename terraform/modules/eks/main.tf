data "aws_partition" "current" {}

data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# -----------------------------------------------------------------------------
# 1. Security Groups
# -----------------------------------------------------------------------------

# Control Plane Security Group
resource "aws_security_group" "cluster" {
  name        = "${var.cluster_name}-cluster-sg"
  description = "Security group for EKS control plane communicating with worker nodes"
  vpc_id      = var.vpc_id

  egress {
    description = "Allow control plane all outbound communication"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-cluster-sg"
    }
  )
}

# Worker Nodes Security Group
resource "aws_security_group" "nodes" {
  name        = "${var.cluster_name}-nodes-sg"
  description = "Security group for all nodes in the cluster"
  vpc_id      = var.vpc_id

  egress {
    description = "Allow nodes all outbound communication"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name                                        = "${var.cluster_name}-nodes-sg"
      "kubernetes.io/cluster/${var.cluster_name}" = "owned"
    }
  )
}

# Allow Node-to-Node communication (Pod networking, CoreDNS, service mesh)
resource "aws_security_group_rule" "nodes_internal" {
  description              = "Allow nodes to communicate with each other"
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.nodes.id
  source_security_group_id = aws_security_group.nodes.id
}

# Allow Control Plane to communicate with Worker Nodes (kubelet API, metrics, logs)
resource "aws_security_group_rule" "cluster_to_nodes_https" {
  description              = "Allow control plane to communicate with worker nodes kubelet & webhook pods"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.nodes.id
  source_security_group_id = aws_security_group.cluster.id
}

resource "aws_security_group_rule" "cluster_to_nodes_kubelet" {
  description              = "Allow control plane to communicate with kubelet port 10250"
  type                     = "ingress"
  from_port                = 10250
  to_port                  = 10250
  protocol                 = "tcp"
  security_group_id        = aws_security_group.nodes.id
  source_security_group_id = aws_security_group.cluster.id
}

# Allow Worker Nodes to communicate with Control Plane HTTPS endpoint
resource "aws_security_group_rule" "nodes_to_cluster_https" {
  description              = "Allow worker nodes to communicate with control plane API server"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.cluster.id
  source_security_group_id = aws_security_group.nodes.id
}

# -----------------------------------------------------------------------------
# 2. Amazon EKS Cluster Control Plane
# -----------------------------------------------------------------------------
resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = var.cluster_role_arn

  vpc_config {
    subnet_ids              = var.subnet_ids
    security_group_ids      = [aws_security_group.cluster.id]
    endpoint_private_access = var.cluster_endpoint_private_access
    endpoint_public_access  = var.cluster_endpoint_public_access
    public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
  }

  enabled_cluster_log_types = var.enabled_cluster_log_types

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  tags = merge(
    var.tags,
    {
      Name = var.cluster_name
    }
  )
}

# -----------------------------------------------------------------------------
# 3. OpenID Connect (OIDC) Provider for IRSA / Workload Identity
# -----------------------------------------------------------------------------
resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-oidc-provider"
    }
  )
}

# -----------------------------------------------------------------------------
# 4. Amazon EKS Managed Node Group
# -----------------------------------------------------------------------------
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = var.node_group_name
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }

  instance_types = var.node_instance_types
  capacity_type  = var.node_capacity_type
  ami_type       = var.ami_type

  update_config {
    max_unavailable = 1
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-${var.node_group_name}"
    }
  )

  depends_on = [
    aws_eks_cluster.main
  ]
}

# -----------------------------------------------------------------------------
# 5. EKS Access Entries (DevOps Nexus Target Role Kubernetes Access)
# -----------------------------------------------------------------------------
resource "aws_eks_access_entry" "devops_nexus" {
  count         = var.enable_devops_nexus_access_entry ? 1 : 0
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = var.devops_nexus_role_arn
  type          = "STANDARD"

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-devops-nexus-access-entry"
    }
  )

  depends_on = [aws_eks_cluster.main]
}

# Attach AmazonEKSClusterAdminPolicy to grant full Kubernetes management to DevOps Nexus
resource "aws_eks_access_policy_association" "devops_nexus_cluster_admin" {
  count         = var.enable_devops_nexus_access_entry ? 1 : 0
  cluster_name  = aws_eks_cluster.main.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = var.devops_nexus_role_arn

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.devops_nexus]
}

# -----------------------------------------------------------------------------
# 6. EBS CSI Driver IRSA IAM Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "ebs_csi_driver" {
  count       = var.enable_ebs_csi_addon ? 1 : 0
  name        = "${var.cluster_name}-ebs-csi-driver-role"
  description = "IAM Role for Amazon EKS EBS CSI Driver via IRSA"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:kube-system:ebs-csi-controller-sa"
            "${replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-ebs-csi-driver-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "ebs_csi_driver_policy" {
  count      = var.enable_ebs_csi_addon ? 1 : 0
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.ebs_csi_driver[0].name
}

# -----------------------------------------------------------------------------
# 7. Core EKS Add-ons
# -----------------------------------------------------------------------------
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"

  tags = var.tags

  depends_on = [aws_eks_cluster.main]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"

  tags = var.tags

  depends_on = [aws_eks_cluster.main]
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"

  tags = var.tags

  depends_on = [
    aws_eks_node_group.main
  ]
}

resource "aws_eks_addon" "aws_ebs_csi_driver" {
  count                    = var.enable_ebs_csi_addon ? 1 : 0
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "aws-ebs-csi-driver"
  service_account_role_arn = aws_iam_role.ebs_csi_driver[0].arn

  tags = var.tags

  depends_on = [
    aws_eks_node_group.main,
    aws_iam_role_policy_attachment.ebs_csi_driver_policy
  ]
}
