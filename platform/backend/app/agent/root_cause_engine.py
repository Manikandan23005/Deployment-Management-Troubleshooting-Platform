# --- Deterministic Multi-Source Root Cause Analysis Engine ---
import re
from typing import Dict, Any, List, Optional
from app.agent.models import FailureCategory
from app.core.logging import logger

class RootCauseEngine:
    """Performs deterministic evidence-based correlation across Kubernetes, ArgoCD, Git, 
    Prometheus, and Loki telemetry before passing structured context to reasoning engines."""

    def diagnose(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Correlates evidence across all infrastructure dimensions into a structured diagnosis."""
        
        pod = evidence.get("pod") or {}
        container = evidence.get("container_status") or {}
        events = evidence.get("events") or []
        deployment = evidence.get("deployment") or {}
        node = evidence.get("node") or {}
        argocd = evidence.get("argocd") or {}
        prom = evidence.get("prometheus") or {}
        loki_logs = evidence.get("loki_logs") or []

        pod_name = pod.get("name", evidence.get("target_resource", "workload"))
        pod_status = pod.get("status", "Unknown")
        restarts = pod.get("restarts", 0)
        last_exit_code = container.get("last_exit_code", 0)
        last_state_reason = container.get("last_state_reason", "None")
        waiting_reason = container.get("waiting_reason", "None")
        is_ready = container.get("ready", True)

        # Flatten events text for deterministic keyword searching
        event_texts = [f"{e.get('reason', '')} {e.get('message', '')}" for e in events]
        event_str = " ".join(event_texts).lower()
        loki_str = " ".join(loki_logs).lower() if isinstance(loki_logs, list) else str(loki_logs).lower()

        # 1. OOMKilled Correlation
        if (last_exit_code == 137 or 
            last_state_reason == "OOMKilled" or 
            "oomkilled" in event_str or 
            "out of memory" in loki_str or 
            "container killed" in event_str and "137" in event_str):
            
            supporting = [
                f"Container last state reason: '{last_state_reason}'",
                f"Container last exit code: {last_exit_code}",
                f"Restart count: {restarts}"
            ]
            if "oomkilled" in event_str:
                supporting.append("Kubernetes Warning Event: OOMKilled detected")
            if prom and prom.get("memory_utilization"):
                supporting.append(f"Memory utilization gauge: {prom['memory_utilization']}%")

            return {
                "failure_category": FailureCategory.OOM_KILLED,
                "incident_type": "OOMKilled",
                "severity": "Critical",
                "certainty": 0.98,
                "confidence_level": "HIGH",
                "probable_cause": f"Container in pod '{pod_name}' was terminated by Linux kernel OOM-killer (Exit Code 137). Memory allocation exceeded limits.",
                "supporting_evidence": supporting,
                "recommendation": "Increase memory limits in values.yaml (e.g. from 256Mi to 512Mi) and inspect memory leaks.",
                "suggested_action": "modify_gitops_values"
            }

        # 2. ImagePullBackOff Correlation
        if (pod_status == "ImagePullBackOff" or 
            waiting_reason == "ImagePullBackOff" or 
            "back-off pulling image" in event_str or 
            "imagepullbackoff" in event_str):
            
            image_name = pod.get("image", "unknown")
            supporting = [
                f"Pod status: '{pod_status}'",
                f"Waiting reason: '{waiting_reason}'",
                f"Referenced container image: '{image_name}'"
            ]
            for ev in events:
                if "pull" in ev.get("reason", "").lower() or "image" in ev.get("reason", "").lower():
                    supporting.append(f"K8s Event [{ev.get('type', 'Warning')}]: {ev.get('message')}")

            return {
                "failure_category": FailureCategory.IMAGE_PULL_BACKOFF,
                "incident_type": "ImagePullBackOff",
                "severity": "High",
                "certainty": 0.95,
                "confidence_level": "HIGH",
                "probable_cause": f"Container image '{image_name}' could not be pulled by Kubelet. Image tag does not exist or imagePullSecrets are invalid.",
                "supporting_evidence": supporting,
                "recommendation": "Verify image tag in Helm values.yaml, verify registry permissions, or rollback image tag.",
                "suggested_action": "rollback_gitops_revision"
            }

        # 3. ErrImagePull Correlation
        if (pod_status == "ErrImagePull" or 
            waiting_reason == "ErrImagePull" or 
            "errimagepull" in event_str or 
            "failed to pull image" in event_str):
            
            image_name = pod.get("image", "unknown")
            return {
                "failure_category": FailureCategory.ERR_IMAGE_PULL,
                "incident_type": "ErrImagePull",
                "severity": "High",
                "certainty": 0.95,
                "confidence_level": "HIGH",
                "probable_cause": f"Kubelet failed to pull image '{image_name}' due to registry connectivity error or nonexistent repository.",
                "supporting_evidence": [
                    f"Pod status: '{pod_status}'",
                    f"Waiting reason: '{waiting_reason}'",
                    f"Target image: '{image_name}'"
                ],
                "recommendation": "Verify container registry reachability and correct repository name.",
                "suggested_action": "rollback_gitops_revision"
            }

        # 4. FailedScheduling Correlation
        if ("failedscheduling" in event_str or 
            "insufficient cpu" in event_str or 
            "insufficient memory" in event_str or 
            "node(s) had untolerated taint" in event_str or 
            "no nodes are available" in event_str):
            
            return {
                "failure_category": FailureCategory.FAILED_SCHEDULING,
                "incident_type": "FailedScheduling",
                "severity": "High",
                "certainty": 0.92,
                "confidence_level": "HIGH",
                "probable_cause": f"Pod '{pod_name}' could not be scheduled onto any node due to insufficient CPU/memory or untolerated node taints.",
                "supporting_evidence": [
                    f"Pod status: '{pod_status}'",
                    f"Scheduling events: {[e.get('message') for e in events if 'schedul' in e.get('reason', '').lower() or 'insufficient' in e.get('message', '').lower()]}"
                ],
                "recommendation": "Scale cluster worker nodes or reduce pod resource requests.",
                "suggested_action": "scale_deployment"
            }

        # 5. Pending Pod Correlation
        if pod_status == "Pending":
            return {
                "failure_category": FailureCategory.PENDING_POD,
                "incident_type": "PendingPod",
                "severity": "Medium",
                "certainty": 0.88,
                "confidence_level": "MEDIUM",
                "probable_cause": f"Pod '{pod_name}' is stuck in Pending phase waiting for volumes, admission controllers, or node binding.",
                "supporting_evidence": [
                    f"Pod phase: '{pod_status}'",
                    f"Container waiting reason: '{waiting_reason}'"
                ],
                "recommendation": "Inspect pod volume claims, storage classes, and cluster events.",
                "suggested_action": "inspect_diagnostics"
            }

        # 6. Readiness Probe Failure Correlation
        if ("readiness probe failed" in event_str or 
            "unhealthy readiness probe" in event_str or 
            (pod_status == "Running" and not is_ready and "readiness" in event_str)):
            
            return {
                "failure_category": FailureCategory.READINESS_PROBE_FAILURE,
                "incident_type": "ReadinessProbeFailure",
                "severity": "High",
                "certainty": 0.90,
                "confidence_level": "HIGH",
                "probable_cause": f"Container readiness probe failed for pod '{pod_name}'. Traffic cannot be routed to this instance.",
                "supporting_evidence": [
                    f"Pod ready status: {is_ready}",
                    f"Readiness events: {[e.get('message') for e in events if 'unhealthy' in e.get('reason', '').lower() or 'probe' in e.get('message', '').lower()]}"
                ],
                "recommendation": "Check application health endpoint and dependent services (e.g. database connectivity).",
                "suggested_action": "restart_deployment"
            }

        # 7. Liveness Probe Failure Correlation
        if ("liveness probe failed" in event_str or 
            "unhealthy liveness probe" in event_str or 
            (restarts > 0 and "liveness" in event_str)):
            
            return {
                "failure_category": FailureCategory.LIVENESS_PROBE_FAILURE,
                "incident_type": "LivenessProbeFailure",
                "severity": "Critical",
                "certainty": 0.90,
                "confidence_level": "HIGH",
                "probable_cause": f"Container liveness probe failed for pod '{pod_name}', causing Kubelet to restart the container.",
                "supporting_evidence": [
                    f"Restart count: {restarts}",
                    f"Liveness events: {[e.get('message') for e in events if 'liveness' in e.get('message', '').lower()]}"
                ],
                "recommendation": "Verify application health check response times and adjust liveness probe timeouts.",
                "suggested_action": "restart_deployment"
            }

        # 8. CrashLoopBackOff Correlation
        if (pod_status in ["CrashLoopBackOff", "Error", "Failed"] or 
            waiting_reason == "CrashLoopBackOff" or 
            (restarts > 0 and last_exit_code > 0)):
            
            return {
                "failure_category": FailureCategory.CRASH_LOOP_BACKOFF,
                "incident_type": "CrashLoopBackOff",
                "severity": "Critical",
                "certainty": 0.94,
                "confidence_level": "HIGH",
                "probable_cause": f"Pod '{pod_name}' is crashing repeatedly (Restarts: {restarts}, Last Exit Code: {last_exit_code}, Reason: {last_state_reason}).",
                "supporting_evidence": [
                    f"Pod phase: '{pod_status}'",
                    f"Restarts: {restarts}",
                    f"Last exit code: {last_exit_code}",
                    f"Container state reason: '{last_state_reason}'"
                ],
                "recommendation": "Inspect container crash logs, startup scripts, and verify database connectivity.",
                "suggested_action": "restart_deployment"
            }

        # 9. High Restart Count Correlation
        if restarts >= 5 or evidence.get("total_restarts_count", 0) >= 10:
            return {
                "failure_category": FailureCategory.HIGH_RESTART_COUNT,
                "incident_type": "HighRestartCount",
                "severity": "High",
                "certainty": 0.88,
                "confidence_level": "HIGH",
                "probable_cause": f"Workload '{pod_name}' has accumulated an abnormally high restart count ({restarts} restarts), indicating runtime instability.",
                "supporting_evidence": [
                    f"Workload restart count: {restarts}",
                    f"Namespace total restarts: {evidence.get('total_restarts_count', 0)}"
                ],
                "recommendation": "Investigate application logs for unhandled exceptions and transient errors.",
                "suggested_action": "restart_deployment"
            }

        # 10. Deployment Unavailable Correlation
        if deployment:
            desired = deployment.get("replicas", 0)
            ready = deployment.get("ready_replicas", 0)
            if desired > 0 and ready == 0:
                return {
                    "failure_category": FailureCategory.DEPLOYMENT_UNAVAILABLE,
                    "incident_type": "DeploymentUnavailable",
                    "severity": "Critical",
                    "certainty": 0.95,
                    "confidence_level": "HIGH",
                    "probable_cause": f"Deployment '{deployment.get('name')}' is completely unavailable (0/{desired} replicas ready).",
                    "supporting_evidence": [
                        f"Desired replicas: {desired}",
                        f"Ready replicas: {ready}"
                    ],
                    "recommendation": "Inspect deployment rollout status, replicasets, and underlying pod conditions.",
                    "suggested_action": "restart_deployment"
                }

        # 11. ArgoCD Sync Failure Correlation
        if argocd and argocd.get("sync_status") in ["Failed", "Error"]:
            return {
                "failure_category": FailureCategory.ARGOCD_SYNC_FAILURE,
                "incident_type": "ArgoCDSyncFailure",
                "severity": "High",
                "certainty": 0.92,
                "confidence_level": "HIGH",
                "probable_cause": f"ArgoCD sync failed for application '{argocd.get('name')}'. GitOps reconciliation error.",
                "supporting_evidence": [
                    f"ArgoCD sync status: {argocd.get('sync_status')}",
                    f"ArgoCD health status: {argocd.get('health_status')}",
                    f"Target revision: {argocd.get('revision')}"
                ],
                "recommendation": "Inspect Helm chart syntax errors and re-trigger ArgoCD sync.",
                "suggested_action": "sync_argocd"
            }

        # 12. ArgoCD OutOfSync Correlation
        if argocd and argocd.get("sync_status") in ["OutOfSync", "Degraded"]:
            return {
                "failure_category": FailureCategory.ARGOCD_OUT_OF_SYNC,
                "incident_type": "ArgoCDOutOfSync",
                "severity": "Warning",
                "certainty": 0.90,
                "confidence_level": "HIGH",
                "probable_cause": f"ArgoCD application '{argocd.get('name')}' is OutOfSync with Git repository revision '{argocd.get('revision', 'HEAD')}'.",
                "supporting_evidence": [
                    f"ArgoCD sync status: {argocd.get('sync_status')}",
                    f"ArgoCD health: {argocd.get('health_status')}"
                ],
                "recommendation": "Synchronize ArgoCD application to reconcile live cluster state with Git.",
                "suggested_action": "sync_argocd"
            }

        # 13. High CPU Load Correlation
        if prom and prom.get("cpu_utilization", 0) > 80.0:
            return {
                "failure_category": FailureCategory.HIGH_CPU,
                "incident_type": "HighCPU",
                "severity": "Warning",
                "certainty": 0.85,
                "confidence_level": "MEDIUM",
                "probable_cause": f"Cluster CPU utilization is severely elevated at {prom['cpu_utilization']}%.",
                "supporting_evidence": [
                    f"Prometheus CPU Gauge: {prom['cpu_utilization']}%",
                    f"Prometheus Status: {evidence.get('prometheus_status', 'REAL_TELEMETRY')}"
                ],
                "recommendation": "Scale deployment replicas horizontally to distribute workload load.",
                "suggested_action": "scale_deployment"
            }

        # 14. High Memory Load Correlation
        if prom and prom.get("memory_utilization", 0) > 85.0:
            return {
                "failure_category": FailureCategory.HIGH_MEMORY,
                "incident_type": "HighMemory",
                "severity": "Warning",
                "certainty": 0.85,
                "confidence_level": "MEDIUM",
                "probable_cause": f"Cluster Memory utilization is dangerously high at {prom['memory_utilization']}%, risking kernel OOM evictions.",
                "supporting_evidence": [
                    f"Prometheus Memory Gauge: {prom['memory_utilization']}%",
                    f"Prometheus Status: {evidence.get('prometheus_status', 'REAL_TELEMETRY')}"
                ],
                "recommendation": "Scale down idle workloads or expand node memory capacity.",
                "suggested_action": "scale_deployment"
            }

        # 15. GitOps Configuration Mismatch Correlation
        git_desired = evidence.get("git_desired_replicas")
        if git_desired is not None and deployment:
            current_replicas = deployment.get("replicas")
            if current_replicas is not None and current_replicas != git_desired:
                return {
                    "failure_category": FailureCategory.GITOPS_CONFIG_MISMATCH,
                    "incident_type": "GitOpsConfigMismatch",
                    "severity": "Warning",
                    "certainty": 0.90,
                    "confidence_level": "HIGH",
                    "probable_cause": f"GitOps configuration mismatch: Git repository declares {git_desired} replicas, but live cluster has {current_replicas}.",
                    "supporting_evidence": [
                        f"Git desired replicas: {git_desired}",
                        f"Live cluster replicas: {current_replicas}"
                    ],
                    "recommendation": "Reconcile live deployment with GitOps source of truth.",
                    "suggested_action": "sync_argocd"
                }

        # 16. Healthy Workload Default
        return {
            "failure_category": FailureCategory.HEALTHY_WORKLOAD,
            "incident_type": "HealthyWorkload",
            "severity": "Info",
            "certainty": 1.0,
            "confidence_level": "HIGH",
            "probable_cause": f"Workload '{pod_name}' in namespace '{evidence.get('namespace', 'devops-nexus-prod')}' is healthy and operating within normal parameters.",
            "supporting_evidence": [
                f"Pod phase: '{pod_status}'",
                f"Ready replicas: {deployment.get('ready_replicas', 1) if deployment else 1}",
                f"ArgoCD status: {argocd.get('sync_status', 'Synced') if argocd else 'Synced'}"
            ],
            "recommendation": "No remediation required. All health probes and metrics are normal.",
            "suggested_action": None
        }

root_cause_engine = RootCauseEngine()
