# --- Risk Policy Engine Foundation ---
from enum import Enum
from typing import Dict, Any, Optional, List

class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RiskPolicyEngine:
    """Evaluates risk levels and approval requirements for infrastructure operational actions."""

    ACTION_RISK_MAP = {
        # READ_ONLY Actions
        "list_pods": RiskLevel.READ_ONLY,
        "get_pod": RiskLevel.READ_ONLY,
        "get_logs": RiskLevel.READ_ONLY,
        "get_metrics": RiskLevel.READ_ONLY,
        "get_events": RiskLevel.READ_ONLY,
        "inspect_context": RiskLevel.READ_ONLY,
        "copilot_investigate": RiskLevel.READ_ONLY,
        
        # LOW Risk Actions
        "restart_pod": RiskLevel.LOW,
        "restart_deployment": RiskLevel.LOW,
        "restart": RiskLevel.LOW,
        "refresh_argocd": RiskLevel.LOW,
        "collect_logs": RiskLevel.READ_ONLY,
        "verify_manifest": RiskLevel.READ_ONLY,
        "verify_pods": RiskLevel.READ_ONLY,

        # MEDIUM Risk Actions
        "scale_deployment": RiskLevel.MEDIUM,
        "scale": RiskLevel.MEDIUM,
        "trigger_rollout": RiskLevel.MEDIUM,
        "sync_argocd": RiskLevel.MEDIUM,
        "sync": RiskLevel.MEDIUM,
        "rollback_deployment": RiskLevel.MEDIUM,
        "rollback": RiskLevel.MEDIUM,

        # HIGH Risk Actions
        "delete_deployment": RiskLevel.HIGH,
        "delete_pod": RiskLevel.HIGH,
        "modify_gitops_values": RiskLevel.HIGH,
        "patch_config": RiskLevel.HIGH,
        "execute_destructive": RiskLevel.HIGH,

        # CRITICAL Risk Actions
        "delete_namespace": RiskLevel.CRITICAL,
        "delete_cluster": RiskLevel.CRITICAL,
        "disconnect_gitops": RiskLevel.CRITICAL,
        "modify_iam": RiskLevel.CRITICAL
    }

    def evaluate_risk(
        self,
        action_type: str,
        target_resource: str,
        namespace: str = "devops-nexus-prod",
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluates operational risk level, approval requirement, and required confirmation tokens."""
        
        clean_action = action_type.lower().strip()
        risk_level = self.ACTION_RISK_MAP.get(clean_action, RiskLevel.MEDIUM)

        # Elevate risk if targeting production namespace with destructive operations
        if namespace in ["prod", "production", "devops-nexus-prod"] and risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]:
            if clean_action in ["scale_deployment", "scale"]:
                replicas = (parameters or {}).get("replicas", 1)
                if replicas == 0:
                    risk_level = RiskLevel.HIGH

        requires_approval = risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        requires_confirm_token = risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

        return {
            "action_type": action_type,
            "target_resource": target_resource,
            "namespace": namespace,
            "risk_level": risk_level.value,
            "requires_approval": requires_approval,
            "requires_confirm_token": requires_confirm_token,
            "confirm_token_expected": "CONFIRM" if requires_confirm_token else None,
            "policy_passed": True
        }

risk_policy_engine = RiskPolicyEngine()
