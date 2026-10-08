# --- Multi-Cluster Registry Service ---
import os
import uuid
import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
import yaml
from kubernetes import client, config
from app.core.logging import logger
from app.db.postgres import SessionLocal, ClusterModel, postgres_available
from shared.exceptions import KubernetesClientException

class ClusterProvider(str, Enum):
    MINIKUBE = "Minikube"
    KUBEADM = "kubeadm"
    EKS = "EKS"
    GKE = "GKE"
    AKS = "AKS"
    CUSTOM = "Custom"

class ClusterEnvironment(str, Enum):
    DEVELOPMENT = "Development"
    STAGING = "Staging"
    PRODUCTION = "Production"
    QA = "QA"

class ClusterStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    UNREACHABLE = "UNREACHABLE"
    DEGRADED = "DEGRADED"

class ClusterRegistryService:
    """Enterprise Cluster Registry managing multiple Kubernetes clusters and contexts."""

    def __init__(self):
        self._memory_clusters: Dict[str, Dict[str, Any]] = {}
        self._api_client_cache: Dict[str, Dict[str, Any]] = {}
        self._auto_detect_local_clusters()

    def _auto_detect_local_clusters(self):
        """Auto-detects local Kubernetes clusters (Minikube, kubeadm, admin.conf) from environment & kubeconfig."""
        self._auto_register_local_minikube()

        # Scan host paths for local kubeadm cluster configurations
        kubeconfig_paths = [
            "/etc/kubernetes/admin.conf",
            os.path.expanduser("~/.kube/config"),
            os.getenv("KUBECONFIG")
        ]

        for kpath in kubeconfig_paths:
            if kpath and os.path.exists(kpath):
                try:
                    with open(kpath, "r") as f:
                        content = f.read()
                    contexts = self.parse_kubeconfig_contexts(content)
                    for ctx in contexts:
                        ctx_name = ctx.get("context_name", "")
                        if "kubernetes-admin" in ctx_name.lower() or "kubeadm" in ctx_name.lower() or "admin.conf" in kpath:
                            self._auto_register_kubeadm(ctx_name, ctx.get("api_server", "https://10.0.1.100:6443"), content)
                except Exception as e:
                    logger.debug(f"Kubeconfig scan on {kpath} skipped: {str(e)}")

    def _auto_register_local_minikube(self):
        """Auto-detects local Minikube kubeconfig and registers it as 'Local Development' only if local config exists."""
        kpath = os.path.expanduser("~/.kube/config")
        if not (os.path.exists(kpath) and os.path.isfile(kpath)):
            return

        try:
            with open(kpath, "r") as f:
                content = f.read()
            if "minikube" not in content.lower():
                return
        except Exception:
            return

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        minikube_cluster = {
            "id": "cluster-minikube-local",
            "name": "Local Development",
            "description": "Local Minikube Kubernetes cluster environment",
            "environment": ClusterEnvironment.DEVELOPMENT.value,
            "provider": ClusterProvider.MINIKUBE.value,
            "context_name": "minikube",
            "kubeconfig_content": None,
            "api_server": "https://192.168.49.2:8443",
            "authentication_type": "Kubeconfig",
            "default_namespace": "devops-nexus-prod",
            "status": ClusterStatus.CONNECTED.value,
            "is_default": True,
            "argocd_url": os.getenv("ARGOCD_SERVER", "http://192.168.49.2:30901"),
            "argocd_token": None,
            "prometheus_url": os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
            "loki_url": os.getenv("LOKI_URL", "http://localhost:3100"),
            "created_at": now,
            "updated_at": now
        }
        self._memory_clusters[minikube_cluster["id"]] = minikube_cluster

        # Sync into PostgreSQL if available
        if postgres_available and SessionLocal:
            try:
                db = SessionLocal()
                existing = db.query(ClusterModel).filter(ClusterModel.id == minikube_cluster["id"]).first()
                if not existing:
                    db_cluster = ClusterModel(
                        id=minikube_cluster["id"],
                        name=minikube_cluster["name"],
                        description=minikube_cluster["description"],
                        environment=minikube_cluster["environment"],
                        provider=minikube_cluster["provider"],
                        context_name=minikube_cluster["context_name"],
                        kubeconfig_content=minikube_cluster["kubeconfig_content"],
                        api_server=minikube_cluster["api_server"],
                        authentication_type=minikube_cluster["authentication_type"],
                        default_namespace=minikube_cluster["default_namespace"],
                        status=minikube_cluster["status"],
                        is_default=minikube_cluster["is_default"],
                        argocd_url=minikube_cluster["argocd_url"],
                        argocd_token=minikube_cluster["argocd_token"],
                        prometheus_url=minikube_cluster["prometheus_url"],
                        loki_url=minikube_cluster["loki_url"],
                        created_at=minikube_cluster["created_at"],
                        updated_at=minikube_cluster["updated_at"]
                    )
                    db.add(db_cluster)
                    db.commit()
                db.close()
                logger.info("Successfully registered local Minikube cluster in Cluster Registry.")
            except Exception as e:
                logger.warning(f"Failed to persist local Minikube cluster in PostgreSQL: {str(e)}")

    def _auto_register_kubeadm(self, context_name: str, api_server: str, kubeconfig_content: str):
        """Auto-registers detected local kubeadm cluster."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        kubeadm_cluster = {
            "id": "cluster-kubeadm-local",
            "name": "Kubeadm Production Cluster",
            "description": "Production kubeadm bare-metal cluster environment",
            "environment": ClusterEnvironment.PRODUCTION.value,
            "provider": ClusterProvider.KUBEADM.value,
            "context_name": context_name,
            "kubeconfig_content": kubeconfig_content,
            "api_server": api_server,
            "authentication_type": "Kubeconfig",
            "default_namespace": "devops-nexus-prod",
            "status": ClusterStatus.CONNECTED.value,
            "is_default": False,
            "argocd_url": None,
            "argocd_token": None,
            "prometheus_url": None,
            "loki_url": None,
            "created_at": now,
            "updated_at": now
        }
        self._memory_clusters[kubeadm_cluster["id"]] = kubeadm_cluster

        if postgres_available and SessionLocal:
            try:
                db = SessionLocal()
                existing = db.query(ClusterModel).filter(ClusterModel.id == kubeadm_cluster["id"]).first()
                if not existing:
                    db_cluster = ClusterModel(
                        id=kubeadm_cluster["id"],
                        name=kubeadm_cluster["name"],
                        description=kubeadm_cluster["description"],
                        environment=kubeadm_cluster["environment"],
                        provider=kubeadm_cluster["provider"],
                        context_name=kubeadm_cluster["context_name"],
                        kubeconfig_content=kubeadm_cluster["kubeconfig_content"],
                        api_server=kubeadm_cluster["api_server"],
                        authentication_type=kubeadm_cluster["authentication_type"],
                        default_namespace=kubeadm_cluster["default_namespace"],
                        status=kubeadm_cluster["status"],
                        is_default=kubeadm_cluster["is_default"],
                        argocd_url=kubeadm_cluster["argocd_url"],
                        argocd_token=kubeadm_cluster["argocd_token"],
                        prometheus_url=kubeadm_cluster["prometheus_url"],
                        loki_url=kubeadm_cluster["loki_url"],
                        created_at=kubeadm_cluster["created_at"],
                        updated_at=kubeadm_cluster["updated_at"]
                    )
                    db.add(db_cluster)
                    db.commit()
                db.close()
                logger.info("Successfully registered local kubeadm cluster in Cluster Registry.")
            except Exception as e:
                logger.warning(f"Failed to persist local kubeadm cluster in PostgreSQL: {str(e)}")

    def list_clusters(self) -> List[Dict[str, Any]]:
        if postgres_available and SessionLocal:
            try:
                db = SessionLocal()
                clusters = db.query(ClusterModel).all()
                result = []
                for c in clusters:
                    result.append({
                        "id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "environment": c.environment,
                        "provider": c.provider,
                        "context_name": c.context_name,
                        "api_server": c.api_server,
                        "authentication_type": c.authentication_type,
                        "default_namespace": c.default_namespace,
                        "status": c.status,
                        "is_default": c.is_default,
                        "argocd_url": c.argocd_url,
                        "prometheus_url": c.prometheus_url,
                        "loki_url": c.loki_url,
                        "created_at": c.created_at,
                        "updated_at": c.updated_at
                    })
                db.close()
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Failed to fetch clusters from PostgreSQL: {str(e)}")

        return list(self._memory_clusters.values())

    def get_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        if not cluster_id or cluster_id in ("default", "active"):
            return self.get_default_cluster()
        if cluster_id in self._memory_clusters:
            return self._memory_clusters[cluster_id]
        if cluster_id == "cluster-minikube-local":
            return {
                "id": "cluster-minikube-local",
                "name": "Local Development",
                "provider": ClusterProvider.MINIKUBE.value,
                "authentication_type": "Kubeconfig",
                "status": "CONNECTED"
            }
        clusters = self.list_clusters()
        for c in clusters:
            if c["id"] == cluster_id:
                return c
        # Match by prefix/suffix or name in case slug or id variations exist
        for c in clusters:
            if cluster_id in c["id"] or c["id"] in cluster_id or cluster_id.lower() == c.get("name", "").lower():
                return c
        return None

    def get_default_cluster(self) -> Optional[Dict[str, Any]]:
        clusters = self.list_clusters()
        for c in clusters:
            if c.get("is_default"):
                return c
        if clusters:
            return clusters[0]
        return self._memory_clusters.get("cluster-minikube-local")

    def add_cluster(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cluster_name = data.get("name", "New Cluster")
        provider = data.get("provider", ClusterProvider.MINIKUBE.value)
        environment = data.get("environment", ClusterEnvironment.DEVELOPMENT.value)

        # Deterministic cluster ID priority
        if data.get("id"):
            cluster_id = data["id"]
        elif provider == ClusterProvider.EKS.value or data.get("eks_cluster_name"):
            eks_name = data.get("eks_cluster_name") or cluster_name.replace("eks-", "")
            cluster_id = f"cluster-eks-{eks_name}"
        elif cluster_name:
            clean_slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in cluster_name.lower()).strip("-")
            cluster_id = f"cluster-{clean_slug}" if clean_slug else f"cluster-{uuid.uuid4().hex[:8]}"
        else:
            cluster_id = f"cluster-{uuid.uuid4().hex[:8]}"

        is_default = data.get("is_default", False)

        cluster = {
            "id": cluster_id,
            "name": data.get("name", "New Cluster"),
            "description": data.get("description", ""),
            "environment": environment,
            "provider": provider,
            "context_name": data.get("context_name", "default"),
            "kubeconfig_content": data.get("kubeconfig_content"),
            "api_server": data.get("api_server", "https://localhost:6443"),
            "authentication_type": data.get("authentication_type", "Kubeconfig"),
            "default_namespace": data.get("default_namespace", "devops-nexus-prod"),
            "status": ClusterStatus.CONNECTED.value,
            "is_default": is_default,
            "argocd_url": data.get("argocd_url"),
            "argocd_token": data.get("argocd_token"),
            "prometheus_url": data.get("prometheus_url"),
            "loki_url": data.get("loki_url"),
            "created_at": now,
            "updated_at": now
        }

        self._memory_clusters[cluster_id] = cluster

        if postgres_available and SessionLocal:
            try:
                db = SessionLocal()
                if is_default:
                    db.query(ClusterModel).update({ClusterModel.is_default: False})
                db_cluster = ClusterModel(
                    id=cluster["id"],
                    name=cluster["name"],
                    description=cluster["description"],
                    environment=cluster["environment"],
                    provider=cluster["provider"],
                    context_name=cluster["context_name"],
                    kubeconfig_content=cluster["kubeconfig_content"],
                    api_server=cluster["api_server"],
                    authentication_type=cluster["authentication_type"],
                    default_namespace=cluster["default_namespace"],
                    status=cluster["status"],
                    is_default=cluster["is_default"],
                    argocd_url=cluster["argocd_url"],
                    argocd_token=cluster["argocd_token"],
                    prometheus_url=cluster["prometheus_url"],
                    loki_url=cluster["loki_url"],
                    created_at=cluster["created_at"],
                    updated_at=cluster["updated_at"]
                )
                db.add(db_cluster)
                db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Failed to add cluster in PostgreSQL: {str(e)}")

        return cluster

    def delete_cluster(self, cluster_id: str) -> bool:
        if cluster_id in self._memory_clusters:
            del self._memory_clusters[cluster_id]

        if postgres_available and SessionLocal:
            try:
                db = SessionLocal()
                deleted = db.query(ClusterModel).filter(ClusterModel.id == cluster_id).delete()
                db.commit()
                db.close()
                return deleted > 0
            except Exception as e:
                logger.error(f"Failed to delete cluster {cluster_id} in PostgreSQL: {str(e)}")
        return True

    def parse_kubeconfig_contexts(self, raw_content: str) -> List[Dict[str, Any]]:
        """Parses contexts and clusters from uploaded/provided kubeconfig content."""
        try:
            doc = yaml.safe_load(raw_content)
            contexts = doc.get("contexts", [])
            clusters = doc.get("clusters", [])
            cluster_map = {c["name"]: c.get("cluster", {}).get("server") for c in clusters if "name" in c}
            
            result = []
            for ctx in contexts:
                ctx_name = ctx.get("name")
                c_info = ctx.get("context", {})
                cluster_name = c_info.get("cluster")
                server_url = cluster_map.get(cluster_name, "https://localhost:6443")
                result.append({
                    "context_name": ctx_name,
                    "cluster_name": cluster_name,
                    "api_server": server_url,
                    "user": c_info.get("user")
                })
            return result
        except Exception as e:
            logger.error(f"Failed to parse kubeconfig content: {str(e)}")
            return []

    def get_k8s_clients(self, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Dynamically instantiates Kubernetes API client instances for the specified cluster."""
        if not cluster_id:
            cluster = self.get_default_cluster()
        else:
            cluster = self.get_cluster(cluster_id) or self.get_default_cluster()

        if not cluster:
            raise KubernetesClientException("No Kubernetes cluster configured.")

        cid = cluster.get("id", "default")
        if cid in self._api_client_cache:
            return self._api_client_cache[cid]

        try:
            context_name = cluster.get("context_name", "minikube")
            kubeconfig_content = cluster.get("kubeconfig_content")

            if kubeconfig_content:
                # Load from in-memory string
                config_dict = yaml.safe_load(kubeconfig_content)
                api_client = config.new_client_from_config_dict(config_dict, context=context_name)
            else:
                # Load from host default kubeconfig file with context_name or fallback
                try:
                    config.load_kube_config(context=context_name)
                    api_client = client.ApiClient()
                except Exception:
                    try:
                        config.load_kube_config()
                        api_client = client.ApiClient()
                    except Exception:
                        api_client = client.ApiClient()

            v1 = client.CoreV1Api(api_client)
            apps_v1 = client.AppsV1Api(api_client)
            networking_v1 = client.NetworkingV1Api(api_client)

            clients = {
                "v1": v1,
                "apps_v1": apps_v1,
                "networking_v1": networking_v1,
                "cluster": cluster
            }
            self._api_client_cache[cid] = clients
            return clients
        except Exception as e:
            logger.warning(f"Failed to initialize Kubernetes API client for cluster '{cid}': {str(e)}")
            raise KubernetesClientException(f"Failed to initialize Kubernetes API client for cluster '{cid}': {str(e)}")

cluster_registry = ClusterRegistryService()
