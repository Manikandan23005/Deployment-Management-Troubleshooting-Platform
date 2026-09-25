# --- Strongly-Typed Tool System Data Models ---
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Type
from pydantic import BaseModel, Field, ConfigDict
import datetime
import uuid
from app.agent.risk_policy import RiskLevel

class ToolCategory(str, Enum):
    KUBERNETES = "KUBERNETES"
    PROMETHEUS = "PROMETHEUS"
    LOKI = "LOKI"
    ARGOCD = "ARGOCD"
    GIT = "GIT"
    SYSTEM = "SYSTEM"

class OperationType(str, Enum):
    READ = "READ"
    MUTATE = "MUTATE"

class ToolExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_INPUT = "INVALID_INPUT"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    TIMEOUT = "TIMEOUT"

class ToolResult(BaseModel):
    """Standardized result returned by all deterministic DevOps tools."""
    tool: str = Field(..., description="Tool unique name identifier.")
    status: ToolExecutionStatus = Field(..., description="Execution outcome status.")
    data: Optional[Any] = Field(None, description="Structured output payload on success.")
    error: Optional[str] = Field(None, description="Detailed error description on failure.")
    evidence_type: str = Field("SYSTEM", description="Telemetry source or evidence category.")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    target: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Resolved operational target metadata.")
    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")

    @property
    def success(self) -> bool:
        return self.status == ToolExecutionStatus.SUCCESS

class ToolDefinition(BaseModel):
    """Contract definition for a registered deterministic DevOps infrastructure tool."""
    name: str = Field(..., description="Unique tool identifier, e.g. 'k8s.list_pods'.")
    description: str = Field(..., description="Clear human-readable description of what the tool does.")
    category: ToolCategory = Field(..., description="Subsystem category.")
    provider: str = Field("kubernetes", description="Underlying client/integration provider.")
    operation_type: OperationType = Field(OperationType.READ, description="READ or MUTATE.")
    risk_level: RiskLevel = Field(RiskLevel.READ_ONLY, description="Risk classification tier.")
    required_permission: str = Field("pods:view", description="IAM resource:action permission string.")
    requires_confirmation: bool = Field(False, description="Whether confirmation is required before execution.")
    input_schema: Optional[Type[BaseModel]] = Field(None, description="Pydantic schema class for input validation.")
    output_schema: Optional[Type[BaseModel]] = Field(None, description="Pydantic schema class for output validation.")
    handler: Optional[Callable[..., Any]] = Field(None, description="Deterministic Python execution handler function.")
    supports_environment: bool = Field(True, description="Whether tool accepts environment scoping.")
    supports_cluster_scope: bool = Field(True, description="Whether tool accepts cluster_id scoping.")
    supports_namespace_scope: bool = Field(True, description="Whether tool accepts namespace scoping.")
    supports_application_scope: bool = Field(True, description="Whether tool accepts application scoping.")

    model_config = ConfigDict(arbitrary_types_allowed=True)

# --- Base & Concrete Tool Input Schemas ---

class BaseToolInput(BaseModel):
    cluster_id: Optional[str] = Field(None, description="Target Kubernetes cluster identifier.")
    environment: Optional[str] = Field(None, description="Resolved target environment (e.g. Amazon EKS, On-Prem).")

# Kubernetes Inputs
class ListNamespacesInput(BaseToolInput):
    pass

class ListPodsInput(BaseToolInput):
    namespace: Optional[str] = Field(None, description="Target namespace (e.g. devops-nexus-prod).")

class GetPodInput(BaseToolInput):
    namespace: str = Field(..., description="Pod namespace.")
    name: str = Field(..., description="Pod name.")

class GetPodLogsInput(BaseToolInput):
    namespace: str = Field(..., description="Pod namespace.")
    name: str = Field(..., description="Pod name.")
    tail_lines: int = Field(50, description="Number of trailing log lines.")
    container: Optional[str] = Field(None, description="Target container name.")

class ListDeploymentsInput(BaseToolInput):
    namespace: Optional[str] = Field(None, description="Deployment namespace.")

class GetDeploymentInput(BaseToolInput):
    namespace: str = Field(..., description="Deployment namespace.")
    name: str = Field(..., description="Deployment name.")

