# --- Phase 4 Autonomous DevOps Troubleshooting & Verified Remediation Tests ---
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.agent.root_cause_engine import root_cause_engine, RootCauseEngine
from app.agent.remediation_planner import remediation_planner
from app.agent.incident_store import incident_store
from app.agent.remediation_engine import remediation_engine, AutonomousRemediationEngine
from app.agent.models import (
    FailureCategory, 
    IncidentStatus, 
    ScopeContext, 
    RemediationPlan, 
    AutonomousIncident
)
from app.agent.risk_policy import RiskLevel
from app.agent.agent_runtime import agent_runtime

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_incident_store():
    incident_store.clear()
    yield
    incident_store.clear()


# =========================================================================
# PART A: 15-Class Deterministic Root Cause Analysis Tests
# =========================================================================

def test_diagnose_oom_killed():
    evidence = {
        "target_resource": "payment-service",
        "namespace": "devops-nexus-prod",
        "pod": {"name": "payment-service-abc", "status": "Running", "restarts": 12},
        "container_status": {"last_exit_code": 137, "last_state_reason": "OOMKilled", "ready": False},
        "events": [{"type": "Warning", "reason": "OOMKilled", "message": "Container killed by OOM killer"}],
        "prometheus": {"memory_utilization": 94.2}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.OOM_KILLED
    assert diag["severity"] == "Critical"
    assert diag["certainty"] >= 0.95
    assert "OOM-killer" in diag["probable_cause"]

def test_diagnose_image_pull_backoff():
    evidence = {
        "target_resource": "auth-service",
        "namespace": "devops-nexus-prod",
        "pod": {"name": "auth-service-xyz", "status": "ImagePullBackOff", "restarts": 0, "image": "nexus.io/auth:v9.9.9-invalid"},
        "container_status": {"waiting_reason": "ImagePullBackOff", "ready": False},
        "events": [{"type": "Warning", "reason": "Failed", "message": "Failed to pull image nexus.io/auth:v9.9.9-invalid: rpc error: code = NotFound"}]
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.IMAGE_PULL_BACKOFF
    assert diag["severity"] == "High"
    assert "could not be pulled" in diag["probable_cause"]

def test_diagnose_err_image_pull():
    evidence = {
        "target_resource": "frontend",
        "pod": {"name": "frontend-123", "status": "ErrImagePull", "image": "nexus.io/frontend:latest"},
        "container_status": {"waiting_reason": "ErrImagePull"},
        "events": [{"type": "Warning", "reason": "ErrImagePull", "message": "failed to pull image"}]
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.ERR_IMAGE_PULL

def test_diagnose_failed_scheduling():
    evidence = {
        "target_resource": "analytics",
        "pod": {"name": "analytics-pod", "status": "Pending"},
        "events": [{"type": "Warning", "reason": "FailedScheduling", "message": "0/3 nodes are available: 3 Insufficient cpu."}]
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.FAILED_SCHEDULING
    assert diag["severity"] == "High"

def test_diagnose_pending_pod():
    evidence = {
        "target_resource": "queue-worker",
        "pod": {"name": "queue-worker-1", "status": "Pending"},
        "events": []
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.PENDING_POD

def test_diagnose_readiness_probe_failure():
    evidence = {
        "target_resource": "orders-service",
        "pod": {"name": "orders-pod", "status": "Running"},
        "container_status": {"ready": False},
        "events": [{"type": "Warning", "reason": "Unhealthy", "message": "Readiness probe failed: HTTP probe failed with statuscode: 503"}]
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.READINESS_PROBE_FAILURE

def test_diagnose_liveness_probe_failure():
    evidence = {
        "target_resource": "orders-service",
        "pod": {"name": "orders-pod", "status": "Running", "restarts": 4},
        "container_status": {"ready": True},
        "events": [{"type": "Warning", "reason": "Unhealthy", "message": "Liveness probe failed: connection refused"}]
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.LIVENESS_PROBE_FAILURE

def test_diagnose_crashloop_backoff():
    evidence = {
        "target_resource": "gateway",
        "pod": {"name": "gateway-abc", "status": "CrashLoopBackOff", "restarts": 8},
        "container_status": {"last_exit_code": 1, "last_state_reason": "Error", "waiting_reason": "CrashLoopBackOff"}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.CRASH_LOOP_BACKOFF
    assert diag["severity"] == "Critical"

def test_diagnose_high_restart_count():
    evidence = {
        "target_resource": "notifier",
        "pod": {"name": "notifier-123", "status": "Running", "restarts": 15},
        "container_status": {"ready": True}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.HIGH_RESTART_COUNT

def test_diagnose_deployment_unavailable():
    evidence = {
        "target_resource": "user-service",
        "deployment": {"name": "user-service", "replicas": 3, "ready_replicas": 0},
        "pod": {"name": "user-service-1", "status": "Running"}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.DEPLOYMENT_UNAVAILABLE

def test_diagnose_argocd_sync_failure():
    evidence = {
        "target_resource": "payment-service",
        "argocd": {"name": "payment-service-prod", "sync_status": "Failed", "health_status": "Degraded", "revision": "main"}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.ARGOCD_SYNC_FAILURE

def test_diagnose_argocd_out_of_sync():
    evidence = {
        "target_resource": "auth-service",
        "argocd": {"name": "auth-service-prod", "sync_status": "OutOfSync", "health_status": "Healthy"}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.ARGOCD_OUT_OF_SYNC

def test_diagnose_high_cpu():
    evidence = {
        "target_resource": "worker",
        "prometheus": {"cpu_utilization": 89.5, "memory_utilization": 45.0}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.HIGH_CPU

def test_diagnose_high_memory():
    evidence = {
        "target_resource": "worker",
        "prometheus": {"cpu_utilization": 30.0, "memory_utilization": 91.0}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.HIGH_MEMORY

def test_diagnose_gitops_config_mismatch():
    evidence = {
        "target_resource": "auth-service",
        "git_desired_replicas": 5,
        "deployment": {"name": "auth-service", "replicas": 2, "ready_replicas": 2}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.GITOPS_CONFIG_MISMATCH

def test_diagnose_healthy_workload():
    evidence = {
        "target_resource": "auth-service",
        "pod": {"name": "auth-service-xyz", "status": "Running", "restarts": 0},
        "container_status": {"ready": True, "last_exit_code": 0},
        "deployment": {"name": "auth-service", "replicas": 2, "ready_replicas": 2},
        "argocd": {"name": "auth-service-prod", "sync_status": "Synced", "health_status": "Healthy"},
        "prometheus": {"cpu_utilization": 22.0, "memory_utilization": 45.0}
    }
    diag = root_cause_engine.diagnose(evidence)
    assert diag["failure_category"] == FailureCategory.HEALTHY_WORKLOAD
    assert diag["severity"] == "Info"


# =========================================================================
# PART B: Remediation Planning & Idempotency Tests
# =========================================================================

def test_remediation_planner_crashloop():
    scope = ScopeContext(environment="KUBERNETES", cluster_id="default", namespace="devops-nexus-prod", application="payment-service")
    diagnosis = {"failure_category": FailureCategory.CRASH_LOOP_BACKOFF}
    evidence = {"target_resource": "payment-service"}

    plan = remediation_planner.build_plan("inc-001", scope, diagnosis, evidence)
    assert plan is not None
    assert len(plan.actions) == 1
    assert plan.actions[0].tool_name == "k8s.restart_deployment"
    assert plan.actions[0].inputs["name"] == "payment-service"
    assert plan.actions[0].verification_plan["check_pods_ready"] is True

def test_remediation_planner_scaling_with_gitops_preview():
    scope = ScopeContext(environment="KUBERNETES", cluster_id="default", namespace="devops-nexus-prod", application="auth-service")
    diagnosis = {"failure_category": FailureCategory.HIGH_CPU}
    evidence = {"target_resource": "auth-service", "deployment": {"replicas": 2}}

    plan = remediation_planner.build_plan("inc-002", scope, diagnosis, evidence)
    assert plan is not None
    assert len(plan.actions) == 1
    assert plan.actions[0].inputs["replicas"] == 3
    assert plan.change_preview is not None
    assert "values" in plan.change_preview["file_path"]

def test_remediation_planner_idempotency_argocd_already_synced():
    scope = ScopeContext(environment="KUBERNETES", cluster_id="default", namespace="devops-nexus-prod", application="auth-service")
    diagnosis = {"failure_category": FailureCategory.ARGOCD_OUT_OF_SYNC}
    evidence = {"target_resource": "auth-service", "argocd": {"sync_status": "Synced"}}

    plan = remediation_planner.build_plan("inc-003", scope, diagnosis, evidence)
    assert plan is not None
    # Swapped to safe refresh instead of redundant sync
    assert plan.actions[0].tool_name == "argocd.refresh_application"

def test_remediation_planner_healthy_returns_none():
    scope = ScopeContext(environment="KUBERNETES", cluster_id="default", namespace="devops-nexus-prod", application="auth-service")
    diagnosis = {"failure_category": FailureCategory.HEALTHY_WORKLOAD}
    evidence = {}

    plan = remediation_planner.build_plan("inc-004", scope, diagnosis, evidence)
    assert plan is None


@pytest.fixture
def mock_evidence_crashloop():
    return {
        "timestamp": "2026-09-25T06:00:00Z",
        "target_resource": "payment-service",
        "namespace": "devops-nexus-prod",
        "cluster_id": "default",
        "pod": {"name": "payment-service-abc", "status": "CrashLoopBackOff", "restarts": 10},
        "container_status": {"last_exit_code": 1, "last_state_reason": "Error", "waiting_reason": "CrashLoopBackOff", "ready": False},
        "previous_logs": "Exception in thread main: database unreachable",
        "current_logs": "restarting container...",
        "events": [{"type": "Warning", "reason": "BackOff", "message": "Back-off restarting failed container"}],
        "deployment": {"name": "payment-service", "replicas": 2, "ready_replicas": 0},
        "argocd": {"name": "payment-service-prod", "sync_status": "Synced", "health_status": "Degraded"},
        "prometheus": {"cpu_utilization": 20.0, "memory_utilization": 50.0},
        "loki_logs": ["Error connecting to database at 10.0.0.5"],
        "evidence_flags": {"pod": True, "deployment": True, "prometheus": True, "loki": True, "argocd": True},
        "fallbacks_used": [],
        "tools_executed": ["pods", "deployments", "argocd", "prometheus", "loki"],
        "tools_attempted": 8,
        "tools_failed": 0
    }

# =========================================================================
# PART C: Closed-Loop Execution, Verification, and Safety Tests
# =========================================================================

def test_closed_loop_troubleshoot_and_remediate_success(mock_evidence_crashloop):
    with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence_crashloop):
        # 1. Start investigation for crashing service
        incident = agent_runtime.troubleshoot(
            prompt="Why is payment-service crashing?",
            resource_name="payment-service",
            namespace="devops-nexus-prod"
        )

        assert incident.incident_id.startswith("inc-")
        assert incident.status in [IncidentStatus.PLAN_GENERATED, IncidentStatus.AWAITING_APPROVAL]
        assert incident.remediation_plan is not None

        # 2. Execute approved remediation
        with patch("app.agent.verification_engine.VerificationEngine.verify_action_execution") as mock_verify:
            with patch("app.agent.tools.registry.ToolRegistry.execute") as mock_tool_exec:
                from app.agent.tools.models import ToolResult, ToolExecutionStatus
                mock_tool_exec.return_value = ToolResult(
                    tool="k8s.restart_deployment",
                    status=ToolExecutionStatus.SUCCESS,
                    data={"restarted": True, "message": "Deployment payment-service restarted"}
                )
                mock_verify.return_value = {
                    "verified": True,
                    "verification_summary": "VERIFIED_SUCCESS: Rollout restart succeeded for payment-service."
                }
                
                updated_incident = agent_runtime.remediate(
                    incident_id=incident.incident_id,
                    user_info={"username": "devops-lead", "role": "admin"}
                )

                assert updated_incident.status == IncidentStatus.COMPLETED
                assert "VERIFIED_SUCCESS" in updated_incident.final_outcome
                assert len(updated_incident.executed_actions) > 0

def test_closed_loop_verification_failure_triggers_escalation(mock_evidence_crashloop):
    with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence_crashloop):
        # 1. Start investigation
        incident = agent_runtime.troubleshoot(
            prompt="Restart payment-service deployment",
            resource_name="payment-service"
        )

        # 2. Mock verification failure
        with patch("app.agent.verification_engine.VerificationEngine.verify_action_execution") as mock_verify:
            with patch("app.agent.tools.registry.ToolRegistry.execute") as mock_tool_exec:
                from app.agent.tools.models import ToolResult, ToolExecutionStatus
                mock_tool_exec.return_value = ToolResult(
                    tool="k8s.restart_deployment",
                    status=ToolExecutionStatus.SUCCESS,
                    data={"restarted": True}
                )
                mock_verify.return_value = {
                    "verified": False,
                    "verification_summary": "VERIFICATION_FAILED: Pods not ready post-restart."
                }
                
                updated_incident = agent_runtime.remediate(
                    incident_id=incident.incident_id,
                    user_info={"username": "devops-lead", "role": "admin"}
                )

                # Invariant: Must NOT claim success, must trigger re-investigation and ESCALATE
                assert updated_incident.status == IncidentStatus.ESCALATED
                assert "Escalated to operations team" in updated_incident.final_outcome

def test_viewer_role_blocked_from_remediation(mock_evidence_crashloop):
    with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence_crashloop):
        incident = agent_runtime.troubleshoot(
            prompt="Restart payment-service",
            resource_name="payment-service"
        )

        result = agent_runtime.remediate(
            incident_id=incident.incident_id,
            user_info={"username": "viewer-user", "role": "viewer"}
        )

        assert result.status == IncidentStatus.FAILED
        assert "RBAC Authorization failed" in result.timeline[-1].message


# =========================================================================
# PART D: REST API Endpoints Integration Tests
# =========================================================================

def test_api_troubleshoot_endpoint(mock_evidence_crashloop):
    with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence_crashloop):
        response = client.post(
            "/api/v1/agent/troubleshoot",
            json={"prompt": "Investigate payment-service crash loop", "resource_name": "payment-service"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "incident_id" in data["data"]
        assert "diagnosis" in data["data"]

def test_api_get_incident_and_timeline(mock_evidence_crashloop):
    with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence_crashloop):
        # Create incident first
        tb_res = client.post(
            "/api/v1/agent/troubleshoot",
            json={"prompt": "Check payment-service status", "resource_name": "payment-service"}
        )
        inc_id = tb_res.json()["data"]["incident_id"]

        # Get by ID
        get_res = client.get(f"/api/v1/agent/incidents/{inc_id}")
        assert get_res.status_code == 200
        assert get_res.json()["data"]["incident_id"] == inc_id

        # Get Timeline
        tl_res = client.get(f"/api/v1/agent/incidents/{inc_id}/timeline")
        assert tl_res.status_code == 200
        assert len(tl_res.json()["data"]["timeline"]) >= 2

def test_api_list_incidents(mock_evidence_crashloop):
    with patch.object(agent_runtime.scheduler, 'execute_tools_parallel', return_value=mock_evidence_crashloop):
        client.post("/api/v1/agent/troubleshoot", json={"prompt": "Incident 1", "resource_name": "payment-service"})
        client.post("/api/v1/agent/troubleshoot", json={"prompt": "Incident 2", "resource_name": "payment-service"})

        list_res = client.get("/api/v1/agent/incidents")
        assert list_res.status_code == 200
        assert len(list_res.json()["data"]) >= 2

def test_api_direct_tool_execute():
    with patch("app.agent.tools.registry.ToolRegistry.execute") as mock_exec:
        from app.agent.tools.models import ToolResult, ToolExecutionStatus
        mock_exec.return_value = ToolResult(
            tool="k8s.get_pod",
            status=ToolExecutionStatus.SUCCESS,
            data={"name": "auth-service", "status": "Running"}
        )
        res = client.post(
            "/api/v1/agent/tools/execute",
            json={"tool_name": "k8s.get_pod", "input_data": {"name": "auth-service", "namespace": "devops-nexus-prod"}}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["tool"] == "k8s.get_pod"

