# --- Strongly-Typed ArgoCD GitOps Tools ---
from typing import Dict, Any, List
from app.clients.argocd import argocd_client
from app.services.argocd_service import argocd_service
from app.agent.risk_policy import RiskLevel
from app.agent.tools.models import (
    ToolDefinition, ToolCategory, OperationType,
    ArgoCDListAppsInput, ArgoCDGetAppInput, ArgoCDRefreshAppInput, ArgoCDSyncAppInput
)

def handle_argocd_list_apps(params: ArgoCDListAppsInput) -> List[Dict[str, Any]]:
    return argocd_service.list_applications(cluster_id=params.cluster_id)

def handle_argocd_get_app(params: ArgoCDGetAppInput) -> Dict[str, Any]:
    return argocd_service.get_application_details(app_name=params.name, cluster_id=params.cluster_id)

def handle_argocd_refresh_app(params: ArgoCDRefreshAppInput) -> Dict[str, Any]:
    return argocd_client.refresh_application(app_name=params.name, cluster_id=params.cluster_id)

def handle_argocd_sync_app(params: ArgoCDSyncAppInput) -> Dict[str, Any]:
    return argocd_service.sync_application(app_name=params.name, cluster_id=params.cluster_id)

ARGOCD_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="argocd.list_applications",
        description="Lists all registered ArgoCD GitOps applications and sync/health states.",
        category=ToolCategory.ARGOCD,
        provider="argocd",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="gitops:view",
        requires_confirmation=False,
        input_schema=ArgoCDListAppsInput,
        handler=handle_argocd_list_apps
    ),
    ToolDefinition(
        name="argocd.get_application",
        description="Retrieves detailed manifest tree, sync history, and revision info for an ArgoCD application.",
        category=ToolCategory.ARGOCD,
        provider="argocd",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="gitops:view",
        requires_confirmation=False,
        input_schema=ArgoCDGetAppInput,
        handler=handle_argocd_get_app
    ),
    ToolDefinition(
        name="argocd.refresh_application",
        description="Triggers an immediate Git repository poll to refresh ArgoCD live state against target Git commit.",
        category=ToolCategory.ARGOCD,
        provider="argocd",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.LOW,
        required_permission="gitops:view",
        requires_confirmation=False,
        input_schema=ArgoCDRefreshAppInput,
        handler=handle_argocd_refresh_app
    ),
    ToolDefinition(
        name="argocd.sync_application",
        description="Synchronizes live Kubernetes infrastructure to match the desired state declared in Git.",
        category=ToolCategory.ARGOCD,
        provider="argocd",
        operation_type=OperationType.MUTATE,
        risk_level=RiskLevel.MEDIUM,
        required_permission="gitops:sync_application",
        requires_confirmation=False,
        input_schema=ArgoCDSyncAppInput,
        handler=handle_argocd_sync_app
    )
]
