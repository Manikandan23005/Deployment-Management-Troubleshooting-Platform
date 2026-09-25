# --- Deterministic Target & Environment Resolver ---
import re
from typing import Dict, Any, Optional, List
# pyrefly: ignore [missing-import]
from app.core.logging import logger

class TargetResolver:
    """Resolves operational target, environment (On-Premises Kubernetes vs Amazon EKS), 
    AWS account, cluster, namespace, application, and resource parameters deterministically."""

    KNOWN_WORKLOADS = ["auth-service", "payment-service", "gateway", "frontend", "orders-service", "users-service", "products-service"]

    def resolve_target(
        self,
        prompt: str,
        resource_name: Optional[str] = None,
        namespace: Optional[str] = None,
        cluster_id: Optional[str] = None,
        scope: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Resolves target environment, AWS account, cluster, namespace, application, and resource details."""
        
        p = prompt.lower().strip()
        
        # 1. Environment & Cluster Resolution
        cid = cluster_id or (getattr(scope, "cluster_id", None) if scope else None) or "default"
        scope_env = getattr(scope, "environment", None) if scope else None
        
        is_eks = ("eks" in p or 
                  "aws" in p or 
                  "eks" in cid.lower() or 
                  "aws" in cid.lower() or 
                  scope_env in ["AWS_EKS", "Amazon EKS"])

        environment = "AWS_EKS" if is_eks else "KUBERNETES"
        env_label = "Amazon EKS" if is_eks else "On-Premises Kubernetes"

        aws_account_id = getattr(scope, "aws_account_id", None) if scope else None
        aws_account_name = getattr(scope, "aws_account_name", None) if scope else None
        aws_region = getattr(scope, "region", None) if scope else None

        # Try to correlate with registered AWS Accounts if EKS is requested
        if is_eks and not aws_account_id:
            try:
                # pyrefly: ignore [missing-import]
                from app.aws.account_registry import aws_account_registry
                registered_accs = aws_account_registry.list_accounts()
                if registered_accs:
                    for acc in registered_accs:
                        if acc.name.lower() in p or acc.account_id in p:
                            aws_account_id = acc.account_id
                            aws_account_name = acc.name
                            aws_region = acc.default_region
                            break
                    if not aws_account_id:
                        # Default to primary registered account
                        aws_account_id = registered_accs[0].account_id
                        aws_account_name = registered_accs[0].name
                        aws_region = registered_accs[0].default_region
            except Exception:
                pass

        # 2. Namespace Resolution
        active_ns = namespace
        if not active_ns and scope:
            active_ns = getattr(scope, "namespace", None)
        if not active_ns or active_ns == "all":
            active_ns = "devops-nexus-prod"

        # 3. Application / Resource Name Resolution
        target_app = resource_name
        if not target_app and scope and getattr(scope, "application", None):
            target_app = scope.application

        # Extract workload from prompt if not explicitly passed
        if not target_app or target_app.lower() in ["all", "none"]:
            for known in self.KNOWN_WORKLOADS:
                clean_known = known.replace("-service", "")
                if known in p or clean_known in p:
                    target_app = known
                    break

        # Fallback keyword matching from prompt regex
        if not target_app or target_app.lower() in ["all", "none"]:
            match = re.search(r'\b([a-z0-9-]+-(?:service|app|api|db))\b', p)
            if match:
                target_app = match.group(1)

        # 4. Kind Resolution
        kind = "deployment"
        if "pod" in p and "deployment" not in p:
            kind = "pod"
        elif "node" in p:
            kind = "node"
        elif "argocd" in p or "gitops" in p:
            kind = "argocd_app"
        elif "service" in p and "deployment" not in p and "-service" not in p:
            kind = "service"
        elif "configmap" in p:
            kind = "configmap"
        elif "secret" in p:
            kind = "secret"

        # 5. Ambiguity & Clarification Need Resolution
        needs_clarification = False
        clarification_message = ""
        
        # If user requests mutation (restart/scale/rollback/delete) without specifying target app
        mutation_requested = any(m in p for m in ["scale", "restart", "rollback", "delete", "remove", "fix"])
        if mutation_requested and not target_app:
            needs_clarification = True
            clarification_message = f"Multiple workloads exist in namespace '{active_ns}'. Please specify target application (e.g. 'auth-service', 'payment-service', 'gateway')."

        resolved = {
            "environment": env_label,
            "environment_type": environment,
            "cluster_id": cid,
            "cluster": cid,
            "namespace": active_ns,
            "application": target_app or "auth-service",
            "resource_kind": kind,
            "resource_name": target_app or "auth-service",
            "aws_account_id": aws_account_id,
            "aws_account_name": aws_account_name,
            "region": aws_region,
            "needs_clarification": needs_clarification,
            "clarification_message": clarification_message,
            "is_ambiguous": target_app is None
        }

        logger.debug(f"TargetResolver resolved: env={env_label} ({environment}), cluster={cid}, ns={active_ns}, app={target_app}, aws_acc={aws_account_id}")
        return resolved

target_resolver = TargetResolver()
