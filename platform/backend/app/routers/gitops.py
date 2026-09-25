# --- GitOps REST Router ---
from fastapi import APIRouter, Request, Query, Path, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.schemas.responses import BaseResponse
from app.services.gitops_service import gitops_service
from app.services.argocd_service import argocd_service
from shared.exceptions import DevOpsNexusException
from fastapi import Depends
from app.dependencies.auth import get_current_user, check_role

router = APIRouter(
    prefix="/api/v1/gitops",
    dependencies=[Depends(get_current_user)]
)

@router.get("/github/workflows", response_model=BaseResponse)
async def get_github_workflows(
    request: Request,
    owner: str = Query("Manikandan23005", description="Repository owner."),
    repo: str = Query("Microservice-Deployment-Monitoring-Platform", description="Repository name.")
):
    """Fetches GitHub Action CI/CD workflow runs."""
    request_id = getattr(request.state, "request_id", None)
    try:
        data = gitops_service.get_workflows_status(owner, repo)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/github/repo-details", response_model=BaseResponse)
async def get_github_repo_details(
    request: Request,
    owner: str = Query("Manikandan23005", description="Repository owner."),
    repo: str = Query("Microservice-Deployment-Monitoring-Platform", description="Repository name.")
):
    """Retrieves branches and latest commits from GitHub."""
    request_id = getattr(request.state, "request_id", None)
    try:
        data = gitops_service.get_repository_details(owner, repo)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

def _get_cluster_id(request: Request) -> Optional[str]:
    return request.headers.get("X-Cluster-ID") or request.query_params.get("cluster_id")

from app.services.scope_engine import scope_engine

@router.get("/argocd/applications", response_model=BaseResponse)
async def list_argocd_applications(
    request: Request,
    scope_mode: Optional[str] = Query("cluster"),
    namespace: Optional[str] = Query(None),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    """Lists applications synchronizations status registered in ArgoCD."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        raw_apps = argocd_service.list_applications(cluster_id=cluster_id)
        data = scope_engine.filter_argocd_apps(raw_apps, scope)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

from app.services.authz_engine import authz_engine
from app.services.audit_service import audit_service

@router.post("/argocd/applications/{app_name}/sync", response_model=BaseResponse)
async def sync_argocd_application(
    request: Request,
    app_name: str = Path(..., description="Target application name.")
):
    """Triggers sync deployment inside ArgoCD."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"
    
    authz_engine.authorize(username, "gitops", "sync_application", application=app_name)
    try:
        data = argocd_service.sync_application(app_name, cluster_id=cluster_id)
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="sync_application",
            target_resource=f"argocd/{app_name}",
            application=app_name,
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/argocd/applications/{app_name}/refresh", response_model=BaseResponse)
async def refresh_argocd_application(
    request: Request,
    app_name: str = Path(..., description="Target application name.")
):
    """Triggers refresh manifests check in ArgoCD."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        data = argocd_service.refresh_application(app_name, cluster_id=cluster_id)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/argocd/applications/{app_name}/rollback", response_model=BaseResponse)
async def rollback_argocd_application(
    request: Request,
    app_name: str = Path(..., description="Target application name."),
    revision: int = Query(..., ge=1, description="Target historical revision index.")
):
    """Triggers application rollback to a specified deployment revision."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "gitops", "rollback_application", application=app_name)
    try:
        data = argocd_service.rollback_application(app_name, revision, cluster_id=cluster_id)
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="rollback_application",
            target_resource=f"argocd/{app_name}",
            application=app_name,
            new_value=f"revision={revision}",
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/argocd/applications/{app_name}/history", response_model=BaseResponse)
async def get_argocd_application_history(
    request: Request,
    app_name: str = Path(..., description="Target application name.")
):
    """Retrieves list of deploy records and revisions tags from ArgoCD."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        data = argocd_service.get_application_history(app_name, cluster_id=cluster_id)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/argocd/applications/{app_name}/disconnect", response_model=BaseResponse)
async def disconnect_argocd_application(
    request: Request,
    app_name: str = Path(..., description="Target application name to disconnect from GitOps.")
):
    """Safely disconnects an ArgoCD application by removing tracking CRD without deleting live workloads."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username", "viewer")

    # Requires Administrator role for GitOps disconnection
    authz_engine.authorize(username, "gitops", "disconnect_gitops", application=app_name)
    try:
        data = argocd_service.delete_application(app_name, cascade=False, cluster_id=cluster_id)
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="disconnect_gitops",
            target_resource=f"argocd/{app_name}",
            application=app_name,
            new_value="gitops_disconnected",
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

class ReconnectRequest(BaseModel):
    mode: str = "restore"
    namespace: Optional[str] = "devops-nexus-prod"

@router.post("/argocd/applications/{app_name}/reconnect", response_model=BaseResponse)
async def reconnect_argocd_application(
    request: Request,
    body: ReconnectRequest,
    app_name: str = Path(..., description="Target application name to reconnect to GitOps.")
):
    """Reconnects a Kubernetes deployment back to ArgoCD GitOps management under adopt or restore mode."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    # Authorized for DevOps Engineer and Administrator roles
    authz_engine.authorize(username, "gitops", "reconnect_gitops", application=app_name)
    try:
        data = argocd_service.reconnect_application(
            app_name=app_name,
            mode=body.mode,
            namespace=body.namespace or "devops-nexus-prod",
            cluster_id=cluster_id
        )
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="reconnect_gitops",
            target_resource=f"argocd/{app_name}",
            application=app_name,
            new_value=f"mode={body.mode}",
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