class ScaleDeploymentInput(BaseToolInput):
    namespace: str = Field(..., description="Deployment namespace.")
    name: str = Field(..., description="Deployment name.")
    replicas: int = Field(..., ge=0, le=100, description="Target desired replica count.")

class RestartDeploymentInput(BaseToolInput):
    namespace: str = Field(..., description="Deployment namespace.")
    name: str = Field(..., description="Deployment name.")

class DeletePodInput(BaseToolInput):
    namespace: str = Field(..., description="Pod namespace.")
    name: str = Field(..., description="Pod name.")

class ListServicesInput(BaseToolInput):
    namespace: Optional[str] = Field(None, description="Service namespace.")

class GetServiceInput(BaseToolInput):
    namespace: str = Field(..., description="Service namespace.")
    name: str = Field(..., description="Service name.")

class ListNodesInput(BaseToolInput):
    pass

class GetNodeInput(BaseToolInput):
    name: str = Field(..., description="Node name.")

class ListEventsInput(BaseToolInput):
    namespace: Optional[str] = Field(None, description="Events namespace.")
    resource_name: Optional[str] = Field(None, description="Optional resource name filter.")

# Prometheus Inputs
class PrometheusQueryInput(BaseToolInput):
    query: str = Field(..., description="PromQL instantaneous query expression.")

class PrometheusRangeInput(BaseToolInput):
    query: str = Field(..., description="PromQL range query expression.")
    start: Optional[float] = Field(None, description="Start unix timestamp.")
    end: Optional[float] = Field(None, description="End unix timestamp.")
    step: str = Field("15s", description="Query resolution step string.")

class PrometheusClusterMetricsInput(BaseToolInput):
    namespace: Optional[str] = Field(None, description="Optional namespace scope.")
    application: Optional[str] = Field(None, description="Optional application scope.")

# Loki Inputs
class LokiQueryInput(BaseToolInput):
    query: str = Field(..., description="LogQL query expression.")
    limit: int = Field(50, description="Maximum number of log entries to retrieve.")

class LokiRangeInput(BaseToolInput):
    query: str = Field(..., description="LogQL query expression.")
    limit: int = Field(50, description="Maximum log limit.")
    start: Optional[float] = Field(None, description="Start timestamp.")
    end: Optional[float] = Field(None, description="End timestamp.")

class LokiSearchErrorsInput(BaseToolInput):
    namespace: str = Field("devops-nexus-prod", description="Target namespace.")
    limit: int = Field(20, description="Max error lines.")
    application: Optional[str] = Field(None, description="Optional application name filter.")

# ArgoCD Inputs
class ArgoCDListAppsInput(BaseToolInput):
    pass

class ArgoCDGetAppInput(BaseToolInput):
    name: str = Field(..., description="ArgoCD application name.")

class ArgoCDRefreshAppInput(BaseToolInput):
    name: str = Field(..., description="ArgoCD application name.")

class ArgoCDSyncAppInput(BaseToolInput):
    name: str = Field(..., description="ArgoCD application name.")

# Git Inputs
class GitGetRepoInput(BaseModel):
    owner: str = Field("Manikandan23005", description="Repository owner/org.")
    repo: str = Field("Microservice-Deployment-Monitoring-Platform", description="Repository name.")

class GitGetBranchInput(BaseModel):
    owner: str = Field("Manikandan23005", description="Repository owner/org.")
    repo: str = Field("Microservice-Deployment-Monitoring-Platform", description="Repository name.")

class GitGetCommitInput(BaseModel):
    owner: str = Field("Manikandan23005", description="Repository owner/org.")
    repo: str = Field("Microservice-Deployment-Monitoring-Platform", description="Repository name.")

class GitUpdateFileInput(BaseModel):
    owner: str = Field("Manikandan23005", description="Repository owner/org.")
    repo: str = Field("Microservice-Deployment-Monitoring-Platform", description="Repository name.")
    path: str = Field(..., description="Target file path in repository.")
    content: str = Field(..., description="Updated file content.")
    message: str = Field(..., description="Commit message.")
    branch: str = Field("main", description="Target branch.")

class GitCommitInput(BaseModel):
    message: str = Field(..., description="Commit message.")
    author: Optional[str] = Field(None, description="Commit author.")

class GitPushInput(BaseModel):
    branch: str = Field("main", description="Target branch.")
