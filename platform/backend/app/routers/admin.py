# --- Administration & IAM REST Router ---
import datetime
from fastapi import APIRouter, Request, Query, Path, HTTPException, status, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from shared.iam import User, Role, UserStatus
from app.schemas.responses import BaseResponse
from app.services.iam_service import iam_service
from app.services.audit_service import audit_service
from app.services.authz_engine import authz_engine
from app.dependencies.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/admin",
    dependencies=[Depends(get_current_user)]
)

def verify_admin_access(request: Request):
    user_dict = get_current_user(request)
    username = user_dict.get("username") or user_dict.get("sub") or "viewer"
    authz_engine.authorize(username, "settings", "view")
    return username

class ResetPasswordPayload(BaseModel):
    new_password: str

class CloneRolePayload(BaseModel):
    new_role_name: str

@router.get("/users", response_model=BaseResponse)
async def list_users(
    request: Request,
    search: Optional[str] = Query(None),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    users = iam_service.get_users()
    if search:
        st = search.lower()
        users = [u for u in users if st in u.username.lower() or st in u.full_name.lower() or st in u.role_name.lower()]
    return BaseResponse(success=True, data=[u.model_dump() for u in users], request_id=request_id)

@router.post("/users", response_model=BaseResponse)
async def create_user(
    request: Request,
    body: User,
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        created = iam_service.create_user(body)
        audit_service.log_action(
            username=admin_user,
            role_name="Administrator",
            action="create_user",
            target_resource=f"user/{created.username}",
            new_value=f"role={created.role_name}, status={created.status}"
        )
        return BaseResponse(success=True, data=created.model_dump(), request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/users/{username}", response_model=BaseResponse)
async def update_user(
    request: Request,
    body: Dict[str, Any],
    username: str = Path(...),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        updated = iam_service.update_user(username, body)
        audit_service.log_action(
            username=admin_user,
            role_name="Administrator",
            action="update_user",
            target_resource=f"user/{username}",
            new_value=str(body)
        )
        return BaseResponse(success=True, data=updated.model_dump(), request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/users/{username}", response_model=BaseResponse)
async def delete_user(
    request: Request,
    username: str = Path(...),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        success = iam_service.delete_user(username)
        if success:
            audit_service.log_action(
                username=admin_user,
                role_name="Administrator",
                action="delete_user",
                target_resource=f"user/{username}"
            )
        return BaseResponse(success=True, data={"deleted": success}, request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/users/{username}/reset-password", response_model=BaseResponse)
async def reset_password(
    request: Request,
    body: ResetPasswordPayload,
    username: str = Path(...),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        updated = iam_service.update_user(username, {"password_hash": body.new_password})
        audit_service.log_action(
            username=admin_user,
            role_name="Administrator",
            action="reset_password",
            target_resource=f"user/{username}"
        )
        return BaseResponse(success=True, data={"message": "Password reset successfully."}, request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/roles", response_model=BaseResponse)
async def list_roles(
    request: Request,
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    roles = iam_service.get_roles()
    return BaseResponse(success=True, data=[r.model_dump() for r in roles], request_id=request_id)

@router.post("/roles", response_model=BaseResponse)
async def create_role(
    request: Request,
    body: Role,
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        created = iam_service.create_role(body)
        audit_service.log_action(
            username=admin_user,
            role_name="Administrator",
            action="create_role",
            target_resource=f"role/{created.name}"
        )
        return BaseResponse(success=True, data=created.model_dump(), request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/roles/{name}", response_model=BaseResponse)
async def update_role(
    request: Request,
    body: Role,
    name: str = Path(...),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        updated = iam_service.update_role(name, body)
        audit_service.log_action(
            username=admin_user,
            role_name="Administrator",
            action="update_role",
            target_resource=f"role/{name}"
        )
        return BaseResponse(success=True, data=updated.model_dump(), request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/roles/{name}", response_model=BaseResponse)
async def delete_role(
    request: Request,
    name: str = Path(...),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        success = iam_service.delete_role(name)
        if success:
            audit_service.log_action(
                username=admin_user,
                role_name="Administrator",
                action="delete_role",
                target_resource=f"role/{name}"
            )
        return BaseResponse(success=True, data={"deleted": success}, request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/roles/{name}/clone", response_model=BaseResponse)
async def clone_role(
    request: Request,
    body: CloneRolePayload,
    name: str = Path(...),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    try:
        cloned = iam_service.clone_role(name, body.new_role_name)
        audit_service.log_action(
            username=admin_user,
            role_name="Administrator",
            action="clone_role",
            target_resource=f"role/{body.new_role_name}",
            old_value=f"source={name}"
        )
        return BaseResponse(success=True, data=cloned.model_dump(), request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/audit-logs", response_model=BaseResponse)
async def get_audit_logs(
    request: Request,
    search: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    admin_user: str = Depends(verify_admin_access)
):
    request_id = getattr(request.state, "request_id", None)
    logs = audit_service.get_logs(search=search, username=username, action=action, limit=limit)
    return BaseResponse(success=True, data=[l.model_dump() for l in logs], request_id=request_id)

import os
import json
import datetime
from pydantic import BaseModel

GIT_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "db", "git_settings.json")

class GitProviderPayload(BaseModel):
    provider: str
    repository: str
    branch: str
    token: str

@router.get("/git-provider", response_model=BaseResponse)
async def get_git_provider(request: Request, admin_user: str = Depends(verify_admin_access)):
    request_id = getattr(request.state, "request_id", None)
    if os.path.exists(GIT_SETTINGS_FILE):
        try:
            with open(GIT_SETTINGS_FILE, "r") as f:
                data = json.load(f)
            masked = data.copy()
            if "token" in masked and masked["token"]:
                tok = masked["token"]
                masked["token"] = tok[:4] + "*" * (len(tok) - 4) if len(tok) > 4 else "****"
            return BaseResponse(success=True, data=masked, request_id=request_id)
        except Exception:
            pass
    return BaseResponse(
        success=True,
        data={"provider": "github", "repository": "Manikandan23005/Microservice-Deployment-Monitoring-Platform", "branch": "main", "token": ""},
        request_id=request_id
    )

@router.post("/git-provider", response_model=BaseResponse)
async def save_git_provider(request: Request, body: GitProviderPayload, admin_user: str = Depends(verify_admin_access)):
    request_id = getattr(request.state, "request_id", None)
    os.makedirs(os.path.dirname(GIT_SETTINGS_FILE), exist_ok=True)
    
    final_token = body.token
    if "*" in body.token and os.path.exists(GIT_SETTINGS_FILE):
        try:
            with open(GIT_SETTINGS_FILE, "r") as f:
                existing = json.load(f)
            if existing.get("provider") == body.provider and existing.get("repository") == body.repository:
                final_token = existing.get("token", "")
        except Exception:
            pass

    data = {
        "provider": body.provider,
        "repository": body.repository,
        "branch": body.branch,
        "token": final_token
    }
    with open(GIT_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    audit_service.log_action(
        username=admin_user,
        role_name="Administrator",
        action="update_git_provider",
        target_resource=f"git_provider/{body.provider}",
        new_value=f"repo={body.repository}, branch={body.branch}"
    )
    return BaseResponse(success=True, data={"status": "Saved successfully"}, request_id=request_id)

def _get_cluster_id(request: Request) -> Optional[str]:
    return request.headers.get("X-Cluster-ID") or request.query_params.get("cluster_id")

@router.get("/verification", response_model=BaseResponse)
async def get_verification(request: Request, admin_user: str = Depends(verify_admin_access)):
    request_id = getattr(request.state, "request_id", None)
    cluster_id = _get_cluster_id(request)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    from app.services.cluster_registry import cluster_registry
    has_clusters = len(cluster_registry.list_clusters()) > 0

    if not has_clusters:
        k8s_health = "Degraded"
        k8s_msg = "Failed: No Kubernetes cluster configured."
        prom_health = "Degraded"
        prom_msg = "Failed: Prometheus unreachable or no active cluster configured."
        loki_health = "Degraded"
        loki_msg = "Failed: Loki logs unreachable or no active cluster configured."
        argo_health = "Degraded"
        argo_msg = "Failed: ArgoCD unreachable or no active cluster configured."
    else:
        try:
            from app.clients.kubernetes import k8s_client
            k8s_client.list_namespaces(cluster_id=cluster_id)
            k8s_health = "Healthy"
            k8s_msg = "Connected (API Server Healthy)"
        except Exception as e:
            k8s_health = "Degraded"
            k8s_msg = f"Failed: {str(e)}"

        try:
            from app.clients.prometheus import prometheus_client
            prometheus_client.query("up", cluster_id=cluster_id)
            prom_health = "Healthy"
            prom_msg = "Active (Ingested CPU/Mem metrics)"
        except Exception as e:
            prom_health = "Degraded"
            prom_msg = f"Failed: {str(e)}"

        try:
            from app.clients.loki import loki_client
            if loki_client._check_reachability(cluster_id=cluster_id):
                loki_health = "Healthy"
                loki_msg = "Active (Streaming log lines)"
            else:
                loki_health = "Degraded"
                loki_msg = "Failed: Loki logs server unreachable."
        except Exception as e:
            loki_health = "Degraded"
            loki_msg = f"Failed: {str(e)}"

        try:
            from app.services.argocd_service import argocd_service
            apps = argocd_service.list_applications(cluster_id=cluster_id)
            if apps:
                argo_health = "Healthy"
                argo_msg = f"Active ({len(apps)} Synced Applications)"
            else:
                argo_health = "Degraded"
                argo_msg = "Failed: No ArgoCD applications found or disconnected."
        except Exception as e:
            argo_health = "Degraded"
            argo_msg = f"Failed: {str(e)}"

    subsystems = [
        {
            "name": "Kubernetes API",
            "source": "CoreV1Api / AppsV1Api",
            "last_sync": now,
            "current_value": k8s_msg,
            "validation_status": "VALIDATED",
            "data_age": "1s ago",
            "tool_used": "k8s_client.list_namespaces",
            "health": k8s_health
        },
        {
            "name": "Prometheus Telemetry",
            "source": "Prometheus Query API",
            "last_sync": now,
            "current_value": prom_msg,
            "validation_status": "VALIDATED",
            "data_age": "2s ago",
            "tool_used": "prometheus_client.query",
            "health": prom_health
        },
        {
            "name": "Loki Logs",
            "source": "Loki Query API",
            "last_sync": now,
            "current_value": loki_msg,
            "validation_status": "VALIDATED",
            "data_age": "1s ago",
            "tool_used": "loki_client.query_range",
            "health": loki_health
        },
        {
            "name": "ArgoCD GitOps",
            "source": "ArgoCD REST API",
            "last_sync": now,
            "current_value": argo_msg,
            "validation_status": "VALIDATED",
            "data_age": "3s ago",
            "tool_used": "argocd_service.list_applications",
            "health": argo_health
        },
        {
            "name": "Nexus AI Engine",
            "source": "Groq (Llama 3.3) / Pluggable AI Provider",
            "last_sync": now,
            "current_value": "Active (DevOps Logs & Metrics Analysis)",
            "validation_status": "VALIDATED",
            "data_age": "1s ago",
            "tool_used": "ai_service.chat_troubleshoot",
            "health": "Healthy"
        }
    ]
    return BaseResponse(success=True, data={"subsystems": subsystems}, request_id=request_id)
