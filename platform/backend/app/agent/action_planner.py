# --- Structured Action Planner ---
import uuid
import datetime
from typing import Dict, Any, Optional, List
from app.agent.risk_policy import risk_policy_engine, RiskLevel
from app.agent.gitops.ownership import gitops_ownership_resolver

class ActionPlanner:
    """Generates structured, validated infrastructure action plans with GitOps awareness and change previews."""

    def create_action_plan(
        self,
        intent: str,
        target_info: Dict[str, Any],
        action_type: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generates a structured action plan with target scoping, GitOps change preview, risk evaluation, and step sequence."""
        
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        params = parameters or {}

        target_resource = target_info.get("resource_name") or "auth-service"
        namespace = target_info.get("namespace") or "devops-nexus-prod"
        cluster_id = target_info.get("cluster_id") or "default"
        environment = target_info.get("environment") or "On-Premises"

        # Resolve GitOps Ownership
        ownership = gitops_ownership_resolver.resolve_ownership(namespace, target_resource, cluster_id=cluster_id)

        risk_eval = risk_policy_engine.evaluate_risk(
            action_type=action_type,
            target_resource=target_resource,
            namespace=namespace,
            parameters=params
        )

        steps: List[Dict[str, Any]] = []
        change_preview: Optional[Dict[str, Any]] = None

        if action_type in ["scale_deployment", "scale"]:
            replicas = params.get("replicas", 3)
            if ownership.is_gitops:
                from app.agent.gitops.change_engine import git_change_engine
                try:
                    preview_obj = git_change_engine.generate_scale_preview(
                        ownership=ownership,
                        new_replicas=replicas,
                        environment=environment,
                        cluster=cluster_id
                    )
                    change_preview = preview_obj.model_dump()
                except Exception:
                    change_preview = None

                steps = [
                    {"step_index": 1, "action": "resolve_ownership", "label": f"Verify GitOps ownership ({ownership.argocd_app_name})", "status": "pending"},
                    {"step_index": 2, "action": "stage_git_change", "label": f"Stage replica change ({replicas} replicas) in {ownership.helm_chart_path}", "status": "pending"},
                    {"step_index": 3, "action": "validate_yaml", "label": "Validate Helm values YAML syntax & diff", "status": "pending"},
                    {"step_index": 4, "action": "commit_and_push", "label": f"Commit desired state & push to branch '{ownership.branch}'", "status": "pending"},
                    {"step_index": 5, "action": "argocd_sync", "label": f"Trigger ArgoCD refresh & sync on application '{ownership.argocd_app_name}'", "status": "pending"},
                    {"step_index": 6, "action": "reconcile_rollout", "label": "Wait for Kubernetes controller reconciliation & pod rollout", "status": "pending"},
                    {"step_index": 7, "action": "verify_state", "label": f"Verify all {replicas} pods are healthy and ArgoCD is Synced", "status": "pending"}
                ]
            else:
                steps = [
                    {"step_index": 1, "action": "inspect_desired_state", "label": f"Check target replica count requirement ({replicas})", "status": "pending"},
                    {"step_index": 2, "action": "modify_state", "label": f"Directly scale deployment {target_resource} to {replicas} replicas", "status": "pending"},
                    {"step_index": 3, "action": "verify_replicas", "label": f"Verify all {replicas} pods are ready", "status": "pending"}
                ]

        elif action_type in ["restart_deployment", "restart"]:
            steps = [
                {"step_index": 1, "action": "collect_logs", "label": f"Collect pre-restart logs for {target_resource}", "status": "pending"},
                {"step_index": 2, "action": "verify_manifest", "label": f"Verify deployment manifest & configmaps in {namespace}", "status": "pending"},
                {"step_index": 3, "action": "execute_restart", "label": f"Trigger rollout restart on deployment {target_resource}", "status": "pending"},
                {"step_index": 4, "action": "verify_pods", "label": f"Verify new pods status & health in {namespace}", "status": "pending"}
            ]

        elif action_type in ["sync_argocd", "sync"]:
            steps = [
                {"step_index": 1, "action": "fetch_git_revision", "label": f"Fetch latest Git commit revision for {target_resource}", "status": "pending"},
                {"step_index": 2, "action": "trigger_sync", "label": f"Execute ArgoCD sync for application {target_resource}", "status": "pending"},
                {"step_index": 3, "action": "verify_gitops", "label": f"Verify ArgoCD Synced and Healthy status", "status": "pending"}
            ]
        else:
            steps = [
                {"step_index": 1, "action": "collect_diagnostics", "label": f"Collect diagnostics for {target_resource}", "status": "pending"},
                {"step_index": 2, "action": "execute_action", "label": f"Execute {action_type} on {target_resource}", "status": "pending"},
                {"step_index": 3, "action": "verify_health", "label": f"Verify health of {target_resource}", "status": "pending"}
            ]

        requires_approval = risk_eval["requires_approval"]
        requires_confirm = risk_eval["requires_confirm_token"]

        structured_plan = {
            "plan_id": plan_id,
            "created_at": now,
            "intent": intent,
            "target": {
                "environment": environment,
                "cluster": cluster_id,
                "namespace": namespace,
                "application": target_resource,
                "resource_kind": target_info.get("resource_kind", "deployment"),
                "gitops_managed": ownership.is_gitops,
                "argocd_app": ownership.argocd_app_name,
                "repo_url": ownership.repo_url
            },
            "action": {
                "type": action_type,
                "parameters": params
            },
            "risk": risk_eval["risk_level"],
            "requires_approval": requires_approval,
            "requires_confirmation": requires_confirm,
            "confirm_token_expected": risk_eval["confirm_token_expected"],
            "status": "AWAITING_APPROVAL" if (requires_approval or requires_confirm) else "PLANNED",
            "change_preview": change_preview,
            "steps": steps,
            "execution_log": []
        }

        return structured_plan

action_planner = ActionPlanner()
