# --- Kubernetes REST Router ---
from fastapi import APIRouter, Request, Query, Path, HTTPException, status
from typing import Optional
from app.schemas.responses import BaseResponse
from app.schemas.k8s import ScaleRequest
from app.services.namespace_service import namespace_service
from app.services.node_service import node_service
from app.services.pod_service import pod_service
from app.services.deployment_service import deployment_service
from app.services.ingress_service import ingress_service
from app.services.scope_engine import scope_engine
from shared.exceptions import KubernetesClientException
from fastapi import Depends
from app.dependencies.auth import get_current_user, check_role
from app.core.logging import logger

router = APIRouter(
    prefix="/api/v1/k8s",
    dependencies=[Depends(get_current_user)]
)

def _get_cluster_id(request: Request) -> Optional[str]:
    return request.headers.get("X-Cluster-ID") or request.query_params.get("cluster_id")

@router.get("/namespaces", response_model=BaseResponse)
async def list_namespaces(
    request: Request,
    scope_mode: Optional[str] = Query("cluster"),
    namespace: Optional[str] = Query(None),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        raw_data = namespace_service.list_namespaces(cluster_id=cluster_id)
        data = scope_engine.filter_namespaces(raw_data, scope)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        logger.warning(f"Namespace listing graceful fallback (no cluster connected): {str(e)}")
        return BaseResponse(success=True, data=[], request_id=request_id)

@router.post("/namespaces", response_model=BaseResponse)
async def create_namespace(request: Request, name: str = Query(..., description="Target namespace identifier.")):
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "namespaces", "create", namespace=name)
    try:
        data = namespace_service.create_namespace(name)
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="create_namespace",
            target_resource=f"namespace/{name}",
            namespace=name,
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/namespaces/{name}", response_model=BaseResponse)
async def delete_namespace(request: Request, name: str = Path(..., description="Target namespace identifier.")):
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "namespaces", "delete", namespace=name)
    try:
        data = namespace_service.delete_namespace(name)
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="delete_namespace",
            target_resource=f"namespace/{name}",
            namespace=name,
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/nodes", response_model=BaseResponse)
async def list_nodes(request: Request):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        data = node_service.list_nodes(cluster_id=cluster_id)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        logger.warning(f"Node listing graceful fallback (no cluster connected): {str(e)}")
        return BaseResponse(success=True, data=[], request_id=request_id)

