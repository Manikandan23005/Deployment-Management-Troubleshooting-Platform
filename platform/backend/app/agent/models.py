# --- Strongly-Typed Autonomous Incident & Remediation Models ---
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict
import datetime
import uuid
from app.agent.risk_policy import RiskLevel
from app.agent.tools.models import ToolResult

class IncidentStatus(str, Enum):
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSING = "DIAGNOSING"
    PLAN_GENERATED = "PLAN_GENERATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REMEDIATING = "REMEDIATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"

class FailureCategory(str, Enum):
    CRASH_LOOP_BACKOFF = "CrashLoopBackOff"
    OOM_KILLED = "OOMKilled"
    IMAGE_PULL_BACKOFF = "ImagePullBackOff"
    ERR_IMAGE_PULL = "ErrImagePull"
    PENDING_POD = "PendingPod"
    FAILED_SCHEDULING = "FailedScheduling"
    DEPLOYMENT_UNAVAILABLE = "DeploymentUnavailable"
    READINESS_PROBE_FAILURE = "ReadinessProbeFailure"
    LIVENESS_PROBE_FAILURE = "LivenessProbeFailure"
    HIGH_RESTART_COUNT = "HighRestartCount"
    HIGH_CPU = "HighCPU"
    HIGH_MEMORY = "HighMemory"
    ARGOCD_OUT_OF_SYNC = "ArgoCDOutOfSync"
    ARGOCD_SYNC_FAILURE = "ArgoCDSyncFailure"
    GITOPS_CONFIG_MISMATCH = "GitOpsConfigMismatch"
    HEALTHY_WORKLOAD = "HealthyWorkload"
    UNKNOWN_FAILURE = "UnknownFailure"

class FailureReason(str, Enum):
    INVESTIGATION_FAILED = "INVESTIGATION_FAILED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DIAGNOSIS_UNCERTAIN = "DIAGNOSIS_UNCERTAIN"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    REMEDIATION_FAILED = "REMEDIATION_FAILED"
    TIMEOUT = "TIMEOUT"
    UNSAFE_ACTION = "UNSAFE_ACTION"
    PERMISSION_DENIED = "PERMISSION_DENIED"

class ScopeContext(BaseModel):
    """Execution scope descriptor supporting on-prem Kubernetes and Amazon EKS environments."""
    environment: str = Field("KUBERNETES", description="Target environment type, e.g. KUBERNETES or AWS_EKS.")
    cluster_id: str = Field("default", description="Cluster identifier.")
    cluster: Optional[str] = Field(None, description="Cluster name alias.")
    namespace: str = Field("devops-nexus-prod", description="Target Kubernetes namespace.")
    application: Optional[str] = Field(None, description="Target application/service identifier.")
    workload: Optional[str] = Field(None, description="Specific pod or workload identifier.")
    resource_kind: str = Field("deployment", description="Resource kind (deployment, pod, statefulset, etc.).")
    aws_account_id: Optional[str] = Field(None, description="Associated AWS Account ID for AWS_EKS environment.")
    aws_account_name: Optional[str] = Field(None, description="Associated AWS Account display name.")
    region: Optional[str] = Field(None, description="AWS Region for AWS_EKS target.")

class RemediationAction(BaseModel):
    """A concrete, tool-mediated infrastructure remediation operation."""
    action_id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:8]}")
    tool_name: str = Field(..., description="Registered ToolRegistry tool identifier, e.g. 'k8s.restart_deployment'.")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Typed inputs passed to ToolRegistry.")
    risk_level: RiskLevel = Field(RiskLevel.LOW, description="Assessed risk level tier.")
    requires_confirmation: bool = Field(False, description="Whether confirmation is required before execution.")
    expected_effect: str = Field(..., description="Anticipated infrastructure state transition.")
    verification_plan: Dict[str, Any] = Field(default_factory=dict, description="Verification checks to perform post-execution.")
    rollback_plan: Optional[Dict[str, Any]] = Field(None, description="Rollback instructions if verification fails.")
    status: str = Field("pending", description="Action status: pending, running, completed, failed, skipped.")
    result: Optional[Dict[str, Any]] = Field(None, description="Serialized ToolResult payload.")

class RemediationPlan(BaseModel):
    """Structured remediation plan containing one or more ordered tool actions."""
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    incident_id: str = Field(..., description="Associated incident ID.")
    target: ScopeContext = Field(..., description="Operational scope target.")
    diagnosis: Dict[str, Any] = Field(default_factory=dict, description="Diagnosis summary and failure class.")
    actions: List[RemediationAction] = Field(default_factory=list, description="Ordered remediation actions.")
    risk_level: RiskLevel = Field(RiskLevel.LOW, description="Aggregated highest risk level.")
    requires_confirmation: bool = Field(False, description="Whether human confirmation token is needed.")
    expected_effect: str = Field(..., description="Summary of expected operational outcome.")
    verification_plan: Dict[str, Any] = Field(default_factory=dict, description="Criteria for successful resolution.")
    rollback_plan: Optional[Dict[str, Any]] = Field(None, description="Fallback instructions on failure.")
    status: str = Field("PLAN_GENERATED", description="Plan lifecycle status.")
    change_preview: Optional[Dict[str, Any]] = Field(None, description="Optional GitOps YAML diff preview.")

class IncidentTimelineEntry(BaseModel):
    """A single chronological audit event in the incident resolution lifecycle."""
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    stage: IncidentStatus = Field(..., description="Incident lifecycle stage.")
    message: str = Field(..., description="Human-readable event narrative.")
    details: Optional[Dict[str, Any]] = Field(None, description="Structured event metadata.")

class AutonomousIncident(BaseModel):
    """Comprehensive autonomous incident record with complete evidence graph and audit history."""
    incident_id: str = Field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:8]}")
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    user_request: str = Field(..., description="Initial user operational prompt or alert.")
    intent: str = Field("ROOT_CAUSE", description="Classified intent.")
    target_scope: ScopeContext = Field(..., description="Resolved operational scope context.")
    status: IncidentStatus = Field(IncidentStatus.INVESTIGATING, description="Current lifecycle state.")
    failure_category: FailureCategory = Field(FailureCategory.UNKNOWN_FAILURE, description="Diagnosed failure class.")
    severity: str = Field("Info", description="Incident severity (Critical, High, Warning, Info).")
    confidence: Dict[str, Any] = Field(default_factory=dict, description="Mathematical confidence score & quality.")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Raw multi-source evidence graph.")
    diagnosis: Dict[str, Any] = Field(default_factory=dict, description="Structured root cause explanation.")
    remediation_plan: Optional[RemediationPlan] = Field(None, description="Generated remediation plan.")
    executed_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Audit log of executed tool actions.")
    verification_results: Optional[Dict[str, Any]] = Field(None, description="Post-action state verification results.")
    final_outcome: str = Field("PENDING", description="Final resolution summary or failure reason.")
    timeline: List[IncidentTimelineEntry] = Field(default_factory=list, description="Chronological event timeline.")
    audit_reference: Optional[str] = Field(None, description="PostgreSQL audit log reference identifier.")

    model_config = ConfigDict(arbitrary_types_allowed=True)
