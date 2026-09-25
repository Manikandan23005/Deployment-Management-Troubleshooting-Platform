# --- ArgoCD REST API Client ---
import httpx
import base64
from typing import List, Dict, Any, Optional
from app.core.settings import settings
from app.core.logging import logger
from shared.exceptions import ArgoCDConnectionException

class ArgoCDClient:
    """Manages connections to the ArgoCD API Server with live endpoint discovery and fail-safe K8s CRD fallbacks."""
    def __init__(self):
        self.default_server = settings.ARGOCD_SERVER or "192.168.49.2:31709"
        self.token = settings.ARGOCD_TOKEN
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.token and self.token != "my-argocd-token-placeholder":
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _get_base_url(self, cluster_id: Optional[str] = None) -> str:
        try:
            from app.services.cluster_registry import cluster_registry
            cluster = cluster_registry.get_cluster(cluster_id)
            argocd_url = cluster.get("argocd_url") if cluster else None
            if argocd_url:
                if not argocd_url.startswith("http"):
                    return f"https://{argocd_url}/api/v1"
                return f"{argocd_url}/api/v1"
        except Exception:
            pass

        # Live discovery of active ArgoCD server NodePort and node IP via K8s API
        try:
            from app.clients.kubernetes import k8s_client
            clients = k8s_client.get_clients(cluster_id)
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
            svc = v1.read_namespaced_service("argocd-server", "argocd")
            node_port = 31709
            for p in svc.spec.ports:
                if (p.name in ("https", "http") or p.port in (443, 80)) and p.node_port:
                    node_port = p.node_port
                    break

            nodes = v1.list_node().items
            node_ip = None
            if nodes:
                for addr in nodes[0].status.addresses:
                    if addr.type == "InternalIP":
                        node_ip = addr.address
                        break

            if node_ip and node_port:
                return f"https://{node_ip}:{node_port}/api/v1"
        except Exception:
            pass

        return f"https://{self.default_server}/api/v1"

    def _ensure_token(self, cluster_id: Optional[str] = None):
        """Programmatically retrieves credentials from K8s secrets and generates a session token."""
        try:
            from app.services.cluster_registry import cluster_registry
            if not cluster_registry.get_clusters():
                return
        except Exception:
            return

        if "Authorization" in self.headers and self.token and self.token != "my-argocd-token-placeholder":
            return
        if hasattr(self, "_last_auth_fail") and (time.time() - self._last_auth_fail < 30):
            return

        base_url = self._get_base_url(cluster_id)
        try:
            from app.clients.kubernetes import k8s_client
            clients = k8s_client.get_clients(cluster_id)
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
            
            # Fetch initial admin credentials directly from cluster secret
            secret = v1.read_namespaced_secret("argocd-initial-admin-secret", "argocd")
            password = base64.b64decode(secret.data["password"]).decode("utf-8").strip()

            url = f"{base_url}/session"
            with httpx.Client(verify=False, timeout=0.8) as client:
                response = client.post(url, json={"username": "admin", "password": password})
                if response.status_code == 200:
                    self.token = response.json()["token"]
                    self.headers["Authorization"] = f"Bearer {self.token}"
                    logger.info("Successfully auto-authenticated with ArgoCD server.")
                else:
                    self._last_auth_fail = time.time()
                    logger.warning(f"ArgoCD session authorization rejected: {response.status_code} - {response.text}")
        except Exception as e:
            self._last_auth_fail = time.time()
            logger.debug(f"ArgoCD client auto-auth skipped/failed: {str(e)}")

    def _fallback_k8s_crd_applications(self, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries ArgoCD Application Custom Resource Definitions directly from Kubernetes API as a fail-safe fallback."""
        try:
            from app.services.cluster_registry import cluster_registry
            if not cluster_registry.get_clusters():
                return []
            from app.clients.kubernetes import k8s_client
            clients = k8s_client.get_clients(cluster_id)
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
            from kubernetes import client as k8s_sdk
            custom_api = k8s_sdk.CustomObjectsApi(v1.api_client)
            crd_res = custom_api.list_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace="argocd",
                plural="applications"
            )
            items = crd_res.get("items", [])
            result = []
            for item in items:
                spec = item.get("spec", {})
                status = item.get("status", {})
                result.append({
                    "metadata": {
                        "name": item.get("metadata", {}).get("name")
                    },
                    "spec": spec,
                    "status": {
                        "sync": {"status": status.get("sync", {}).get("status", "Synced")},
                        "health": {"status": status.get("health", {}).get("status", "Healthy")},
                        "history": status.get("history", [])
                    }
                })
            logger.info(f"Retrieved {len(result)} ArgoCD applications via live K8s CustomObjects API fallback.")
            return result
        except Exception as e:
            logger.warning(f"K8s CustomObjectsApi fallback query for ArgoCD apps failed: {str(e)}")
            return []

    def list_applications(self, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            from app.services.cluster_registry import cluster_registry
            if not cluster_registry.get_clusters():
                return []
            self._ensure_token(cluster_id)
            base_url = self._get_base_url(cluster_id)
            url = f"{base_url}/applications"
            with httpx.Client(headers=self.headers, verify=False, timeout=1.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    items = response.json().get("items", [])
                    if items:
                        return items
        except Exception as e:
            logger.warning(f"ArgoCD REST API list request warning ({str(e)}). Falling back to K8s CRD API.")

        # Fail-safe K8s CRD API fallback
        return self._fallback_k8s_crd_applications(cluster_id)

    def sync_application(self, app_name: str, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_token(cluster_id)
        base_url = self._get_base_url(cluster_id)
        url = f"{base_url}/applications/{app_name}/sync"
        try:
            with httpx.Client(headers=self.headers, verify=False, timeout=5.0) as client:
                response = client.post(url, json={})
                if response.status_code == 400 and "another operation is already in progress" in response.text:
                    logger.info(f"Sync already in progress for ArgoCD application {app_name}.")
                    return {"status": "Syncing", "message": f"ArgoCD sync operation for {app_name} is already in progress."}
                if response.status_code != 200:
                    raise ArgoCDConnectionException(f"ArgoCD sync failed {response.status_code}: {response.text}")
                return response.json()
        except Exception as e:
            if "another operation is already in progress" in str(e):
                return {"status": "Syncing", "message": f"ArgoCD sync operation for {app_name} is already in progress."}
            logger.error(f"Failed to sync ArgoCD application {app_name}: {str(e)}")
            raise ArgoCDConnectionException(f"ArgoCD connection error: {str(e)}")

    def refresh_application(self, app_name: str, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_token(cluster_id)
        base_url = self._get_base_url(cluster_id)
        url = f"{base_url}/applications/{app_name}?refresh=hard"
        try:
            with httpx.Client(headers=self.headers, verify=False, timeout=5.0) as client:
                response = client.get(url)
                if response.status_code != 200:
                    raise ArgoCDConnectionException(f"ArgoCD refresh failed {response.status_code}: {response.text}")
                return response.json()
        except Exception as e:
            logger.error(f"Failed to refresh ArgoCD application {app_name}: {str(e)}")
            raise ArgoCDConnectionException(f"ArgoCD connection error: {str(e)}")

    def rollback_application(self, app_name: str, revision: int, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_token(cluster_id)
        base_url = self._get_base_url(cluster_id)
        url = f"{base_url}/applications/{app_name}/rollback"
        body = {"revision": revision}
        try:
            with httpx.Client(headers=self.headers, verify=False, timeout=2.0) as client:
                response = client.post(url, json=body)
                if response.status_code != 200:
                    raise ArgoCDConnectionException(f"ArgoCD rollback failed {response.status_code}: {response.text}")
                return response.json()
        except Exception as e:
            logger.error(f"Failed to rollback ArgoCD application {app_name}: {str(e)}")
            raise ArgoCDConnectionException(f"ArgoCD connection error: {str(e)}")

    def get_application(self, app_name: str, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_token(cluster_id)
        base_url = self._get_base_url(cluster_id)
        url = f"{base_url}/applications/{app_name}"
        try:
            with httpx.Client(headers=self.headers, verify=False, timeout=2.0) as client:
                response = client.get(url)
                if response.status_code != 200:
                    raise ArgoCDConnectionException(f"ArgoCD details request failed {response.status_code}: {response.text}")
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch ArgoCD application {app_name} details: {str(e)}")
            # Fallback via K8s CustomObjects API
            try:
                from app.clients.kubernetes import k8s_client
                clients = k8s_client.get_clients(cluster_id)
                v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
                from kubernetes import client as k8s_sdk
                custom_api = k8s_sdk.CustomObjectsApi(v1.api_client)
                item = custom_api.get_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace="argocd",
                    plural="applications",
                    name=app_name
                )
                return item
            except Exception:
                pass
            raise ArgoCDConnectionException(f"ArgoCD connection error: {str(e)}")

    def delete_application(self, app_name: str, cascade: bool = False, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_token(cluster_id)
        base_url = self._get_base_url(cluster_id)
        url = f"{base_url}/applications/{app_name}?cascade={str(cascade).lower()}"
        try:
            with httpx.Client(headers=self.headers, verify=False, timeout=5.0) as client:
                response = client.delete(url)
                if response.status_code not in (200, 204):
                    raise ArgoCDConnectionException(f"ArgoCD delete application failed {response.status_code}: {response.text}")
                return {"success": True, "message": f"ArgoCD Application '{app_name}' disconnected successfully."}
        except Exception as e:
            logger.error(f"Failed to delete ArgoCD application {app_name}: {str(e)}")
            # Fallback using K8s Custom Objects API if ArgoCD API token is unavailable
            try:
                from app.clients.kubernetes import k8s_client
                clients = k8s_client.get_clients(cluster_id)
                v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
                from kubernetes import client as k8s_sdk
                custom_api = k8s_sdk.CustomObjectsApi(v1.api_client)
                custom_api.delete_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace="argocd",
                    plural="applications",
                    name=app_name
                )
                return {"success": True, "message": f"ArgoCD Application '{app_name}' disconnected via K8s CRD API."}
            except Exception as inner_e:
                logger.error(f"Fallback CRD deletion also failed: {str(inner_e)}")
            raise ArgoCDConnectionException(f"ArgoCD connection error: {str(e)}")

    def reconnect_application(self, app_name: str, mode: str = "restore", namespace: str = "devops-nexus-prod", cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Reconnects a Kubernetes deployment back to ArgoCD GitOps management."""
        clean_prefix = app_name.replace("-service", "").replace("-prod", "").replace("-dev", "").lower()
        target_app_name = f"{clean_prefix}-prod" if not app_name.endswith("-prod") else app_name

        # Determine git repo manifest path
        if clean_prefix in ["auth", "frontend", "gateway", "notification", "orders", "payment", "products", "users"]:
            repo_path = f"helm/{clean_prefix}"
        else:
            repo_path = "kubernetes"

        app_manifest = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": target_app_name,
                "namespace": "argocd",
                "labels": {"env": "prod"}
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": "https://github.com/Manikandan23005/Microservice-Deployment-Monitoring-Platform.git",
                    "targetRevision": "main",
                    "path": repo_path
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": namespace
                },
                "syncPolicy": {
                    "automated": {
                        "selfHeal": True,
                        "prune": False
                    }
                },
                "ignoreDifferences": [
                    {
                        "group": "apps",
                        "kind": "Deployment",
                        "jsonPointers": ["/spec/replicas"]
                    }
                ]
            }
        }

        # Step 1: Create/Apply ArgoCD Application CRD
        from app.clients.kubernetes import k8s_client
        clients = k8s_client.get_clients(cluster_id)
        v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
        from kubernetes import client as k8s_sdk

        custom_api = k8s_sdk.CustomObjectsApi(v1.api_client)
        try:
            custom_api.create_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace="argocd",
                plural="applications",
                body=app_manifest
            )
            logger.info(f"Created ArgoCD Application CRD '{target_app_name}'.")
        except k8s_sdk.rest.ApiException as e:
            if e.status in (409, 422):
                # Update existing application CRD if it already exists
                custom_api.patch_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace="argocd",
                    plural="applications",
                    name=target_app_name,
                    body=app_manifest
                )
                logger.info(f"Patched existing ArgoCD Application CRD '{target_app_name}'.")
            else:
                raise ArgoCDConnectionException(f"Failed to create ArgoCD application CRD: {e.reason}")

        # Step 2: Trigger Sync
        try:
            self.refresh_application(target_app_name, cluster_id=cluster_id)
        except Exception as e:
            logger.warning(f"Refresh failed during reconnect: {str(e)}")

        return {
            "success": True,
            "message": f"Deployment '{app_name}' reconnected to GitOps successfully under ArgoCD app '{target_app_name}'.",
            "app_name": target_app_name,
            "mode": mode
        }

argocd_client = ArgoCDClient()
