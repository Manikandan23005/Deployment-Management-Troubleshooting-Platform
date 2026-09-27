# --- Deterministic GitOps Ownership Resolver ---
import os
from typing import Optional, Dict, Any, List
from app.core.logging import logger
from app.agent.gitops.models import GitOpsOwnership

class GitOpsOwnershipResolver:
    """Resolves whether a Kubernetes workload is GitOps-managed and maps its repository, Helm chart, and values files."""

    @staticmethod
    def get_repo_root() -> str:
        candidates = [
            "/repo",
            "/app/repo",
            os.environ.get("REPO_ROOT", ""),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
            os.getcwd(),
            "/app"
        ]
        for c in candidates:
            if c and os.path.exists(c) and (os.path.exists(os.path.join(c, "helm")) or os.path.exists(os.path.join(c, ".git"))):
                return c
        return "/repo" if os.path.exists("/repo") else os.getcwd()

    def __init__(self):
        pass

    @property
    def repo_root(self) -> str:
        return self.get_repo_root()

    def _resolve_clean_prefix(self, name: str) -> str:
        """Extracts clean service name prefix (e.g. 'auth-prod', 'auth-service' -> 'auth')."""
        return name.replace("-service", "").replace("-prod", "").replace("-dev", "").replace("-stage", "").replace("-qa", "").lower()

    def resolve_ownership(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> GitOpsOwnership:
        """Determines if target deployment is managed by ArgoCD and locates its Helm values file."""
        clean_prefix = self._resolve_clean_prefix(name)
        root = self.get_repo_root()
        helm_service_dir = os.path.join(root, "helm", clean_prefix)
        has_local_helm = os.path.exists(helm_service_dir) and os.path.isdir(helm_service_dir)

        # 1. Fetch active ArgoCD applications if available
        matched_app: Optional[Dict[str, Any]] = None
        if not has_local_helm or cluster_id:
            try:
                from app.services.argocd_service import argocd_service
                argocd_apps = argocd_service.list_applications(cluster_id=cluster_id)
                for app in argocd_apps:
                    app_name = app.get("name", "")
                    app_dest_ns = app.get("destination_namespace", "devops-nexus-prod")
                    clean_app = self._resolve_clean_prefix(app_name)
                    if (app_name == name or 
                        app_name == f"{clean_prefix}-prod" or 
                        app_name == f"{clean_prefix}-dev" or
                        clean_app == clean_prefix) and (namespace == app_dest_ns or not namespace or namespace == "devops-nexus-prod"):
                        matched_app = app
                        break
            except Exception as e:
                logger.debug(f"GitOpsOwnershipResolver: Could not fetch ArgoCD apps: {str(e)}")

        if not matched_app and not has_local_helm:
            return GitOpsOwnership(
                is_gitops=False,
                target_name=name,
                namespace=namespace,
                cluster_id=cluster_id
            )

        app_identifier = matched_app.get("name") if matched_app else f"{clean_prefix}-prod"
        repo_url = (matched_app.get("repo_url") if matched_app else None) or "https://github.com/Manikandan23005/Deployment-Management-Troubleshooting-Platform"
        branch = (matched_app.get("targetRevision") if matched_app else "main") or "main"

        # Determine target Helm values file
        candidate_values = ["values-prod.yaml", "values.yaml", "values-dev.yaml", "values-stage.yaml", "values-qa.yaml"]
        resolved_values_file: Optional[str] = None
        available_files: List[str] = []

        if has_local_helm:
            for vf in candidate_values:
                candidate_path = os.path.join(helm_service_dir, vf)
                if os.path.exists(candidate_path):
                    available_files.append(vf)
                    if not resolved_values_file:
                        resolved_values_file = candidate_path

        return GitOpsOwnership(
            is_gitops=True,
            target_name=name,
            namespace=namespace,
            argocd_app_name=app_identifier,
            repo_url=repo_url,
            branch=branch,
            helm_chart_path=f"helm/{clean_prefix}",
            values_files=available_files,
            target_values_file=resolved_values_file,
            cluster_id=cluster_id
        )

gitops_ownership_resolver = GitOpsOwnershipResolver()
