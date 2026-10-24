#!/bin/bash
set -e

# =============================================================================
# Multi-Cluster Application Deployment Script for DevOps Nexus
# =============================================================================
# Deploys the complete 8-microservice stack to devops-nexus-dev,
# devops-nexus-qa, and devops-nexus-stage using Helm.

ENVIRONMENTS=("dev" "qa" "stage")
SERVICES=("auth" "users" "products" "orders" "payment" "notification" "gateway" "frontend")
REGION="ap-south-1"

echo "=========================================================="
echo "Starting multi-cluster application rollout across environments..."
echo "Environments: ${ENVIRONMENTS[*]}"
echo "Services:     ${SERVICES[*]}"
echo "Region:       ${REGION}"
echo "=========================================================="

for env in "${ENVIRONMENTS[@]}"; do
  CLUSTER_NAME="devops-nexus-${env}"
  NAMESPACE="devops-nexus-${env}"

  echo ""
  echo ">>> [Cluster: $CLUSTER_NAME | Namespace: $NAMESPACE]"
  echo "Updating kubeconfig..."
  aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME"

  echo "Creating namespace $NAMESPACE if not exists..."
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

  for svc in "${SERVICES[@]}"; do
    echo "  -> Deploying $svc (values-${env}.yaml)..."
    helm upgrade --install "$svc" "helm/$svc" \
      --namespace "$NAMESPACE" \
      --values "helm/$svc/values-${env}.yaml" \
      --wait=false
  done

  echo "✅ Applications submitted for $CLUSTER_NAME"
done

echo ""
echo "=========================================================="
echo "🎉 Multi-cluster application rollout initiated successfully!"
echo "=========================================================="
