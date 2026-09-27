# --- Kubernetes Client Wrapper ---
import datetime
from typing import List, Dict, Any, Optional
from kubernetes import client, config
from shared.exceptions import KubernetesClientException
from app.core.logging import logger

from app.clients.k8s_factory import k8s_client_factory
from app.services.cluster_registry import cluster_registry

class KubernetesClient:
    """Manages low-level connections and queries across multiple Kubernetes API clusters (On-Premises & Amazon EKS)."""
    def __init__(self):
        self._initialized = True
        self.v1 = None
        self.apps_v1 = None
        self.networking_v1 = None

    def get_clients(self, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Resolves dynamic API clients for target cluster_id through environment-aware client factory."""
        return k8s_client_factory.get_clients(cluster_id)

    # CoreV1 Mappings
    def list_namespaces(self, cluster_id: Optional[str] = None) -> List[Any]:
        clients = self.get_clients(cluster_id)
        try:
            return clients["v1"].list_namespace().items
        except Exception as e:
            raise KubernetesClientException(f"Failed to list namespaces: {str(e)}")

    def list_nodes(self, cluster_id: Optional[str] = None) -> List[Any]:
        clients = self.get_clients(cluster_id)
        try:
            return clients["v1"].list_node().items
        except Exception as e:
            raise KubernetesClientException(f"Failed to list worker nodes: {str(e)}")

    def list_pods(self, namespace: Optional[str] = None, cluster_id: Optional[str] = None) -> List[Any]:
        clients = self.get_clients(cluster_id)
        try:
            if namespace:
                return clients["v1"].list_namespaced_pod(namespace).items
            return clients["v1"].list_pod_for_all_namespaces().items
        except Exception as e:
            raise KubernetesClientException(f"Failed to list pods: {str(e)}")

    def get_pod(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        try:
            return clients["v1"].read_namespaced_pod(name, namespace)
        except Exception as e:
            raise KubernetesClientException(f"Failed to read pod {name} in {namespace}: {str(e)}")

    def get_pod_events(self, namespace: str, pod_name: str, cluster_id: Optional[str] = None) -> List[Any]:
        clients = self.get_clients(cluster_id)
        try:
            field_selector = f"involvedObject.name={pod_name},involvedObject.kind=Pod"
            return clients["v1"].list_namespaced_event(namespace, field_selector=field_selector).items
        except Exception as e:
            raise KubernetesClientException(f"Failed to fetch events for pod {pod_name}: {str(e)}")

    def get_pod_logs(self, namespace: str, name: str, tail_lines: int = 100, container: Optional[str] = None, cluster_id: Optional[str] = None) -> str:
        clients = self.get_clients(cluster_id)
        try:
            if container:
                return clients["v1"].read_namespaced_pod_log(name, namespace, tail_lines=tail_lines, container=container)
            return clients["v1"].read_namespaced_pod_log(name, namespace, tail_lines=tail_lines)
        except Exception as e:
            raise KubernetesClientException(f"Failed to fetch logs for pod {name}: {str(e)}")

    def list_services(self, namespace: Optional[str] = None, cluster_id: Optional[str] = None) -> List[Any]:
        clients = self.get_clients(cluster_id)
        try:
            if namespace:
                return clients["v1"].list_namespaced_service(namespace).items
            return clients["v1"].list_service_for_all_namespaces().items
        except Exception as e:
            raise KubernetesClientException(f"Failed to list services: {str(e)}")

    # AppsV1 Mappings
    def list_deployments(self, namespace: Optional[str] = None, cluster_id: Optional[str] = None) -> List[Any]:
        clients = self.get_clients(cluster_id)
        try:
            if namespace:
                return clients["apps_v1"].list_namespaced_deployment(namespace).items
            return clients["apps_v1"].list_deployment_for_all_namespaces().items
        except Exception as e:
            raise KubernetesClientException(f"Failed to list deployments: {str(e)}")

    def get_deployment(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        try:
            return clients["apps_v1"].read_namespaced_deployment(name, namespace)
        except Exception as e:
            raise KubernetesClientException(f"Failed to read deployment {name} in {namespace}: {str(e)}")

    def scale_deployment(self, namespace: str, name: str, replicas: int, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        body = {"spec": {"replicas": replicas}}
        try:
            return clients["apps_v1"].patch_namespaced_deployment(name, namespace, body)
        except Exception:
            try:
                return clients["apps_v1"].patch_namespaced_deployment_scale(name, namespace, body)
            except Exception as e:
                raise KubernetesClientException(f"Failed to scale deployment {name} to {replicas}: {str(e)}")

    def restart_deployment(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        try:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": now
                            }
                        }
                    }
                }
            }
            return clients["apps_v1"].patch_namespaced_deployment(name, namespace, body)
        except Exception as e:
            raise KubernetesClientException(f"Failed to restart rollout for deployment {name}: {str(e)}")

    def delete_pod(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        try:
            return clients["v1"].delete_namespaced_pod(name, namespace)
        except Exception as e:
            raise KubernetesClientException(f"Failed to delete pod {name}: {str(e)}")

    def delete_deployment(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        try:
            return clients["apps_v1"].delete_namespaced_deployment(name, namespace)
        except Exception as e:
            raise KubernetesClientException(f"Failed to delete deployment {name}: {str(e)}")

    def create_namespace(self, name: str, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        try:
            body = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
            return clients["v1"].create_namespace(body)
        except Exception as e:
            raise KubernetesClientException(f"Failed to create namespace {name}: {str(e)}")

    def delete_namespace(self, name: str, cluster_id: Optional[str] = None) -> Any:
        clients = self.get_clients(cluster_id)
        try:
            return clients["v1"].delete_namespace(name)
        except Exception as e:
            raise KubernetesClientException(f"Failed to delete namespace {name}: {str(e)}")

    # NetworkingV1 Mappings
    def list_ingresses(self, namespace: Optional[str] = None, cluster_id: Optional[str] = None) -> List[Any]:
        clients = self.get_clients(cluster_id)
        try:
            if namespace:
                return clients["networking_v1"].list_namespaced_ingress(namespace).items
            return clients["networking_v1"].list_ingress_for_all_namespaces().items
        except Exception as e:
            raise KubernetesClientException(f"Failed to list ingresses: {str(e)}")

# Export single global client instance
k8s_client = KubernetesClient()
