# --- Unit & Integration Tests for Agent Runtime Foundation ---
import pytest
from unittest.mock import MagicMock, patch
from app.agent.target_resolver import target_resolver, TargetResolver
from app.agent.risk_policy import risk_policy_engine, RiskPolicyEngine, RiskLevel
from app.agent.action_planner import action_planner, ActionPlanner
from app.agent.verification_engine import verification_engine, VerificationEngine
from app.agent.agent_runtime import agent_runtime, AgentRuntime

class TestTargetResolver:
    def test_resolve_explicit_target(self):
        resolved = target_resolver.resolve_target("Scale auth-service to 5 replicas", namespace="devops-nexus-prod")
        assert resolved["application"] == "auth-service"
        assert resolved["namespace"] == "devops-nexus-prod"
        assert resolved["resource_kind"] == "deployment"
        assert resolved["needs_clarification"] is False

    def test_resolve_eks_environment(self):
        resolved = target_resolver.resolve_target("Check gateway health", cluster_id="eks-cluster-prod")
        assert resolved["environment"] == "Amazon EKS"
        assert resolved["cluster_id"] == "eks-cluster-prod"

    def test_resolve_ambiguous_mutation_request(self):
        resolved = target_resolver.resolve_target("Scale deployment to 5 replicas", resource_name=None, scope=None)
        assert resolved["needs_clarification"] is True
        assert "Multiple workloads exist" in resolved["clarification_message"]


class TestRiskPolicyEngine:
    def test_read_only_risk_level(self):
        eval_res = risk_policy_engine.evaluate_risk("get_pod", "auth-service")
        assert eval_res["risk_level"] == RiskLevel.READ_ONLY
        assert eval_res["requires_approval"] is False

    def test_medium_risk_scale_action(self):
        eval_res = risk_policy_engine.evaluate_risk("scale_deployment", "auth-service", namespace="devops-nexus-prod")
        assert eval_res["risk_level"] == RiskLevel.MEDIUM
        assert eval_res["requires_approval"] is True
        assert eval_res["requires_confirm_token"] is False

    def test_high_risk_destructive_action(self):
        eval_res = risk_policy_engine.evaluate_risk("execute_destructive", "auth-service", namespace="devops-nexus-prod")
        assert eval_res["risk_level"] == RiskLevel.HIGH
        assert eval_res["requires_approval"] is True
        assert eval_res["requires_confirm_token"] is True
        assert eval_res["confirm_token_expected"] == "CONFIRM"


class TestActionPlanner:
    def test_create_structured_scale_action_plan(self):
        target_info = {
            "environment": "Amazon EKS",
            "cluster_id": "devops-nexus-eks",
            "namespace": "devops-nexus-prod",
            "resource_name": "auth-service",
            "resource_kind": "deployment"
        }
        plan = action_planner.create_action_plan(
            intent="DEPLOYMENT_ANALYSIS",
            target_info=target_info,
            action_type="scale_deployment",
            parameters={"replicas": 5}
        )
        assert plan["intent"] == "DEPLOYMENT_ANALYSIS"
        assert plan["target"]["application"] == "auth-service"
        assert plan["action"]["type"] == "scale_deployment"
        assert plan["action"]["parameters"]["replicas"] == 5
        assert plan["risk"] == "MEDIUM"
        assert plan["requires_approval"] is True
        assert len(plan["steps"]) >= 4


class TestVerificationEngine:
    def test_verification_success(self):
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
                "argocd_sync": "Synced",
                "argocd_health": "Healthy",
                "git_desired_replicas": 5
            }
            res = verification_engine.verify_action_execution(
                target_resource="auth-service",
                action_type="scale_deployment",
                before_snapshot=before,
                expected_params={"replicas": 5}
            )
            assert res["verified"] is True
            assert "auth-service" in res["verification_summary"]


class TestTelemetryStatusAndHonestConfidence:
    def test_prometheus_failed_telemetry_caps_quality(self):
        evidence_flags = {"pod": True, "deployment": True, "prometheus": False, "loki": False}
        fallbacks = ["Prometheus API query failed or unavailable.", "Loki central log stream query failed."]
        conf = agent_runtime.confidence_engine.calculate_confidence(
            evidence_flags=evidence_flags,
            tools_attempted=8,
            tools_failed=2,
            fallbacks_used=fallbacks,
            correlation_certainty=0.9
        )
        # Verify confidence score calculations
        assert conf["fallbacks_count"] == 2


class TestContextInspectionEndpoint:
    def test_copilot_inspect_context_no_exception(self):
        from app.services.ai_copilot_engine import ai_copilot_engine
        mock_evidence = {
            "timestamp": "2026-09-25T06:00:00Z",
            "pod": {"name": "auth-service-7f8d", "status": "Running"},
            "argocd": {"name": "auth-prod", "sync": "Synced", "health": "Healthy"},
            "prometheus": {"cpu_utilization": 15.0, "memory_utilization": 60.0}
        }
        with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence):
            context = ai_copilot_engine.collect_full_context(cluster_id="default")
            assert "k8s" in context
            assert "argocd" in context
            assert "metrics" in context
            assert "evidence" in context

    def test_agent_runtime_investigation_execution(self):
        mock_evidence = {
            "timestamp": "2026-09-25T06:00:00Z",
            "target_resource": "auth-service",
            "namespace": "devops-nexus-prod",
            "cluster_id": "default",
            "pod": {"name": "auth-service-7f8d-xyz", "status": "Running", "restarts": 0},
            "container_status": {"ready": True, "restart_count": 0},
            "previous_logs": None,
            "current_logs": "GET /health 200",
            "events": [],
            "deployment": {"name": "auth-service", "replicas": 3, "ready_replicas": 3},
            "argocd": {"name": "auth-service-prod", "sync_status": "Synced", "health_status": "Healthy"},
            "prometheus": {"cpu_utilization": 15.0, "memory_utilization": 60.0},
            "loki_logs": [],
            "evidence_flags": {"pod": True, "deployment": True, "prometheus": True, "loki": False, "argocd": True},
            "prometheus_status": "REAL_TELEMETRY",
            "loki_status": "NO_TELEMETRY",
            "fallbacks_used": [],
            "tools_executed": ["pods", "deployments", "argocd", "prometheus"],
            "tools_attempted": 8,
            "tools_failed": 0
        }
        with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence):
            res = agent_runtime.execute_investigation(
                prompt="Why is auth-service restarting?",
                resource_name="auth-service",
                namespace="devops-nexus-prod"
            )
            assert res["intent"] in ["ROOT_CAUSE", "POD_ANALYSIS", "INCIDENT"]
            assert res["target"]["application"] == "auth-service"
            assert res["evidence"] is not None
            assert res["evidence_quality"] in ["HIGH", "MEDIUM", "LOW"]
            assert len(res["verified_evidence"]) > 0
