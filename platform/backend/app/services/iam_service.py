# --- DevOps Nexus IAM & Role Service ---
import os
import uuid
import datetime
from typing import Dict, Any, List, Optional
from shared.iam import User, Role, UserStatus, Resource, Action
from app.core.security_pass import hash_password, verify_password
from app.core.logging import logger

from app.db.postgres import SessionLocal, UserModel, postgres_available

class IAMService:
    """Manages dynamic Users, Roles, and Permission Matrices with PostgreSQL persistence."""

    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._users: Dict[str, User] = {}
        self._init_default_roles()
        self._init_default_users()
        self._sync_postgres_users()

    def _init_default_roles(self):
        resources = [r.value for r in Resource]
        actions = [a.value for a in Action]

        # 1. Administrator (Full Access)
        admin_matrix = {
            res: {act: True for act in actions}
            for res in resources
        }
        self._roles["Administrator"] = Role(
            name="Administrator",
            description="Full root administrative access across all platform modules and settings.",
            is_system=True,
            allowed_workspaces=["cluster", "namespace", "app", "infra"],
            allowed_namespaces=["*"],
            allowed_apps=["*"],
            permissions=admin_matrix
        )

        # 2. Platform Engineer Template
        pe_matrix = {
            res: {act: (act in ["view", "create", "update", "restart_deployment", "scale_deployment", "ai_chat", "ai_incident"]) for act in actions}
            for res in resources
        }
        pe_matrix["settings"]["delete"] = False
        self._roles["Platform Engineer"] = Role(
            name="Platform Engineer",
            description="Infrastructure and cluster-wide maintenance access excluding sensitive setting deletion.",
            is_system=True,
            allowed_workspaces=["cluster", "namespace", "app", "infra"],
            allowed_namespaces=["*"],
            allowed_apps=["*"],
            permissions=pe_matrix
        )

        # 3. DevOps Engineer (Dashboard, AI Operations, Kubernetes, Monitoring, GitOps)
        devops_matrix = {
            res: {
                act: (act in ["view", "create", "update", "restart_deployment", "scale_deployment", "sync_application", "rollback_application", "ai_chat", "ai_incident"])
                for act in actions
            }
            for res in resources
        }
        devops_matrix["nodes"]["create"] = False
        devops_matrix["nodes"]["delete"] = False
        devops_matrix["settings"]["view"] = False
        self._roles["DevOps Engineer"] = Role(
            name="DevOps Engineer",
            description="Deployment lifecycle, GitOps synchronization, monitoring, and incident triage.",
            is_system=True,
            allowed_workspaces=["namespace", "app", "infra"],
            allowed_namespaces=["devops-nexus-prod", "monitoring", "logging-lab", "argocd"],
            allowed_apps=["*"],
            permissions=devops_matrix
        )

        # 4. Application DevOps Template
        app_devops_matrix = {
            res: {
                act: (act in ["view", "restart_deployment", "scale_deployment", "sync_application", "ai_chat", "ai_incident"])
                for act in actions
            }
            for res in resources
        }
        app_devops_matrix["nodes"]["view"] = False
        app_devops_matrix["settings"]["view"] = False
        self._roles["Application DevOps"] = Role(
            name="Application DevOps",
            description="Application-level rollout management and telemetry monitoring.",
            is_system=True,
            allowed_workspaces=["app"],
            allowed_namespaces=["devops-nexus-prod"],
            allowed_apps=["payment-service", "orders-service", "auth-service"],
            permissions=app_devops_matrix
        )

        # 5. Developer (Dashboard, AI Operations, Deployments, Logs)
        dev_matrix = {
            res: {
                act: (act in ["view", "restart_deployment", "scale_deployment", "ai_chat"])
                for act in actions
            }
            for res in resources
        }
        dev_matrix["nodes"]["view"] = False
        dev_matrix["settings"]["view"] = False
        dev_matrix["gitops"]["sync_application"] = False
        dev_matrix["gitops"]["rollback_application"] = False
        self._roles["Developer"] = Role(
            name="Developer",
            description="Application developer access with restart and scaling on assigned workloads.",
            is_system=True,
            allowed_workspaces=["namespace", "app"],
            allowed_namespaces=["devops-nexus-prod"],
            allowed_apps=["payment-service", "auth-service"],
            permissions=dev_matrix
        )

        # 6. Viewer (Dashboard, Monitoring, AI Operations Read Only)
        viewer_matrix = {
            res: {
                act: (act == "view" or act == "ai_chat")
                for act in actions
            }
            for res in resources
        }
        viewer_matrix["nodes"]["view"] = False
        viewer_matrix["settings"]["view"] = False
        self._roles["Viewer"] = Role(
            name="Viewer",
            description="Read-only observational access across authorized namespaces.",
            is_system=True,
            allowed_workspaces=["namespace", "app"],
            allowed_namespaces=["devops-nexus-prod"],
            allowed_apps=["*"],
            permissions=viewer_matrix
        )

    def _init_default_users(self):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        default_admin_uname = os.getenv("DEFAULT_ADMIN_USERNAME", "admin").lower()
        default_admin_pwd = os.getenv("DEFAULT_ADMIN_PASSWORD", "test123")

        # 1. Default Administrator Account
        self._users[default_admin_uname] = User(
            username=default_admin_uname,
            full_name="Platform Administrator",
            email="admin@devopsnexus.io",
            role_name="Administrator",
            status=UserStatus.ACTIVE,
            assigned_workspaces=["cluster", "namespace", "app", "infra"],
            assigned_namespaces=["*"],
            assigned_apps=["*"],
            created_at=now,
            last_login=now,
            password_hash=hash_password(default_admin_pwd),
            require_password_change=False
        )

        # 2. Pre-seeded Enterprise Role Accounts
        self._users["devops"] = User(
            username="devops",
            full_name="Lead DevOps Engineer",
            email="devops@devopsnexus.io",
            role_name="DevOps Engineer",
            status=UserStatus.ACTIVE,
            assigned_workspaces=["namespace", "app", "infra"],
            assigned_namespaces=["devops-nexus-prod", "monitoring", "logging-lab", "argocd"],
            assigned_apps=["*"],
            created_at=now,
            last_login=now,
            password_hash=hash_password("devops123"),
            require_password_change=False
        )

        self._users["developer"] = User(
            username="developer",
            full_name="Backend Application Developer",
            email="developer@devopsnexus.io",
            role_name="Developer",
            status=UserStatus.ACTIVE,
            assigned_workspaces=["namespace", "app"],
            assigned_namespaces=["devops-nexus-prod"],
            assigned_apps=["payment-service", "auth-service"],
            created_at=now,
            last_login=now,
            password_hash=hash_password("developer123"),
            require_password_change=False
        )

        self._users["viewer"] = User(
            username="viewer",
            full_name="Read-Only Observability Auditor",
            email="viewer@devopsnexus.io",
            role_name="Viewer",
            status=UserStatus.ACTIVE,
            assigned_workspaces=["namespace", "app"],
            assigned_namespaces=["devops-nexus-prod"],
            assigned_apps=["*"],
            created_at=now,
            last_login=now,
            password_hash=hash_password("viewer123"),
            require_password_change=False
        )

    def _sync_postgres_users(self):
        """Syncs pre-seeded and active user accounts into PostgreSQL table users."""
        if not (postgres_available and SessionLocal):
            return
        try:
            db = SessionLocal()
            for u in self._users.values():
                existing = db.query(UserModel).filter(UserModel.username == u.username).first()
                if not existing:
                    db_user = UserModel(
                        id=str(uuid.uuid4()),
                        username=u.username,
                        email=u.email or f"{u.username}@devopsnexus.io",
                        password_hash=u.password_hash or "",
                        role=u.role_name,
                        status=u.status.value if hasattr(u.status, 'value') else str(u.status),
                        created_at=u.created_at or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        last_login=getattr(u, 'last_login', u.created_at) or datetime.datetime.now(datetime.timezone.utc).isoformat()
                    )
                    db.add(db_user)
                elif u.username == "admin":
                    existing.status = "ACTIVE"
                    existing.password_hash = u.password_hash
                    db.add(existing)
            db.commit()
            db.close()
            logger.info("Successfully synced user accounts into PostgreSQL database 'devops_nexus'.")
        except Exception as e:
            logger.warning(f"Failed to sync users into PostgreSQL: {str(e)}")

    # --- Role CRUD ---
    def get_roles(self) -> List[Role]:
        return list(self._roles.values())

    def get_role(self, name: str) -> Optional[Role]:
        return self._roles.get(name)

    def create_role(self, role: Role) -> Role:
        if role.name in self._roles:
            raise ValueError(f"Role '{role.name}' already exists.")
        self._roles[role.name] = role
        logger.info(f"Created new IAM role: {role.name}")
        return role

    def update_role(self, name: str, updated: Role) -> Role:
        if name not in self._roles:
            raise ValueError(f"Role '{name}' not found.")
        self._roles[name] = updated
        logger.info(f"Updated IAM role: {name}")
        return updated

    def delete_role(self, name: str) -> bool:
        if name not in self._roles:
            return False
        if self._roles[name].is_system:
            raise ValueError(f"Cannot delete system role template '{name}'.")
        del self._roles[name]
        logger.info(f"Deleted IAM role: {name}")
        return True

    def clone_role(self, source_name: str, new_name: str) -> Role:
        source = self.get_role(source_name)
        if not source:
            raise ValueError(f"Source role '{source_name}' not found.")
        cloned = Role(
            name=new_name,
            description=f"Cloned from {source_name}",
            is_system=False,
            allowed_workspaces=list(source.allowed_workspaces),
            allowed_namespaces=list(source.allowed_namespaces),
            allowed_apps=list(source.allowed_apps),
            permissions=dict(source.permissions)
        )
        return self.create_role(cloned)

    # --- User CRUD & Account Lockout ---
    def get_users(self) -> List[User]:
        return list(self._users.values())

    def get_user(self, username: str) -> Optional[User]:
        return self._users.get(username.lower())

    def create_user(self, user: User, temporary_password: Optional[str] = None) -> User:
        uname = user.username.lower()
        if uname in self._users:
            raise ValueError(f"User '{user.username}' already exists.")
        user.username = uname
        
        pwd = temporary_password or user.password_hash or "TempNexus@123"
        user.password_hash = hash_password(pwd)
        user.require_password_change = True
        
        self._users[uname] = user
        logger.info(f"Created new IAM user: {user.username} (First Login Password Change Required)")
        return user

    def update_user(self, username: str, user_data: Dict[str, Any]) -> User:
        uname = username.lower()
        user = self._users.get(uname)
        if not user:
            raise ValueError(f"User '{username}' not found.")
        
        for k, v in user_data.items():
            if k == "password_hash" and v:
                user.password_hash = hash_password(v)
            elif hasattr(user, k) and v is not None:
                setattr(user, k, v)
        
        logger.info(f"Updated IAM user: {username}")
        return user

    def delete_user(self, username: str) -> bool:
        uname = username.lower()
        if uname not in self._users:
            return False
        if uname == "admin":
            raise ValueError("Root 'admin' account cannot be deleted.")
        del self._users[uname]
        logger.info(f"Deleted IAM user: {username}")
        return True

    def set_user_status(self, username: str, status: UserStatus) -> User:
        uname = username.lower()
        user = self._users.get(uname)
        if not user:
            raise ValueError(f"User '{username}' not found.")
        user.status = status
        if status == UserStatus.ACTIVE:
            user.is_locked = False
            user.failed_login_attempts = 0
        logger.info(f"Set status of user '{username}' to {status}")
        return user

    def record_failed_login(self, username: str) -> bool:
        """Increments failed login attempts. Locks non-root accounts after 5 failed attempts."""
        uname = username.lower()
        user = self._users.get(uname)
        if not user:
            return False
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            if uname == "admin":
                logger.warning(f"Root admin account '@{username}' reached 5 failed login attempts - resetting counter to prevent root lockout.")
                user.failed_login_attempts = 0
                return False
            user.is_locked = True
            user.status = UserStatus.DISABLED
            logger.warning(f"Account '@{username}' LOCKED due to 5 repeated failed login attempts.")
            return True
        return False

    def reset_failed_login(self, username: str):
        uname = username.lower()
        user = self._users.get(uname)
        if user:
            user.failed_login_attempts = 0

    def change_password(self, username: str, old_password: str, new_password: str) -> User:
        """Verifies old password and updates password hash."""
        uname = username.lower()
        user = self._users.get(uname)
        if not user:
            raise ValueError(f"User '{username}' not found.")
        
        if not verify_password(old_password, user.password_hash):
            raise ValueError("Current password verification failed.")
        
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters long.")
            
        user.password_hash = hash_password(new_password)
        user.require_password_change = False
        user.failed_login_attempts = 0
        logger.info(f"Password updated successfully for user '@{username}'.")
        return user

iam_service = IAMService()
