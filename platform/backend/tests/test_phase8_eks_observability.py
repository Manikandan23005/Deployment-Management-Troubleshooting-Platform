# --- Phase 8: EKS Observability Integration Tests ---
import pytest
from unittest.mock import MagicMock, patch
from app.clients.prometheus import PrometheusClient
from app.clients.loki import LokiClient
from app.agent.tools import tool_registry, ToolExecutionStatus
from app.agent.models import FailureCategory, ScopeContext
from app.agent.root_cause_engine import RootCauseEngine
from app.agent.verification_engine import VerificationEngine

class TestPhase8PrometheusAndLokiClients:
    def test_prometheus_client_query(self):
        client = PrometheusClient()
        with patch.object(client, "_check_reachability", return_value=True):
            with patch("httpx.Client.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"metric": {"__name__": "up"}, "value": [1700000000, "1"]}]
                    }
                }
                mock_get.return_value = mock_resp
                res = client.query("up")
                assert res["status"] == "success"
                assert len(res["data"]["result"]) == 1

    def test_prometheus_client_alerts(self):
        client = PrometheusClient()
        with patch.object(client, "_check_reachability", return_value=True):
            with patch("httpx.Client.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "status": "success",
                    "data": {
                        "alerts": [
                            {"labels": {"alertname": "PodCrashLoopBackOff", "pod": "gateway-abc"}, "state": "firing"}
                        ]
                    }
                }
                mock_get.return_value = mock_resp
                alerts = client.get_alerts()
                assert len(alerts["data"]["alerts"]) == 1
                assert alerts["data"]["alerts"][0]["labels"]["alertname"] == "PodCrashLoopBackOff"

    def test_loki_client_query_range(self):
        client = LokiClient()
        with patch.object(client, "_check_reachability", return_value=True):
            with patch("httpx.Client.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "status": "success",
                    "data": {
                        "resultType": "streams",
                        "result": [
                            {
                                "stream": {"app": "gateway", "namespace": "devops-nexus-prod"},
                                "values": [["1700000000000000000", "HTTP 500 Internal Server Error in /api/v1/checkout"]]
                            }
                        ]
                    }
                }
                mock_get.return_value = mock_resp
                res = client.query_range('{app="gateway"}')
                assert res["status"] == "success"
                assert len(res["data"]["result"]) == 1

class TestPhase8ObservabilityToolGovernance:
    def test_prometheus_query_tool_execution(self):
        with patch("app.clients.prometheus.prometheus_client.query", return_value={"status": "success", "data": {"result": []}}):
            res = tool_registry.execute(
                "prometheus.query",
                input_data={"query": "sum(rate(container_cpu_usage_seconds_total[5m]))"},
                user_info={"username": "ops-engineer", "role": "Developer"}
            )
            assert res.status == ToolExecutionStatus.SUCCESS
            assert res.data["status"] == "success"

    def test_loki_query_tool_execution(self):
        with patch("app.clients.loki.loki_client.query_range", return_value={"status": "success", "data": {"result": []}}):
            res = tool_registry.execute(
                "loki.query",
                input_data={"query": '{namespace="devops-nexus-prod"} |= "error"', "limit": 50},
                user_info={"username": "viewer", "role": "Viewer"}
            )
            assert res.status == ToolExecutionStatus.SUCCESS
            assert res.data["status"] == "success"

    def test_loki_search_errors_tool(self):
        fake_result = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"pod": "gateway-7489-abc"},
                        "values": [["1700000000000000000", "FATAL: database connection timeout"]]
                    }
                ]
            }
        }
        with patch("app.clients.loki.loki_client.query_range", return_value=fake_result):
            res = tool_registry.execute(
                "loki.search_errors",
                input_data={"namespace": "devops-nexus-prod", "application": "gateway", "limit": 10},
                user_info={"username": "sre", "role": "Administrator"}
            )
            assert res.status == ToolExecutionStatus.SUCCESS
            assert len(res.data) == 1
            assert res.data[0]["pod"] == "gateway-7489-abc"

class TestPhase8RootCauseTelemetryCorrelation:
    def test_correlate_http_500_and_loki_exceptions(self):
        engine = RootCauseEngine()
        evidence = {
            "target_resource": "gateway-service",
            "namespace": "devops-nexus-prod",
            "pod": {"name": "gateway-service-abc", "status": "Running", "restarts": 0},
            "container_status": {"ready": True, "last_exit_code": 0},
            "deployment": {"name": "gateway-service", "replicas": 1, "ready_replicas": 1},
            "argocd": {"sync_status": "Synced", "health_status": "Healthy"},
            "prometheus": {"error_rate": 18.5, "cpu_utilization": 22.0},
            "loki_logs": [
                "2026-09-26T04:00:00Z ERROR Exception in GatewayController: 500 Internal Server Error",
                "2026-09-26T04:00:01Z Traceback (most recent call last): httpexception"
            ]
        }
        diag = engine.diagnose(evidence)
        assert diag["failure_category"] in [FailureCategory.HIGH_ERROR_RATE, FailureCategory.APPLICATION_EXCEPTION]
        assert "500" in diag["probable_cause"] or "error" in diag["probable_cause"].lower()
        assert diag["confidence_level"] == "HIGH"
        assert len(diag["supporting_evidence"]) >= 3

    def test_correlate_oom_killed_with_prometheus_memory(self):
        engine = RootCauseEngine()
        evidence = {
            "target_resource": "payment-service",
            "namespace": "devops-nexus-prod",
            "pod": {"name": "payment-service-xyz", "status": "OOMKilled", "restarts": 4},
            "container_status": {"ready": False, "last_exit_code": 137, "last_state_reason": "OOMKilled"},
            "events": [{"type": "Warning", "reason": "OOMKilled", "message": "Container killed by OOM"}],
            "prometheus": {"memory_utilization": 98.2}
        }
        diag = engine.diagnose(evidence)
        assert diag["failure_category"] == FailureCategory.OOM_KILLED
        assert diag["certainty"] >= 0.95
        assert any("137" in s for s in diag["supporting_evidence"])

class TestPhase8VerificationEngineObservability:
    def test_verification_validates_telemetry_recovery(self):
        engine = VerificationEngine()
        before = {
            "timestamp": 1000.0,
            "target_resource": "gateway-service",
            "running_pods": 0,
            "ready_pods": 0,
            "argocd_sync": "OutOfSync",
            "argocd_health": "Degraded",
            "firing_alerts": 1
        }
        
        with patch.object(engine, "capture_state_snapshot") as mock_snap:
            mock_snap.return_value = {
                "timestamp": 1005.0,
                "target_resource": "gateway-service",
                "running_pods": 1,
                "ready_pods": 1,
                "deployment_ready_replicas": 1,
                "git_desired_replicas": 1,
                "argocd_sync": "Synced",
                "argocd_health": "Healthy",
                "firing_alerts": 0
            }
            res = engine.verify_action_execution(
                target_resource="gateway-service",
                action_type="restart_deployment",
                before_snapshot=before
            )
            assert res["verified"] is True
            assert res["observability_verified"] is True
            assert "VERIFIED_SUCCESS" in res["verification_summary"]
