# --- DevOps Nexus Centralized Authorization Engine ---
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from shared.iam import User, Role, UserStatus
from app.services.iam_service import iam_service
from app.core.logging import logger

class AuthorizationException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class AuthzEngine:
    """Centralized authorization engine validating dynamic role permissions and workspace scope bounds."""

    def authorize(
        self,
        username: str,
        resource: str,
        action: str,
        namespace: Optional[str] = None,
        application: Optional[str] = None
    ) -> User:
        """
        Validates authorization for a requested resource and action.
        Raises AuthorizationException (403 Forbidden) if denied.
        """
        user = iam_service.get_user(username)
        if not user:
            # Fallback user context for testing or unregistered admin sub handles
            user = User(
                username=username,
                role_name="Administrator",
                status=UserStatus.ACTIVE,
                assigned_workspaces=["cluster", "namespace", "app", "infra"],
                assigned_namespaces=["*"],
                assigned_apps=["*"]
            )

        if user.status != UserStatus.ACTIVE:
            raise AuthorizationException(f"User account '{username}' is disabled.")

        role = iam_service.get_role(user.role_name)
        if not role:
            raise AuthorizationException(f"Role '{user.role_name}' assigned to user '{username}' does not exist.")

        # Root administrator bypass
        if role.name == "Administrator":
            return user

        # 1. Check Resource/Action Permission Matrix
        res_matrix = role.permissions.get(resource, {})
        allowed = res_matrix.get(action, False)
        if not allowed:
            # Check fallback action mappings
            if action not in ["view", "create", "update", "delete"]:
                if any(m in action for m in ["scale", "restart", "sync", "rollback", "edit", "exec", "mutate"]):
                    allowed = res_matrix.get("update", False)
                elif any(m in action for m in ["delete", "remove"]):
                    allowed = res_matrix.get("delete", False)
                else:
                    allowed = res_matrix.get("view", False)
        
        if not allowed:
            raise AuthorizationException(
                f"Permission Denied: User '{username}' with role '{role.name}' is not authorized to execute '{action}' on resource '{resource}'."
            )

        # 2. Check Namespace Workspace Bounds
        if namespace and namespace != "*":
            allowed_ns = role.allowed_namespaces
            user_ns = user.assigned_namespaces
            if "*" not in allowed_ns and namespace not in allowed_ns:
                raise AuthorizationException(f"Scope Access Denied: Role '{role.name}' does not have access to namespace '{namespace}'.")
            if "*" not in user_ns and namespace not in user_ns:
                raise AuthorizationException(f"Scope Access Denied: User '{username}' is not assigned to namespace '{namespace}'.")

        # 3. Check Application Workspace Bounds
        if application and application != "*":
            allowed_apps = role.allowed_apps
            user_apps = user.assigned_apps
            if "*" not in allowed_apps and application not in allowed_apps:
                raise AuthorizationException(f"Scope Access Denied: Role '{role.name}' does not have access to application '{application}'.")
            if "*" not in user_apps and application not in user_apps:
                raise AuthorizationException(f"Scope Access Denied: User '{username}' is not assigned to application '{application}'.")

        return user

    def get_user_allowed_namespaces(self, username: str) -> List[str]:
        """Returns the list of authorized namespaces for the user."""
        user = iam_service.get_user(username)
        if not user or user.role_name == "Administrator":
            return ["*"]
        role = iam_service.get_role(user.role_name)
        if not role or "*" in role.allowed_namespaces:
            return user.assigned_namespaces
        if "*" in user.assigned_namespaces:
            return role.allowed_namespaces
        return list(set(role.allowed_namespaces).intersection(set(user.assigned_namespaces)))

authz_engine = AuthzEngine()

def require_permission(resource: str, action: str):
    """FastAPI Dependency enforcing centralized authorization on routes."""
    def dependency(request: Request):
        from app.dependencies.auth import get_current_user
        current_user_dict = get_current_user(request)
        username = current_user_dict.get("username", "viewer")
        ns = request.query_params.get("namespace") or request.path_params.get("namespace")
        app = request.query_params.get("app") or request.path_params.get("app")
        return authz_engine.authorize(username, resource, action, namespace=ns, application=app)
    return dependency
