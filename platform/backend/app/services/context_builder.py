# --- AI Incident Context Builder ---
from typing import Dict, Any, List, Optional
from app.services.pod_service import pod_service
from app.services.deployment_service import deployment_service
from app.services.node_service import node_service
from app.services.namespace_service import namespace_service
from app.services.monitoring_service import monitoring_service
from app.services.argocd_service import argocd_service
from app.services.incident_analyzer import incident_analyzer
from app.services.scope_engine import scope_engine
from shared.scope import OperationsScope
from app.utils.cache import ttl_cache
from app.utils.session_manager import session_manager
from app.core.logging import logger

from app.services.cluster_registry import cluster_registry

class ContextBuilder:
    """Collects live cluster configurations, events, metrics, logs, and GitOps sync states into a unified dictionary."""

    def _get_pods(self, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return pod_service.list_pods(cluster_id=cluster_id)
        except Exception as e:
            logger.warning(f"Failed to list pods: {str(e)}")
            return []

    def _get_deployments(self, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return deployment_service.list_deployments(cluster_id=cluster_id)
        except Exception as e:
            logger.warning(f"Failed to list deployments: {str(e)}")
            return []

    def _get_nodes(self, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return node_service.list_nodes(cluster_id=cluster_id)
        except Exception as e:
            logger.warning(f"Failed to list nodes: {str(e)}")
            return []

    def _get_metrics(self, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            return monitoring_service.get_cluster_metrics(cluster_id=cluster_id)
        except Exception as e:
            logger.warning(f"Failed to get metrics: {str(e)}")
            return {"cpu_utilization": 0.0, "memory_utilization": 0.0, "network_throughput_bytes": 0.0}

    def _get_argocd_apps(self) -> List[Dict[str, Any]]:
        try:
            return argocd_service.list_applications()
        except Exception as e:
            logger.warning(f"Failed to list ArgoCD apps: {str(e)}")
            return []

    def _get_namespaces(self, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return namespace_service.list_namespaces(cluster_id=cluster_id)
        except Exception as e:
            logger.warning(f"Failed to list namespaces: {str(e)}")
            return []

    def classify_query(self, prompt: str) -> List[str]:
        lower = prompt.lower()
        categories = []
        
        if any(w in lower for w in ["health", "status", "ready", "running"]):
            categories.append("Cluster Health")
        if "pod" in lower:
            categories.append("Pods")
        if any(w in lower for w in ["deployment", "rollout", "replica"]):
            categories.append("Deployments")
        if "namespace" in lower:
            categories.append("Namespaces")
        if "node" in lower:
            categories.append("Nodes")
        if any(w in lower for w in ["metric", "prometheus", "gauge"]):
            categories.append("Metrics")
        if "cpu" in lower:
            categories.append("CPU")
        if "memory" in lower or "oom" in lower:
            categories.append("Memory")
        if any(w in lower for w in ["log", "loki", "message"]):
            categories.append("Logs")
        if any(w in lower for w in ["event", "schedule"]):
            categories.append("Events")
        if "restart" in lower:
            categories.append("Restart Analysis")
        if any(w in lower for w in ["gitops", "argocd"]):
            categories.append("GitOps")
        if any(w in lower for w in ["incident", "outage", "error", "fail"]):
            categories.append("Incidents")
            
        return categories if categories else ["General Operations"]

    def build_incident_context(self, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Gathers complete context details for a specific pod incident."""
        context = {
            "target_pod": pod_name,
            "target_namespace": namespace,
            "kubernetes_state": {},
            "prometheus_metrics": {},
            "argocd_status": []
        }

        try:
            pod_details = pod_service.describe_pod(namespace, pod_name)
            context["kubernetes_state"]["pod_details"] = pod_details
        except Exception as e:
            logger.warning(f"ContextBuilder failed to read pod details: {str(e)}")
            context["kubernetes_state"]["pod_details"] = {"name": pod_name, "error": str(e)}

        try:
            logs = pod_service.get_pod_logs(namespace, pod_name, tail_lines=50)
            context["kubernetes_state"]["pod_recent_logs"] = logs
        except Exception as e:
            logger.warning(f"ContextBuilder failed to read logs: {str(e)}")
            context["kubernetes_state"]["pod_recent_logs"] = f"Unavailable: {str(e)}"

        try:
            deployments = self._get_deployments()
            context["kubernetes_state"]["deployments"] = deployments
        except Exception as e:
            logger.warning(f"ContextBuilder failed to list deployments: {str(e)}")

        try:
            nodes = self._get_nodes()
            context["kubernetes_state"]["nodes"] = nodes
        except Exception as e:
            logger.warning(f"ContextBuilder failed to list nodes: {str(e)}")

        try:
            metrics = self._get_metrics()
            context["prometheus_metrics"] = metrics
        except Exception as e:
            logger.warning(f"ContextBuilder failed to get cluster metrics: {str(e)}")

        try:
            apps = self._get_argocd_apps()
            context["argocd_status"] = apps
        except Exception as e:
            logger.warning(f"ContextBuilder failed to list ArgoCD apps: {str(e)}")

        return context

    def build_query_context(self, prompt: str, session_id: Optional[str] = None, scope: Optional[OperationsScope] = None) -> Dict[str, Any]:
        """Detects query intent, applies inherited operations scope, and gathers comprehensive cluster, log, metric, and platform metadata."""
        current_scope = scope or scope_engine.resolve_scope()
        categories = self.classify_query(prompt)
        
        # 1. Clusters & Cloud Accounts Metadata
        from app.services.cluster_registry import cluster_registry
        from app.aws.account_registry import aws_account_registry
        from app.services.iam_service import iam_service
        from app.services.audit_service import audit_service

        clusters_list = cluster_registry.list_clusters()
        aws_accounts = aws_account_registry.list_accounts()
        default_cluster = cluster_registry.get_default_cluster()

        has_connected_cluster = len(clusters_list) > 0
        active_cluster_data = default_cluster or (clusters_list[0] if clusters_list else None)
        active_cid = active_cluster_data.get("id") if isinstance(active_cluster_data, dict) else getattr(current_scope, "cluster_id", None)

        cluster_info = {
            "is_connected": has_connected_cluster,
            "total_clusters": len(clusters_list),
            "clusters": clusters_list,
            "total_aws_accounts": len(aws_accounts),
            "aws_accounts": [{"id": getattr(a, "id", None), "account_id": getattr(a, "account_id", None), "name": getattr(a, "name", None), "region": getattr(a, "default_region", None), "status": getattr(a.status, "value", str(getattr(a, "status", "")))} for a in aws_accounts],
            "active_cluster": active_cluster_data or "None (No cluster connected)"
        }

        # 2. Kubernetes Metadata Store (Pods, Nodes, Deployments, Namespaces)
        raw_pods = self._get_pods(cluster_id=active_cid) if has_connected_cluster else []
        pods = scope_engine.filter_pods(raw_pods, current_scope) if raw_pods else []
        running_pods = [p for p in pods if p.get("status") == "Running"]
        failing_pods = [p for p in pods if p.get("status") in ["CrashLoopBackOff", "Error", "Failed", "OOMKilled"]]
        pending_pods = [p for p in pods if p.get("status") == "Pending"]

        raw_nodes = self._get_nodes(cluster_id=active_cid) if has_connected_cluster else []
        raw_deps = self._get_deployments(cluster_id=active_cid) if has_connected_cluster else []
        deps = scope_engine.filter_deployments(raw_deps, current_scope) if raw_deps else []
        raw_ns = self._get_namespaces(cluster_id=active_cid) if has_connected_cluster else []

        # 3. Target Service / Pod Logs Collection
        resolved_service = session_manager.resolve_target_service(session_id, prompt)
        targeted_logs = ""
        if has_connected_cluster and (resolved_service or "log" in prompt.lower() or "error" in prompt.lower()):
            try:
                target_pod_name = None
                target_ns = current_scope.namespace or "devops-nexus-prod"
                if resolved_service:
                    for p in pods:
                        p_name = p.get("name") or p.get("podName", "")
                        if resolved_service in p_name:
                            target_pod_name = p_name
                            target_ns = p.get("namespace", target_ns)
                            break
                elif pods:
                    target_pod_name = pods[0].get("name") or pods[0].get("podName")
                    target_ns = pods[0].get("namespace", target_ns)

                if target_pod_name:
                    targeted_logs = pod_service.get_pod_logs(target_ns, target_pod_name, tail_lines=40)
            except Exception as e:
                targeted_logs = f"Log fetch exception: {str(e)}"

        # 4. Telemetry Metrics
        raw_metrics = self._get_metrics()
        metrics = {
            "cpu_utilization": round(raw_metrics.get("cpu_utilization", 0.0), 1),
            "memory_utilization": round(raw_metrics.get("memory_utilization", 0.0), 1),
            "network_throughput_bytes": round(raw_metrics.get("network_throughput_bytes", 0.0), 1)
        }

        # 5. GitOps / ArgoCD Applications
        raw_apps = self._get_argocd_apps() if has_connected_cluster else []
        apps = scope_engine.filter_argocd_apps(raw_apps, current_scope) if raw_apps else []

        # 6. Platform Administration & Security Knowledge
        users = []
        try:
            users = [{"username": u.get("username"), "role": u.get("role"), "is_active": u.get("is_active", True)} for u in iam_service.list_users()]
        except Exception:
            pass

        roles = ["Administrator", "Platform Engineer", "DevOps Engineer", "Developer", "Viewer"]
        permissions_summary = {
            "Administrator": "Full administrative control, user management, cluster registration, RBAC matrix, destructive actions.",
            "Platform Engineer": "Cluster & infrastructure configuration, GitOps pipelines, telemetry monitoring, deployment operations.",
            "DevOps Engineer": "Deployment scaling, restarts, log inspection, Prometheus/Loki metrics, incident diagnostics.",
            "Developer": "Application workload view, pod logs, developer workspace scope, AI operations chat.",
            "Viewer": "Read-only access across cluster telemetry, metrics, and incident reports."
        }

        recent_audits = []
        try:
            audit_records = audit_service.get_audit_logs(limit=5)
            recent_audits = [{"username": a.get("username"), "action": a.get("action"), "target": a.get("target_resource"), "timestamp": a.get("timestamp")} for a in audit_records]
        except Exception:
            pass

        context = {
            "cluster_status": cluster_info,
            "operations_scope": {
                "mode": current_scope.mode.value,
                "namespace": current_scope.namespace,
                "application": current_scope.application,
                "domain": current_scope.domain.value if current_scope.domain else None
            },
            "query_categories": categories,
            "resolved_service": resolved_service,
            "infrastructure_summary": {
                "total_nodes": len(raw_nodes),
                "nodes": [{"name": n.get("name"), "status": n.get("status"), "role": n.get("role")} for n in raw_nodes[:10]],
                "total_pods": len(pods),
                "running_pods_count": len(running_pods),
                "failing_pods_count": len(failing_pods),
                "pending_pods_count": len(pending_pods),
                "pods_sample": [{"name": p.get("name"), "namespace": p.get("namespace"), "status": p.get("status"), "restarts": p.get("restarts", 0)} for p in pods[:12]],
                "total_deployments": len(deps),
                "deployments": [{"name": d.get("name"), "namespace": d.get("namespace"), "replicas": d.get("replicas"), "available": d.get("available_replicas")} for d in deps[:10]],
                "namespaces": [n.get("name") if isinstance(n, dict) else n for n in raw_ns[:10]]
            },
            "targeted_logs": targeted_logs if targeted_logs else "No pod logs requested or cluster unconfigured.",
            "metrics": metrics,
            "gitops_applications": [{"name": a.get("name"), "sync_status": a.get("sync_status"), "health_status": a.get("health_status")} for a in apps[:10]],
            "platform_security_and_admin": {
                "registered_users_count": len(users),
                "users_list": users,
                "roles_catalog": roles,
                "permissions_matrix": permissions_summary,
                "recent_audit_logs": recent_audits,
                "devops_nexus_platform_overview": (
                    "DevOps Nexus is an enterprise Cloud-Native Deployment Management & Observability Platform. "
                    "Features include Multi-Cluster Registry (Minikube, kubeadm, AWS EKS via STS AssumeRole), "
                    "Granular RBAC Matrix, Real-time Prometheus & Loki Observability, GitOps Control Plane with ArgoCD, "
                    "and AI Operations Q&A Assistant."
                )
            }
        }

        return context

context_builder = ContextBuilder()
