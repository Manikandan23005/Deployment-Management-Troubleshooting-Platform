# --- Dedicated Remediation Planning Layer ---
import uuid
import datetime
from typing import Dict, Any, Optional, List
from app.agent.models import (
    RemediationPlan, 
    RemediationAction, 
    ScopeContext, 
    FailureCategory
)
from app.agent.risk_policy import risk_policy_engine, RiskLevel
from app.agent.gitops.ownership import gitops_ownership_resolver
from app.core.logging import logger

class RemediationPlanner:
    """Generates deterministic, idempotent remediation plans mapped to strongly-typed ToolRegistry operations."""

    def build_plan(
        self,
        incident_id: str,
        target_scope: ScopeContext,
        diagnosis: Dict[str, Any],
        evidence: Dict[str, Any],
        user_intent: Optional[str] = None
    ) -> Optional[RemediationPlan]:
        """Synthesizes a concrete RemediationPlan from target scope, diagnosis, and evidence graph."""
        
        failure_cat = diagnosis.get("failure_category", FailureCategory.HEALTHY_WORKLOAD)
        if isinstance(failure_cat, str):
            try:
                failure_cat = FailureCategory(failure_cat)
            except ValueError:
                failure_cat = FailureCategory.UNKNOWN_FAILURE

        # If workload is healthy, no remediation is generated
        if failure_cat == FailureCategory.HEALTHY_WORKLOAD:
            return None

        resource_name = target_scope.application or target_scope.workload or "auth-service"
        namespace = target_scope.namespace
        cluster_id = target_scope.cluster_id
        environment = target_scope.environment

        # Resolve GitOps ownership
        ownership = gitops_ownership_resolver.resolve_ownership(
            namespace=namespace,
            name=resource_name,
            cluster_id=cluster_id
        )

        actions: List[RemediationAction] = []
        change_preview: Optional[Dict[str, Any]] = None
        expected_effect = ""
        verification_plan: Dict[str, Any] = {}
        rollback_plan: Optional[Dict[str, Any]] = None

        # 1. CrashLoopBackOff / Readiness / Liveness / HighRestartCount / DeploymentUnavailable -> Rollout Restart
        if failure_cat in [
            FailureCategory.CRASH_LOOP_BACKOFF,
            FailureCategory.READINESS_PROBE_FAILURE,
            FailureCategory.LIVENESS_PROBE_FAILURE,
            FailureCategory.HIGH_RESTART_COUNT,
            FailureCategory.DEPLOYMENT_UNAVAILABLE
        ]:
            expected_effect = f"Recreate pods for deployment '{resource_name}' to clear corrupted container memory and re-establish network connection pools."
            verification_plan = {
                "check_pods_ready": True,
                "expected_running_pods_min": 1,
                "timeout_seconds": 60,
                "target_resource": resource_name,
                "namespace": namespace
            }
            rollback_plan = {
                "action": "escalate_to_operator",
                "message": f"Rollout restart of '{resource_name}' failed to achieve ready status. Manual operator intervention required."
            }

            risk_eval = risk_policy_engine.evaluate_risk(
                action_type="restart_deployment",
                target_resource=resource_name,
                namespace=namespace
            )

            actions.append(RemediationAction(
                tool_name="k8s.restart_deployment",
                inputs={"name": resource_name, "namespace": namespace, "cluster_id": cluster_id},
                risk_level=risk_eval["risk_level"],
                requires_confirmation=risk_eval["requires_confirm_token"],
                expected_effect=expected_effect,
                verification_plan=verification_plan,
                rollback_plan=rollback_plan
            ))

        # 2. ArgoCD OutOfSync / SyncFailure / GitOpsConfigMismatch -> ArgoCD Sync
        elif failure_cat in [
            FailureCategory.ARGOCD_OUT_OF_SYNC,
            FailureCategory.ARGOCD_SYNC_FAILURE,
            FailureCategory.GITOPS_CONFIG_MISMATCH
        ]:
            app_name = ownership.argocd_app_name or resource_name
            expected_effect = f"Trigger ArgoCD reconciliation sync on application '{app_name}' to match live state with Git."
            verification_plan = {
                "check_argocd_synced": True,
                "expected_sync_status": "Synced",
                "expected_health_status": "Healthy",
                "target_app": app_name
            }
            rollback_plan = {
                "action": "refresh_argocd_app",
                "message": f"ArgoCD sync failed for '{app_name}'. Refreshing repository index."
            }

            risk_eval = risk_policy_engine.evaluate_risk(
                action_type="sync_argocd",
                target_resource=app_name,
                namespace=namespace
            )

            # Idempotency check: If ArgoCD is already Synced in evidence, skip redundant sync
            argocd_evidence = evidence.get("argocd") or {}
            if argocd_evidence.get("sync_status") == "Synced" and failure_cat != FailureCategory.GITOPS_CONFIG_MISMATCH:
                expected_effect = f"ArgoCD application '{app_name}' is already Synced. Triggering cache refresh instead."
                actions.append(RemediationAction(
                    tool_name="argocd.refresh_application",
                    inputs={"name": app_name, "cluster_id": cluster_id},
                    risk_level=RiskLevel.LOW,
                    requires_confirmation=False,
                    expected_effect=expected_effect,
                    verification_plan=verification_plan
                ))
            else:
                actions.append(RemediationAction(
                    tool_name="argocd.sync_application",
                    inputs={"name": app_name, "cluster_id": cluster_id, "prune": False},
                    risk_level=risk_eval["risk_level"],
                    requires_confirmation=risk_eval["requires_confirm_token"],
                    expected_effect=expected_effect,
                    verification_plan=verification_plan,
                    rollback_plan=rollback_plan
                ))

        # 3. HighCPU / HighMemory / FailedScheduling -> Scale Workload
        elif failure_cat in [
            FailureCategory.HIGH_CPU,
            FailureCategory.HIGH_MEMORY,
            FailureCategory.FAILED_SCHEDULING
        ]:
            dep_evidence = evidence.get("deployment") or {}
            current_replicas = dep_evidence.get("replicas", 2) or 2
            target_replicas = current_replicas + 1

            expected_effect = f"Scale deployment '{resource_name}' from {current_replicas} to {target_replicas} replicas to distribute resource pressure."
            verification_plan = {
                "check_desired_replicas": target_replicas,
                "check_pods_ready": True,
                "timeout_seconds": 60,
                "target_resource": resource_name,
                "namespace": namespace
            }
            rollback_plan = {
                "action": "scale_deployment",
                "parameters": {"replicas": current_replicas},
                "message": f"Scaling failed. Rollback to previous replica count {current_replicas}."
            }

            if ownership.is_gitops:
                from app.agent.gitops.change_engine import git_change_engine
                try:
                    preview_obj = git_change_engine.generate_scale_preview(
                        ownership=ownership,
                        new_replicas=target_replicas,
                        environment=environment,
                        cluster=cluster_id
                    )
                    change_preview = preview_obj.model_dump()
                except Exception as e:
                    logger.debug(f"Remediation preview generation error: {str(e)}")

            risk_eval = risk_policy_engine.evaluate_risk(
                action_type="scale_deployment",
                target_resource=resource_name,
                namespace=namespace,
                parameters={"replicas": target_replicas}
            )

            tool_name = "k8s.scale_deployment"
            actions.append(RemediationAction(
                tool_name=tool_name,
                inputs={"name": resource_name, "namespace": namespace, "replicas": target_replicas, "cluster_id": cluster_id},
                risk_level=risk_eval["risk_level"],
                requires_confirmation=risk_eval["requires_confirm_token"],
                expected_effect=expected_effect,
                verification_plan=verification_plan,
                rollback_plan=rollback_plan
            ))

        # 4. ImagePullBackOff / ErrImagePull -> GitOps Rollback / Image Correction
        elif failure_cat in [
            FailureCategory.IMAGE_PULL_BACKOFF,
            FailureCategory.ERR_IMAGE_PULL
        ]:
            expected_effect = f"Revert invalid container image reference for '{resource_name}' to previous stable Git revision."
            verification_plan = {
                "check_image_pull_resolved": True,
                "check_pods_ready": True,
                "timeout_seconds": 60,
                "target_resource": resource_name,
                "namespace": namespace
            }
            rollback_plan = {
                "action": "escalate_to_operator",
                "message": "Invalid container image tag requires developer code fix in repository."
            }

            risk_eval = risk_policy_engine.evaluate_risk(
                action_type="git_push",
                target_resource=resource_name,
                namespace=namespace
            )

            actions.append(RemediationAction(
                tool_name="argocd.refresh_application",
                inputs={"name": ownership.argocd_app_name or resource_name, "cluster_id": cluster_id},
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                expected_effect=expected_effect,
                verification_plan=verification_plan,
                rollback_plan=rollback_plan
            ))

        # 5. OOMKilled -> Suggest Memory Limits Adjustment
        elif failure_cat == FailureCategory.OOM_KILLED:
            expected_effect = f"Restart '{resource_name}' and notify operator to increase Helm memory limits."
            verification_plan = {
                "check_pods_ready": True,
                "target_resource": resource_name,
                "namespace": namespace
            }
            risk_eval = risk_policy_engine.evaluate_risk(
                action_type="restart_deployment",
                target_resource=resource_name,
                namespace=namespace
            )
            actions.append(RemediationAction(
                tool_name="k8s.restart_deployment",
                inputs={"name": resource_name, "namespace": namespace, "cluster_id": cluster_id},
                risk_level=risk_eval["risk_level"],
                requires_confirmation=risk_eval["requires_confirm_token"],
                expected_effect=expected_effect,
                verification_plan=verification_plan
            ))

        else:
            # Generic safe diagnostics / refresh
            expected_effect = f"Refresh application state and collect real-time status for '{resource_name}'."
            verification_plan = {"check_resource_exists": True, "target_resource": resource_name}
            actions.append(RemediationAction(
                tool_name="k8s.get_pod",
                inputs={"name": resource_name, "namespace": namespace, "cluster_id": cluster_id},
                risk_level=RiskLevel.LOW,
                requires_confirmation=False,
                expected_effect=expected_effect,
                verification_plan=verification_plan
            ))

        if not actions:
            return None

        # Determine overall plan risk
        highest_risk = RiskLevel.LOW
        any_confirm = False
        for a in actions:
            if a.risk_level == RiskLevel.HIGH:
                highest_risk = RiskLevel.HIGH
                any_confirm = True
            elif a.risk_level == RiskLevel.MEDIUM and highest_risk != RiskLevel.HIGH:
                highest_risk = RiskLevel.MEDIUM
                if a.requires_confirmation:
                    any_confirm = True

        plan = RemediationPlan(
            incident_id=incident_id,
            target=target_scope,
            diagnosis=diagnosis,
            actions=actions,
            risk_level=highest_risk,
            requires_confirmation=any_confirm,
            expected_effect=expected_effect,
            verification_plan=verification_plan,
            rollback_plan=rollback_plan,
            status="AWAITING_APPROVAL" if any_confirm else "PLAN_GENERATED",
            change_preview=change_preview
        )

        return plan

remediation_planner = RemediationPlanner()
