# --- Tool-Level RBAC & Authorization Engine ---
from typing import Dict, Any, Optional
from app.services.authz_engine import authz_engine, AuthorizationException
from app.core.logging import logger

class ToolPermissionManager:
    """Enforces fine-grained, tool-level RBAC authorization before tool execution."""

    # Map tool categories and operations to IAM resource:action
    TOOL_PERMISSION_MAP = {
        # Kubernetes Read Tools
        "k8s.list_namespaces": ("namespaces", "view"),
        "k8s.list_pods": ("pods", "view"),
        "k8s.get_pod": ("pods", "view"),
        "k8s.get_pod_logs": ("logs", "view"),
        "k8s.list_deployments": ("deployments", "view"),
        "k8s.get_deployment": ("deployments", "view"),
        "k8s.list_services": ("services", "view"),
        "k8s.get_service": ("services", "view"),
        "k8s.list_nodes": ("nodes", "view"),
        "k8s.get_node": ("nodes", "view"),
        "k8s.list_events": ("events", "view"),

        # Kubernetes Mutating Tools
        "k8s.scale_deployment": ("deployments", "scale_deployment"),
        "k8s.restart_deployment": ("deployments", "restart_deployment"),
        "k8s.delete_pod": ("pods", "delete"),
        "k8s.delete_deployment": ("deployments", "delete"),

        # Prometheus Tools
        "prometheus.query": ("metrics", "view"),
        "prometheus.query_range": ("metrics", "view"),
        "prometheus.cluster_metrics": ("metrics", "view"),

        # Loki Tools
        "loki.query": ("logs", "view"),
        "loki.query_range": ("logs", "view"),
        "loki.search_errors": ("logs", "view"),

        # ArgoCD Tools
        "argocd.list_applications": ("gitops", "view"),
        "argocd.get_application": ("gitops", "view"),
        "argocd.refresh_application": ("gitops", "view"),
        "argocd.sync_application": ("gitops", "sync_application"),

        # Git Tools
        "git.get_repository": ("gitops", "view"),
        "git.get_branch": ("gitops", "view"),
        "git.get_commit": ("gitops", "view"),
        "git.update_file": ("gitops", "update"),
        "git.commit": ("gitops", "update"),
        "git.push": ("gitops", "update"),
    }

    def check_tool_permission(
        self,
        tool_name: str,
        user_info: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        application: Optional[str] = None
    ) -> bool:
        """
        Validates if the user has RBAC permissions to execute the specified tool.
        Raises AuthorizationException if permission is denied.
        """
        user_info = user_info or {}
        username = user_info.get("username") or user_info.get("sub") or "viewer"

        resource, action = self.TOOL_PERMISSION_MAP.get(tool_name, ("ai", "ai_chat"))

        try:
            authz_engine.authorize(
                username=username,
                resource=resource,
                action=action,
                namespace=namespace,
                application=application
            )
            return True
        except AuthorizationException as e:
            logger.warning(f"Tool RBAC Denied: User '{username}' attempted '{tool_name}' ({resource}:{action}) - {e.detail}")
            raise e

tool_permission_manager = ToolPermissionManager()
