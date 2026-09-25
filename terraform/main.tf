# -----------------------------------------------------------------------------
# 1. Multi-AZ VPC & Subnet Networking
# -----------------------------------------------------------------------------
module "networking" {
  source = "./modules/networking"

  vpc_cidr                  = var.vpc_cidr
  availability_zones        = var.availability_zones
  public_subnet_cidrs       = var.public_subnet_cidrs
  private_subnet_cidrs      = var.private_subnet_cidrs
  cluster_name              = var.cluster_name
  enable_single_nat_gateway = var.enable_single_nat_gateway
  tags                      = var.tags
}

# -----------------------------------------------------------------------------
# 2. IAM Roles & Least-Privilege Policies
# -----------------------------------------------------------------------------
module "iam" {
  source = "./modules/iam"

  cluster_name           = var.cluster_name
  trusted_principal_arns = []
  tags                   = var.tags
}

# -----------------------------------------------------------------------------
# 3. Amazon EKS Cluster, Node Groups & Add-ons
# -----------------------------------------------------------------------------
module "eks" {
  source = "./modules/eks"

  cluster_name                         = var.cluster_name
  kubernetes_version                   = var.kubernetes_version
  vpc_id                               = module.networking.vpc_id
  subnet_ids                           = concat(module.networking.public_subnet_ids, module.networking.private_subnet_ids)
  private_subnet_ids                   = module.networking.private_subnet_ids
  cluster_role_arn                     = module.iam.eks_cluster_role_arn
  node_role_arn                        = module.iam.eks_node_role_arn
  devops_nexus_role_arn                = module.iam.devops_nexus_access_role_arn
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  node_instance_types                  = var.node_instance_types
  node_capacity_type                   = var.node_capacity_type
  ami_type                             = var.ami_type
  desired_size                         = var.desired_size
  min_size                             = var.min_size
  max_size                             = var.max_size
  tags                                 = var.tags

  depends_on = [
    module.networking,
    module.iam
  ]
}
