# --- Comprehensive Unit & Integration Tests for DevOps Tool Registry & Tool RBAC ---
import pytest
from unittest.mock import MagicMock, patch
from app.agent.tools import (
    tool_registry, ToolRegistry, ToolDefinition, ToolResult,
    ToolExecutionStatus, ToolCategory, OperationType
)
from app.agent.tools.models import ListPodsInput, ScaleDeploymentInput, PrometheusQueryInput, LokiQueryInput
from app.agent.risk_policy import RiskLevel
from app.agent.tools.permissions import tool_permission_manager
from app.services.authz_engine import AuthorizationException
from app.agent.agent_runtime import agent_runtime

class TestToolRegistryBasics:
    def test_registered_tools_count(self):
        tools = tool_registry.list()
        assert len(tools) >= 20
        assert tool_registry.get("k8s.list_pods") is not None
        assert tool_registry.get("prometheus.query") is not None
        assert tool_registry.get("loki.query") is not None
        assert tool_registry.get("argocd.sync_application") is not None
        assert tool_registry.get("git.get_repository") is not None

    def test_duplicate_registration_rejection(self):
        custom_registry = ToolRegistry()
        dummy_tool = ToolDefinition(
            name="test.dummy",
            description="Dummy test tool",
            category=ToolCategory.SYSTEM,
            operation_type=OperationType.READ,
            risk_level=RiskLevel.READ_ONLY,
            required_permission="ai:ai_chat",
            handler=lambda x: {"status": "ok"}
        )
        custom_registry.register(dummy_tool)
        with pytest.raises(ValueError, match="DuplicateToolRegistration"):
            custom_registry.register(dummy_tool)

    def test_unknown_tool_execution(self):
        res = tool_registry.execute("nonexistent.tool", input_data={})
        assert res.status == ToolExecutionStatus.UNKNOWN_TOOL
        assert "not registered" in res.error

    def test_input_validation_failure(self):
        # Scale deployment requires integer replicas
        res = tool_registry.execute(
            "k8s.scale_deployment",
            input_data={"namespace": "devops-nexus-prod", "name": "auth-service", "replicas": "invalid_replicas"},
            user_info={"username": "admin", "role": "Administrator"}
        )
        assert res.status == ToolExecutionStatus.INVALID_INPUT
        assert res.error is not None

    def test_tool_lookups_by_category_and_risk(self):
        k8s_tools = tool_registry.find_by_category(ToolCategory.KUBERNETES)
        assert len(k8s_tools) >= 10
        
        high_risk_tools = tool_registry.find_by_risk(RiskLevel.HIGH)
        assert any(t.name == "k8s.delete_pod" for t in high_risk_tools)
        assert any(t.name == "git.update_file" for t in high_risk_tools)

class TestToolRBACAndPermissionEnforcement:
    def test_viewer_permission_denial_on_mutation(self):
        # Viewer user attempting to execute scale_deployment should receive UNAUTHORIZED
        viewer_user = {
            "username": "viewer",
            "role": "Viewer"
        }
        res = tool_registry.execute(
            "k8s.scale_deployment",
            input_data={"namespace": "devops-nexus-prod", "name": "auth-service", "replicas": 5},
            user_info=viewer_user
        )
        assert res.status == ToolExecutionStatus.UNAUTHORIZED
        assert "RBAC Permission Denied" in res.error

    def test_viewer_permission_allowed_on_read(self):
        # Viewer is allowed to list pods
        viewer_user = {
            "username": "viewer",
            "role": "Viewer"
        }
        with patch("app.services.pod_service.pod_service.list_pods", return_value=[{"name": "pod-1", "namespace": "devops-nexus-prod"}]):
            res = tool_registry.execute(
                "k8s.list_pods",
                input_data={"namespace": "devops-nexus-prod"},
                user_info=viewer_user
            )
            assert res.status == ToolExecutionStatus.SUCCESS
            assert len(res.data) == 1

