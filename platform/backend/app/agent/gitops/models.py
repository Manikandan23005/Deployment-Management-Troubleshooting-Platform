# --- Strongly-Typed GitOps Control Plane Data Models ---
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import datetime
import uuid

class GitOpsStage(str, Enum):
    # Progression Stages
    PLANNED = "PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    GIT_MODIFYING = "GIT_MODIFYING"
    GIT_VALIDATING = "GIT_VALIDATING"
    GIT_COMMITTING = "GIT_COMMITTING"
    GIT_PUSHING = "GIT_PUSHING"
    ARGOCD_REFRESHING = "ARGOCD_REFRESHING"
    ARGOCD_SYNCING = "ARGOCD_SYNCING"
    RECONCILING = "RECONCILING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"

    # Explicit Failure Stages
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    GIT_VALIDATION_FAILED = "GIT_VALIDATION_FAILED"
    GIT_COMMIT_FAILED = "GIT_COMMIT_FAILED"
    GIT_PUSH_FAILED = "GIT_PUSH_FAILED"
    ARGOCD_SYNC_FAILED = "ARGOCD_SYNC_FAILED"
    ROLLOUT_FAILED = "ROLLOUT_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TIMEOUT = "TIMEOUT"

class GitOpsOwnership(BaseModel):
    """Deterministic GitOps ownership resolution metadata for an application/deployment."""
    is_gitops: bool = Field(False, description="Whether target is actively managed by ArgoCD GitOps.")
    target_name: str = Field(..., description="Target deployment or workload name.")
    namespace: str = Field("devops-nexus-prod", description="Target namespace.")
    argocd_app_name: Optional[str] = Field(None, description="Matched ArgoCD application identifier.")
    repo_url: Optional[str] = Field(None, description="Upstream Git repository URL.")
    branch: str = Field("main", description="Git target branch/revision.")
    helm_chart_path: Optional[str] = Field(None, description="Path to Helm chart directory.")
    values_files: List[str] = Field(default_factory=list, description="Associated Helm value files.")
    target_values_file: Optional[str] = Field(None, description="Resolved absolute or relative path to target values.yaml.")
    cluster_id: Optional[str] = Field(None, description="Target cluster ID.")

class GitChangePreview(BaseModel):
    """Structured diff and change preview before applying mutations to Git repository."""
    target_resource: str = Field(..., description="Target workload name.")
    environment: str = Field("On-Premises", description="Environment scope.")
    cluster: str = Field("default", description="Cluster name.")
    namespace: str = Field("devops-nexus-prod", description="Target namespace.")
    file_path: str = Field(..., description="Target values YAML file path.")
    current_desired_replicas: int = Field(..., description="Replicas before mutation.")
    requested_replicas: int = Field(..., description="Desired replicas after mutation.")
    diff: str = Field(..., description="Unified diff representation of Git change.")
    is_valid_yaml: bool = Field(True, description="Whether generated YAML passed syntax validation.")
    risk_level: str = Field("MEDIUM", description="Assessed risk level.")
    gitops_enabled: bool = Field(True, description="Whether GitOps reconciliation is active.")
    argocd_app: Optional[str] = Field(None, description="Matched ArgoCD app name.")

class GitCommitResult(BaseModel):
    """Result of staging, committing, and pushing desired state changes."""
    success: bool = Field(..., description="Whether commit and push succeeded.")
    commit_sha: Optional[str] = Field(None, description="Generated Git commit SHA.")
    commit_message: str = Field(..., description="Commit message used.")
    branch: str = Field("main", description="Target Git branch.")
    files_changed: List[str] = Field(default_factory=list, description="List of files modified.")
    error: Optional[str] = Field(None, description="Error message on failure.")

class GitOpsScaleStep(BaseModel):
    """Progress tracker step for GitOps operations visualizer."""
    step: int = Field(..., description="Step sequence number (1-based).")
    name: str = Field(..., description="Human-readable step name.")
    stage: GitOpsStage = Field(..., description="Granular state enum.")
    status: str = Field("pending", description="Step status: 'pending', 'in_progress', 'completed', 'failed'.")
    message: Optional[str] = Field(None, description="Optional step detail message.")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

class GitOpsScaleResult(BaseModel):
    """End-to-end verified execution result for a deployment scale operation."""
    success: bool = Field(..., description="Whether the entire GitOps lifecycle completed and verified.")
    is_gitops: bool = Field(..., description="Whether operation was executed via GitOps.")
    stage: GitOpsStage = Field(..., description="Final or current lifecycle stage.")
    gitops_app: Optional[str] = Field(None, description="ArgoCD application name.")
    replicas: int = Field(..., description="Target replica count.")
    previous_replicas: Optional[int] = Field(None, description="Previous replica count.")
    git_commit_sha: Optional[str] = Field(None, description="Git commit SHA if committed.")
    steps: List[Dict[str, Any]] = Field(default_factory=list, description="Step progression list for UI.")
    verification: Optional[Dict[str, Any]] = Field(None, description="VerificationEngine comparison payload.")
    message: str = Field(..., description="Human-readable summary message.")
    preview: Optional[Dict[str, Any]] = Field(None, description="Change preview if approval was required.")
    execution_id: str = Field(default_factory=lambda: f"gitops-scale-{uuid.uuid4().hex[:8]}")
