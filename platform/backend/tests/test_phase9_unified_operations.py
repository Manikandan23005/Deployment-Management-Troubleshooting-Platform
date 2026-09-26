# --- Phase 9: Unified EKS + On-Prem Operations Integration Tests ---
import pytest
from unittest.mock import MagicMock, patch
from app.agent.target_resolver import target_resolver, TargetResolver
from app.agent.models import ScopeContext, RemediationPlan, RemediationAction
from app.agent.risk_policy import RiskLevel
from app.agent.tools import tool_registry, ToolExecutionStatus
from app.agent.agent_runtime import agent_runtime

class TestPhase9TargetResolver:
    def test_resolve_eks_environment_from_prompt(self):
        resolved = target_resolver.resolve_target(
            prompt="Check the gateway in production EKS"
        )
        assert resolved["environment_type"] == "AWS_EKS"
        assert resolved["environment"] == "Amazon EKS"
        assert resolved["application"] == "gateway"
        assert resolved["aws_account_id"] == "605294565283"
        assert resolved["region"] == "ap-south-1"
        assert resolved["cluster_id"] == "devops-nexus-prod"

    def test_resolve_onprem_environment_from_prompt(self):
        resolved = target_resolver.resolve_target(
            prompt="Check the gateway in on-prem production"
        )
        assert resolved["environment_type"] == "ON_PREM_KUBERNETES"
        assert resolved["environment"] == "On-Premises Kubernetes"
        assert resolved["application"] == "gateway"
        assert resolved["cluster_id"] == "onprem-prod"

    def test_resolve_cross_environment_comparison_prompt(self):
        resolved = target_resolver.resolve_target(
            prompt="Compare gateway between EKS and on-prem"
        )
        assert resolved["is_comparison"] is True
        assert "AWS_EKS" in resolved["compare_environments"]
        assert "ON_PREM_KUBERNETES" in resolved["compare_environments"]
        assert resolved["application"] == "gateway"

    def test_mutation_without_target_flags_clarification(self):
        resolved = target_resolver.resolve_target(
            prompt="scale deployment to 3 replicas"
        )
        assert resolved["needs_clarification"] is True
        assert "Please specify target application" in resolved["clarification_message"]

    def test_compare_workload_environments_factual_report(self):
        report = target_resolver.compare_workload_environments(
            workload="gateway",
            namespace="devops-nexus-prod",
            envs=["AWS_EKS", "ON_PREM_KUBERNETES"]
        )
        assert report["workload"] == "gateway"
        assert "AWS_EKS" in report["environments"]
        assert "ON_PREM_KUBERNETES" in report["environments"]
        
        eks_data = report["environments"]["AWS_EKS"]
        onprem_data = report["environments"]["ON_PREM_KUBERNETES"]
        
        assert eks_data["cluster"] == "devops-nexus-prod"
        assert onprem_data["cluster"] == "onprem-prod"
        assert "605294565283" in eks_data["image"]
        assert "605294565283" not in onprem_data["image"]

class TestPhase9UnifiedToolRegistryExecution:
    def test_k8s_list_pods_with_eks_scope(self):
        eks_scope = ScopeContext(
            environment="AWS_EKS",
            cluster_id="devops-nexus-prod",
            namespace="devops-nexus-prod",
            aws_account_id="605294565283",
            region="ap-south-1"
        )
        with patch("app.clients.kubernetes.k8s_client.list_pods", return_value=[]):
            res = tool_registry.execute(
                "k8s.list_pods",
                input_data={"namespace": eks_scope.namespace, "cluster_id": eks_scope.cluster_id},
                user_info={"username": "admin", "role": "Administrator"}
            )
            assert res.status == ToolExecutionStatus.SUCCESS

    def test_k8s_list_pods_with_onprem_scope(self):
        onprem_scope = ScopeContext(
            environment="ON_PREM_KUBERNETES",
            cluster_id="onprem-prod",
            namespace="devops-nexus-prod"
        )
        with patch("app.clients.kubernetes.k8s_client.list_pods", return_value=[]):
            res = tool_registry.execute(
                "k8s.list_pods",
                input_data={"namespace": onprem_scope.namespace, "cluster_id": onprem_scope.cluster_id},
                user_info={"username": "admin", "role": "Administrator"}
            )
            assert res.status == ToolExecutionStatus.SUCCESS

class TestPhase9RemediationPlanEnvironmentBoundary:
    def test_remediation_plan_preserves_scope_context(self):
        eks_scope = ScopeContext(
            environment="AWS_EKS",
            cluster_id="devops-nexus-prod",
            namespace="devops-nexus-prod",
            application="auth-service",
            aws_account_id="605294565283",
            region="ap-south-1"
        )
        plan = RemediationPlan(
            incident_id="inc-test-999",
            target=eks_scope,
            diagnosis={"probable_cause": "CrashLoopBackOff in pod"},
            actions=[
                RemediationAction(
                    tool_name="k8s.restart_deployment",
                    inputs={"namespace": "devops-nexus-prod", "name": "auth-service", "cluster_id": "devops-nexus-prod"},
                    expected_effect="Deployment restarted on EKS cluster"
                )
            ],
            risk_level=RiskLevel.LOW,
            expected_effect="Auth service recovered"
        )
        assert plan.target.environment == "AWS_EKS"
        assert plan.target.aws_account_id == "605294565283"
        assert plan.actions[0].inputs["cluster_id"] == "devops-nexus-prod"