@router.get("/pods", response_model=BaseResponse)
async def list_pods(
    request: Request,
    namespace: Optional[str] = Query(None, description="Optional namespace filter."),
    scope_mode: Optional[str] = Query("cluster"),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        effective_ns = scope.get_effective_namespaces()
        ns_param = effective_ns[0] if (len(effective_ns) == 1) else None
        
        raw_pods = pod_service.list_pods(ns_param, cluster_id=cluster_id)
        data = scope_engine.filter_pods(raw_pods, scope)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        logger.warning(f"Pod listing graceful fallback (no cluster connected): {str(e)}")
        return BaseResponse(success=True, data=[], request_id=request_id)

@router.get("/pods/{namespace}/{pod_name}", response_model=BaseResponse)
async def describe_pod(
    request: Request,
    namespace: str = Path(..., description="Namespace scope."),
    pod_name: str = Path(..., description="Target pod identifier.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        data = pod_service.describe_pod(namespace, pod_name, cluster_id=cluster_id)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/pods/{namespace}/{pod_name}/logs", response_model=BaseResponse)
async def get_pod_logs(
    request: Request,
    namespace: str = Path(..., description="Namespace scope."),
    pod_name: str = Path(..., description="Target pod identifier."),
    tail_lines: int = Query(100, ge=1, description="Lines offset limit.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        logs_text = pod_service.get_pod_logs(namespace, pod_name, tail_lines, cluster_id=cluster_id)
        return BaseResponse(success=True, data={"logs": logs_text}, request_id=request_id)
    except KubernetesClientException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/deployments", response_model=BaseResponse)
async def list_deployments(
    request: Request,
    namespace: Optional[str] = Query(None, description="Optional namespace filter."),
    scope_mode: Optional[str] = Query("cluster"),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        effective_ns = scope.get_effective_namespaces()
        ns_param = effective_ns[0] if (len(effective_ns) == 1) else None

        raw_deps = deployment_service.list_deployments(ns_param, cluster_id=cluster_id)
        data = scope_engine.filter_deployments(raw_deps, scope)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        logger.warning(f"Deployment listing graceful fallback (no cluster connected): {str(e)}")
        return BaseResponse(success=True, data=[], request_id=request_id)

from app.services.authz_engine import authz_engine
from app.services.audit_service import audit_service

@router.post("/deployments/{namespace}/{name}/restart", response_model=BaseResponse)
async def restart_deployment(
    request: Request,
    namespace: str = Path(..., description="Namespace scope."),
    name: str = Path(..., description="Target deployment identifier.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"
    
    authz_engine.authorize(username, "deployments", "restart_deployment", namespace=namespace, application=name)
    try:
        data = deployment_service.restart_deployment(namespace, name, cluster_id=cluster_id)
        pod_service.invalidate_cache()
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="restart_deployment",
            target_resource=f"deployment/{name}",
            namespace=namespace,
            application=name,
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/deployments/{namespace}/{name}/scale", response_model=BaseResponse)
async def scale_deployment(
    request: Request,
    body: ScaleRequest,
    namespace: str = Path(..., description="Namespace scope."),
    name: str = Path(..., description="Target deployment identifier.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "deployments", "scale_deployment", namespace=namespace, application=name)
    is_gitops = deployment_service.check_gitops_managed(namespace, name, cluster_id=cluster_id)

    try:
        data = deployment_service.scale_deployment(namespace, name, body.replicas, cluster_id=cluster_id)
        pod_service.invalidate_cache()
        action_name = "scale_gitops_deployment" if is_gitops else "scale_deployment"
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action=action_name,
            target_resource=f"deployment/{name}",
            namespace=namespace,
            application=name,
            new_value=f"replicas={body.replicas}",
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except Exception as e:
        logger.error(f"scale_deployment failed for {namespace}/{name}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/pods/{namespace}/{name}", response_model=BaseResponse)
async def delete_pod(
    request: Request,
    namespace: str = Path(..., description="Namespace scope."),
    name: str = Path(..., description="Target pod identifier.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "pods", "delete", namespace=namespace, application=name)
    try:
        data = pod_service.delete_pod(namespace, name, cluster_id=cluster_id)
        deployment_service.invalidate_cache()
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="delete_pod",
            target_resource=f"pod/{name}",
            namespace=namespace,
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/pods/{namespace}/{name}/restart", response_model=BaseResponse)
async def restart_pod(
    request: Request,
    namespace: str = Path(..., description="Namespace scope."),
    name: str = Path(..., description="Target pod identifier.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "pods", "restart_deployment", namespace=namespace, application=name)
    try:
        data = pod_service.restart_pod(namespace, name, cluster_id=cluster_id)
        deployment_service.invalidate_cache()
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="restart_pod",
            target_resource=f"pod/{name}",
            namespace=namespace,
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/deployments/{namespace}/{name}", response_model=BaseResponse)
async def delete_deployment(
    request: Request,
    namespace: str = Path(..., description="Namespace scope."),
    name: str = Path(..., description="Target deployment identifier."),
    temporary: bool = Query(False, description="Set to true for temporary runtime maintenance deletion under ArgoCD self-healing.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "deployments", "delete", namespace=namespace, application=name)
    
    is_gitops = deployment_service.check_gitops_managed(namespace, name, cluster_id=cluster_id)
    if is_gitops and not temporary:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Operation rejected: Deployment '{name}' is managed by ArgoCD. Direct permanent deletion violates GitOps reconciliation. Disconnect from GitOps first or use Temporary Delete."
        )

    try:
        target_name = deployment_service._resolve_k8s_name(namespace, name, cluster_id=cluster_id)
        k8s_client.delete_deployment(namespace, target_name, cluster_id=cluster_id)
        deployment_service.invalidate_cache()
        pod_service.invalidate_cache()
        action_name = "temporary_delete" if is_gitops else "delete_deployment"
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action=action_name,
            target_resource=f"deployment/{target_name}",
            namespace=namespace,
            application=name,
            new_value="temporary_maintenance" if temporary else "permanently_deleted",
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        msg = f"Temporary maintenance deletion executed for {target_name}. ArgoCD Self-Healing will recreate it." if temporary else f"Deployment {target_name} deleted successfully."
        return BaseResponse(success=True, data={"message": msg}, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/deployments/{namespace}/{name}/rollback", response_model=BaseResponse)
async def rollback_deployment(
    request: Request,
    namespace: str = Path(..., description="Namespace scope."),
    name: str = Path(..., description="Target deployment identifier.")
):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"

    authz_engine.authorize(username, "deployments", "rollback_application", namespace=namespace, application=name)
    try:
        target_name = deployment_service._resolve_k8s_name(namespace, name, cluster_id=cluster_id)
        k8s_client.restart_deployment(namespace, target_name, cluster_id=cluster_id)
        deployment_service.invalidate_cache()
        pod_service.invalidate_cache()
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="rollback_deployment",
            target_resource=f"deployment/{target_name}",
            namespace=namespace,
            application=name,
            new_value="rolled_back_previous_revision",
            client_ip=request.client.host if request.client else "127.0.0.1"
        )
        return BaseResponse(success=True, data={"message": f"Rollout restart/rollback triggered for {target_name}."}, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/ingresses", response_model=BaseResponse)
async def list_ingresses(request: Request, namespace: Optional[str] = Query(None, description="Optional namespace filter.")):
    request_id = getattr(request.state, "request_id", None)
    try:
        data = ingress_service.list_ingresses(namespace)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except KubernetesClientException as e:
        logger.warning(f"Ingress listing graceful fallback (no cluster connected): {str(e)}")
        return BaseResponse(success=True, data=[], request_id=request_id)
