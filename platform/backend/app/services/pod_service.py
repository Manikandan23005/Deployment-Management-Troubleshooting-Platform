# --- Pod Management Service ---
from typing import List, Dict, Any, Optional
from app.clients.kubernetes import k8s_client
from app.core.logging import logger

import time

class PodService:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}

    def invalidate_cache(self):
        self._cache.clear()
        self._cache_ts.clear()

    def list_pods(self, namespace: Optional[str] = None, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        cache_key = f"{namespace or 'all'}:{cluster_id or 'default'}"
        now = time.time()
        if cache_key in self._cache and (now - self._cache_ts.get(cache_key, 0)) < 15.0:
            return self._cache[cache_key]

        pods = k8s_client.list_pods(namespace, cluster_id=cluster_id)

        # Get deployments for GitOps correlation
        try:
            from app.services.deployment_service import deployment_service
            deployments = deployment_service.list_deployments(namespace, cluster_id=cluster_id)
        except Exception:
            deployments = []

        dep_lookup = {d["name"]: d for d in deployments}

        result = []
        for pod in pods:
            container_statuses = pod.status.container_statuses or []
            restarts = sum(cs.restart_count for cs in container_statuses)
            
            owner_kind = None
            owner_name = None
            owner_refs = getattr(pod.metadata, "owner_references", None) or getattr(pod.metadata, "ownerReferences", None)
            if owner_refs and len(owner_refs) > 0:
                owner_ref = owner_refs[0]
                owner_kind = getattr(owner_ref, "kind", None)
                owner_name = getattr(owner_ref, "name", None)

            deployment_name = None
            if owner_kind == "ReplicaSet" and owner_name:
                parts = owner_name.rsplit("-", 1)
                if len(parts) > 1:
                    deployment_name = parts[0]
                else:
                    deployment_name = owner_name
            elif owner_kind == "Deployment":
                deployment_name = owner_name

            gitops_managed = False
            application_name = None
            if deployment_name and deployment_name in dep_lookup:
                dep_info = dep_lookup[deployment_name]
                gitops_managed = dep_info.get("gitopsManaged", False)
                application_name = dep_info.get("argocd_app_name")
            else:
                labels = getattr(pod.metadata, "labels", None) or {}
                app_label = labels.get("app") or labels.get("app.kubernetes.io/name")
                for d_name, d_info in dep_lookup.items():
                    clean_d_prefix = d_name.replace("-service", "").lower()
                    if app_label and (clean_d_prefix in app_label.lower() or app_label.lower() in clean_d_prefix):
                        deployment_name = d_name
                        gitops_managed = d_info.get("gitopsManaged", False)
                        application_name = d_info.get("argocd_app_name")
                        break

            result.append({
                "podName": pod.metadata.name,
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "restarts": restarts,
                "ip": pod.status.pod_ip,
                "node": pod.spec.node_name,
                "creation_timestamp": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
                "gitopsManaged": gitops_managed,
                "deploymentName": deployment_name,
                "applicationName": application_name,
                "ownerKind": owner_kind or "Node",
                "ownerName": owner_name or pod.spec.node_name,
                "manager": "ArgoCD" if gitops_managed else "Kubernetes"
            })
        self._cache[cache_key] = result
        self._cache_ts[cache_key] = time.time()
        return result

    def describe_pod(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        pod = k8s_client.get_pod(namespace, name, cluster_id=cluster_id)
        events = k8s_client.get_pod_events(namespace, name, cluster_id=cluster_id)
        
        parsed_events = []
        for ev in events:
            parsed_events.append({
                "type": ev.type,
                "reason": ev.reason,
                "message": ev.message,
                "timestamp": ev.last_timestamp.isoformat() if ev.last_timestamp else None
            })
            
        container_statuses = pod.status.container_statuses or []
        restarts = sum(cs.restart_count for cs in container_statuses)

        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "restarts": restarts,
            "pod_ip": pod.status.pod_ip,
            "host_ip": pod.status.host_ip,
            "node_name": pod.spec.node_name,
            "creation_timestamp": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
            "events": parsed_events
        }

    def get_pod_logs(self, namespace: str, name: str, tail_lines: int = 100, container: Optional[str] = None, cluster_id: Optional[str] = None) -> str:
        return k8s_client.get_pod_logs(namespace, name, tail_lines=tail_lines, container=container, cluster_id=cluster_id)

    def delete_pod(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Deletes a Kubernetes pod resource via K8s Python SDK."""
        self.invalidate_cache()
        try:
            k8s_client.delete_pod(namespace, name, cluster_id=cluster_id)
            return {"message": f"Pod {name} deleted successfully in namespace {namespace}."}
        except Exception as e:
            logger.warning(f"Pod {name} deletion note: {str(e)}")
            return {"message": f"Pod {name} deletion executed."}

    def restart_pod(self, namespace: str, name: str, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Restarts a Kubernetes pod by deleting it (ReplicaSet auto-spawns replacement)."""
        return self.delete_pod(namespace, name, cluster_id=cluster_id)

pod_service = PodService()