class TestRiskAndConfirmationEnforcement:
    def test_high_risk_tool_requires_confirmation_token(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        # Execute delete_pod without confirmation token
        res = tool_registry.execute(
            "k8s.delete_pod",
            input_data={"namespace": "devops-nexus-prod", "name": "auth-service-xyz"},
            user_info=admin_user,
            confirm_token=None
        )
        assert res.status == ToolExecutionStatus.CONFIRMATION_REQUIRED
        assert "requires explicit confirmation token 'CONFIRM'" in res.error

    def test_high_risk_tool_executes_with_valid_token(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        with patch("app.clients.kubernetes.k8s_client.delete_pod", return_value=True):
            res = tool_registry.execute(
                "k8s.delete_pod",
                input_data={"namespace": "devops-nexus-prod", "name": "auth-service-xyz"},
                user_info=admin_user,
                confirm_token="CONFIRM"
            )
            assert res.status == ToolExecutionStatus.SUCCESS
            assert "deleted in namespace" in res.data.get("message", "")

class TestCategoryToolExecution:
    def test_prometheus_tool_execution(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        mock_prom_data = {"status": "success", "data": {"resultType": "vector", "result": [{"value": [1000, "15.5"]}]}}
        with patch("app.clients.prometheus.prometheus_client.query", return_value=mock_prom_data):
            res = tool_registry.execute(
                "prometheus.query",
                input_data={"query": "container_cpu_usage_seconds_total"},
                user_info=admin_user
            )
            assert res.status == ToolExecutionStatus.SUCCESS
            assert res.data["status"] == "success"

    def test_loki_tool_execution(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        mock_loki_data = {"status": "success", "data": {"resultType": "streams", "result": []}}
        with patch("app.clients.loki.loki_client.query_range", return_value=mock_loki_data):
            res = tool_registry.execute(
                "loki.query",
                input_data={"query": '{namespace="devops-nexus-prod"}'},
                user_info=admin_user
            )
            assert res.status == ToolExecutionStatus.SUCCESS

    def test_argocd_sync_tool_execution(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        with patch("app.services.argocd_service.argocd_service.sync_application", return_value={"status": "Synced"}):
            res = tool_registry.execute(
                "argocd.sync_application",
                input_data={"name": "auth-prod"},
                user_info=admin_user
            )
            assert res.status == ToolExecutionStatus.SUCCESS
            assert res.data.get("status") == "Synced"

    def test_git_get_repository_execution(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        res = tool_registry.execute(
            "git.get_repository",
            input_data={"owner": "Manikandan23005", "repo": "Microservice-Deployment-Monitoring-Platform"},
            user_info=admin_user
        )
        assert res.status == ToolExecutionStatus.SUCCESS
        assert "branches" in res.data

class TestParallelToolExecution:
    def test_parallel_read_tools_execution(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        calls = [
            {"tool": "k8s.list_namespaces", "input": {}},
            {"tool": "prometheus.cluster_metrics", "input": {}},
            {"tool": "argocd.list_applications", "input": {}}
        ]
        with patch("app.services.namespace_service.namespace_service.list_namespaces", return_value=["devops-nexus-prod", "monitoring"]), \
             patch("app.services.monitoring_service.monitoring_service.get_cluster_metrics", return_value={"cpu_utilization": 20.0}), \
             patch("app.services.argocd_service.argocd_service.list_applications", return_value=[{"name": "auth-prod"}]):
            results = tool_registry.execute_parallel(calls, user_info=admin_user)
            assert len(results) == 3
            assert all(r.status == ToolExecutionStatus.SUCCESS for r in results)

class TestAgentRuntimeToolIntegration:
    def test_agent_runtime_execute_tool(self):
        admin_user = {"username": "admin", "role": "Administrator"}
        with patch("app.services.namespace_service.namespace_service.list_namespaces", return_value=["default", "devops-nexus-prod"]):
            res = agent_runtime.execute_tool("k8s.list_namespaces", user_info=admin_user)
            assert res.status == ToolExecutionStatus.SUCCESS
            assert "devops-nexus-prod" in res.data
