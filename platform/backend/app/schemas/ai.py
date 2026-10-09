# --- AI Assistant Validation Schemas ---
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class AIChatRequest(BaseModel):
    """Payload to prompt a chat response."""
    prompt: str = Field(..., description="The user query or context to analyze.")
    provider: Optional[str] = Field(None, description="Select client AI provider: openai, groq, ollama, lmstudio.")
    model: Optional[str] = Field(None, description="Groq/Bedrock model identifier e.g. openai/gpt-oss-20b.")
    session_id: Optional[str] = Field(None, description="Optional conversational session tracking identifier.")
    scope_mode: Optional[str] = Field("cluster", description="Operations scope mode.")
    scope_namespace: Optional[str] = Field("devops-nexus-prod", description="Scope target namespace.")
    scope_app: Optional[str] = Field(None, description="Scope target application name.")
    scope_domain: Optional[str] = Field(None, description="Scope target domain.")

class AIIncidentRequest(BaseModel):
    """Payload to trigger detailed incident diagnostics."""
    pod_name: str = Field(..., description="Target pod identifier.")
    namespace: str = Field(..., description="Namespace scope.")
    logs: str = Field("", description="Snippet of container logs.")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="CPU/Memory utilization gauges.")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Kubernetes lifecycle events list.")
    provider: Optional[str] = Field(None, description="Select client AI provider.")

class AIStructuredResponse(BaseModel):
    summary: str = Field(..., description="High-level summary of the operational status.")
    root_cause: str = Field(..., description="Deep-dive root cause analysis grounded in live telemetry.")
    evidence: List[str] = Field(default_factory=list, description="Concrete metrics, logs, or events logs serving as evidence.")
    affected_resources: List[str] = Field(default_factory=list, description="List of Kubernetes resources affected by the incident.")
    recommendations: List[str] = Field(default_factory=list, description="Actionable remediation steps to fix the issue.")
    severity: str = Field(..., description="Target severity indicator: Info, Warning, Critical.")
    confidence: int = Field(..., description="Analysis confidence percentage score between 0 and 100.")

class AICopilotInvestigateRequest(BaseModel):
    prompt: str = Field(..., description="Investigation prompt or question.")
    resource_name: Optional[str] = Field(None, description="Selected resource name.")
    resource_kind: Optional[str] = Field("deployment", description="Selected resource kind: deployment, pod, namespace, node.")
    namespace: Optional[str] = Field("devops-nexus-prod", description="Namespace scope.")
    cluster_id: Optional[str] = Field("default", description="Active cluster ID.")

class AIGeneratePlanRequest(BaseModel):
    action_type: str = Field(..., description="Action type: restart_deployment, sync_argocd, scale_deployment, etc.")
    target_resource: str = Field(..., description="Target resource name.")
    namespace: Optional[str] = Field("devops-nexus-prod", description="Namespace scope.")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Action parameters e.g. replicas.")
    cluster_id: Optional[str] = Field("default", description="Active cluster ID.")

class AIExecuteStepRequest(BaseModel):
    plan_id: str = Field(..., description="Execution plan ID.")
    step_index: int = Field(..., description="Step index to execute (1-indexed).")
    confirm_token: Optional[str] = Field(None, description="Explicit confirmation token 'CONFIRM' for high-risk actions.")

class AIVerifyRequest(BaseModel):
    target_resource: str = Field(..., description="Target resource name.")
    namespace: Optional[str] = Field("devops-nexus-prod", description="Namespace scope.")
    cluster_id: Optional[str] = Field("default", description="Active cluster ID.")
