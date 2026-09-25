# --- Phase 3 GitOps Control Plane & Verification Unit Tests ---
import os
import pytest
from unittest.mock import patch, MagicMock
from app.agent.gitops.models import GitOpsStage, GitOpsOwnership, GitChangePreview
from app.agent.gitops.ownership import gitops_ownership_resolver, GitOpsOwnershipResolver
from app.agent.gitops.change_engine import git_change_engine, GitChangeEngine
from app.agent.gitops.workflow import gitops_workflow, GitOpsWorkflowEngine
from app.agent.action_planner import action_planner
from app.agent.verification_engine import verification_engine
from app.agent.agent_runtime import agent_runtime
from app.agent.tools import tool_registry

class TestGitOpsOwnershipResolution:
    def test_resolve_gitops_ownership_auth_service(self):
        ownership = gitops_ownership_resolver.resolve_ownership(
            namespace="devops-nexus-prod",
            name="auth-service"
        )
        assert ownership.is_gitops is True
        assert ownership.target_name == "auth-service"
        assert ownership.helm_chart_path == "helm/auth"
        assert len(ownership.values_files) > 0
        assert ownership.target_values_file is not None

    def test_resolve_gitops_ownership_app_alias(self):
        ownership = gitops_ownership_resolver.resolve_ownership(
            namespace="devops-nexus-prod",
            name="auth-prod"
        )
        assert ownership.is_gitops is True
        assert ownership.helm_chart_path == "helm/auth"

    def test_resolve_non_gitops_workload(self):
        ownership = gitops_ownership_resolver.resolve_ownership(
            namespace="custom-namespace",
            name="non-existent-legacy-app"
        )
        assert ownership.is_gitops is False
        assert ownership.target_values_file is None


class TestGitChangeEngine:
    def test_read_desired_state(self):
        ownership = gitops_ownership_resolver.resolve_ownership("devops-nexus-prod", "auth-service")
        assert ownership.target_values_file is not None
        state = git_change_engine.read_desired_state(ownership.target_values_file)
        assert "replicaCount" in state
        assert isinstance(state["replicaCount"], int)

    def test_generate_scale_preview_and_diff(self):
        ownership = gitops_ownership_resolver.resolve_ownership("devops-nexus-prod", "auth-service")
        preview = git_change_engine.generate_scale_preview(
            ownership=ownership,
            new_replicas=5,
            environment="Amazon EKS",
            cluster="production-eks"
        )
        assert isinstance(preview, GitChangePreview)
        assert preview.requested_replicas == 5
        assert preview.is_valid_yaml is True
        assert "replicaCount" in preview.diff
        assert preview.gitops_enabled is True

    def test_invalid_replica_count_rejected(self):
        ownership = gitops_ownership_resolver.resolve_ownership("devops-nexus-prod", "auth-service")
        with pytest.raises(ValueError):
            git_change_engine.generate_scale_preview(ownership=ownership, new_replicas=-1)
        with pytest.raises(ValueError):
            git_change_engine.generate_scale_preview(ownership=ownership, new_replicas=105)

    def test_yaml_validation_on_syntax_error(self):
        ownership = gitops_ownership_resolver.resolve_ownership("devops-nexus-prod", "auth-service")
        preview = git_change_engine.generate_scale_preview(ownership, 4)
        preview.is_valid_yaml = False
        res = git_change_engine.apply_commit_and_push(preview)
        assert res.success is False
        assert "invalid YAML" in res.error


class TestGitOpsWorkflowEngine:
    def test_preview_scale_endpoint(self):
        preview_data = gitops_workflow.preview_scale(
            namespace="devops-nexus-prod",
            name="auth-service",
            replicas=6
        )
        assert preview_data["is_gitops"] is True
        assert preview_data["preview"]["requested_replicas"] == 6
        assert preview_data["risk"]["risk_level"] == "MEDIUM"

    def test_execute_scale_gitops_success(self):
        res = gitops_workflow.execute_scale(
            namespace="devops-nexus-prod",
            name="auth-service",
            replicas=4,
            confirm_token="CONFIRM"
        )
        assert res["is_gitops"] is True
        assert res["success"] is True
        assert res["stage"] == GitOpsStage.COMPLETED.value
        assert len(res["steps"]) >= 5
        assert res["verification"]["verified"] is True

    def test_execute_scale_requires_confirmation_token(self):
        # Without confirm_token, high/medium risk should require confirmation if policy triggers
        with patch("app.agent.risk_policy.risk_policy_engine.evaluate_risk", return_value={"requires_confirm_token": True, "risk_level": "HIGH", "requires_approval": True}):
            res = gitops_workflow.execute_scale(
                namespace="devops-nexus-prod",
                name="auth-service",
                replicas=8,
                confirm_token=None
            )
            assert res["stage"] == GitOpsStage.AWAITING_APPROVAL.value
            assert res["success"] is False
            assert "confirmation token" in res["message"]

    def test_execute_scale_non_gitops_workload(self):
        with patch("app.clients.kubernetes.k8s_client.scale_deployment", return_value=MagicMock()):
            res = gitops_workflow.execute_scale(
                namespace="legacy-ns",
                name="standalone-workload",
                replicas=3
            )
            assert res["is_gitops"] is False
            assert res["success"] is True
            assert res["stage"] == GitOpsStage.COMPLETED.value
            assert "non-GitOps" in res["message"]


class TestVerificationEngineIntegration:
    def test_verification_success_all_aligned(self):
        before = {
            "timestamp": 1000.0,
            "target_resource": "auth-service",
            "namespace": "devops-nexus-prod",
            "running_pods": 3,
            "ready_pods": 3,
            "argocd_sync": "Synced",
            "argocd_health": "Healthy"
        }
        with patch.object(verification_engine, 'capture_state_snapshot') as mock_snap:
            mock_snap.return_value = {
                "timestamp": 1010.0,
                "target_resource": "auth-service",
                "namespace": "devops-nexus-prod",
                "running_pods": 5,
                "ready_pods": 5,
                "total_pods": 5,
                "deployment_ready_replicas": 5,
                "git_desired_replicas": 5,
                "argocd_sync": "Synced",
                "argocd_health": "Healthy"
            }
            res = verification_engine.verify_action_execution(
                target_resource="auth-service",
                action_type="scale_deployment",
                before_snapshot=before,
                expected_params={"replicas": 5}
            )
            assert res["verified"] is True
            assert res["git_verified"] is True
            assert res["k8s_verified"] is True
            assert res["argocd_verified"] is True
            assert "VERIFIED_SUCCESS" in res["verification_summary"]

    def test_verification_failure_on_desync(self):
        before = {"timestamp": 1000.0}
        with patch.object(verification_engine, 'capture_state_snapshot') as mock_snap:
            mock_snap.return_value = {
                "timestamp": 1010.0,
                "target_resource": "auth-service",
                "namespace": "devops-nexus-prod",
                "running_pods": 1,
                "ready_pods": 1,
                "total_pods": 1,
                "deployment_ready_replicas": 1,
                "git_desired_replicas": 5,
                "argocd_sync": "OutOfSync",
                "argocd_health": "Degraded"
            }
            res = verification_engine.verify_action_execution(
                target_resource="auth-service",
                action_type="scale_deployment",
                before_snapshot=before,
                expected_params={"replicas": 5}
            )
            assert res["verified"] is False
            assert res["argocd_verified"] is False
            assert "VERIFICATION_FAILED" in res["verification_summary"]


class TestAgentActionPlanGitOpsIntegration:
    def test_action_planner_creates_gitops_preview(self):
        target = {
            "environment": "Amazon EKS",
            "cluster_id": "production-eks",
            "namespace": "devops-nexus-prod",
            "resource_name": "auth-service",
            "resource_kind": "deployment"
        }
        plan = action_planner.create_action_plan(
            intent="REMEDIATION",
            target_info=target,
            action_type="scale_deployment",
            parameters={"replicas": 5}
        )
        assert plan["target"]["gitops_managed"] is True
        assert plan["change_preview"] is not None
        assert plan["change_preview"]["requested_replicas"] == 5
        assert len(plan["steps"]) == 7
        assert any("ArgoCD" in s["label"] for s in plan["steps"])

    def test_agent_tool_registry_executes_scale_tool(self):
        user_admin = {"username": "admin", "role": "Administrator"}
        result = tool_registry.execute(
            tool_name="k8s.scale_deployment",
            input_data={
                "namespace": "devops-nexus-prod",
                "name": "auth-service",
                "replicas": 3
            },
            user_info=user_admin,
            confirm_token="CONFIRM"
        )
        assert result.status.value == "SUCCESS"
        assert result.data["is_gitops"] is True
        assert result.data["success"] is True
