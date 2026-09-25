# Autonomous AIOps Troubleshooting & Verified Remediation Architecture

## Overview

The **DevOps Nexus Autonomous Troubleshooting & Verified Remediation Engine** elevates the platform from an investigation-capable assistant into a controlled, closed-loop DevOps operations agent operating across on-premise Kubernetes and multi-account Amazon EKS environments.

The core invariant is that the Large Language Model (LLM) functions strictly as a reasoning, synthesis, and explanation layer. The LLM **never** executes arbitrary shell commands, raw `kubectl`, direct cloud APIs, or direct Git mutations. Every infrastructure mutation must:
1. Originate from a deterministic, strongly typed `RemediationPlan`
2. Pass fine-grained RBAC authorization via `ToolPermissionManager`
3. Comply with risk policies and confirmation requirements via `RiskPolicyEngine`
4. Execute via the strongly typed `ToolRegistry` through the environment-aware `KubernetesClientFactory`
5. Be verified against live cluster and GitOps state via `VerificationEngine`
6. Feed into a closed-loop safety guard that re-investigates or escalates if post-action verification fails.

---

## 🏛️ Autonomous Operational Architecture (`app/agent/`)

```
User Request / Alert
         │
         ▼
Intent Detection (`IntentEngine`)
         │
         ▼
Target Scope Resolution (`TargetResolver` -> Environment, AWS Account, Region, EKS Cluster, Namespace, Workload)
         │
         ▼
Investigation Planner (`InvestigationPlanner`)
         │
         ▼
Parallel Evidence Collection (`ToolScheduler` across K8s/EKS, ArgoCD, Prom, Loki, Git)
         │
         ▼
15-Class Root Cause Failure Analysis (`RootCauseEngine`)
         │
         ▼
Dedicated Remediation Planning (`RemediationPlanner` -> `RemediationPlan`)
         │
         ▼
Risk Classification & Confirmation Check (`RiskPolicyEngine` / `ToolPermissionManager`)
         │
         ├── [High/Unconfirmed] ──► Status: AWAITING_APPROVAL (Requires Confirm Token)
         │
         ▼ [Approved / Low Risk]
ToolRegistry Execution (`ToolRegistry.execute`)
         │
         ▼
Environment-Aware K8s Client Factory (`KubernetesClientFactory`)
         ├── On-Premise / Local K8s ──► In-cluster / Kubeconfig API client
         └── AWS Amazon EKS ──────────► Dynamic STS AssumeRole presigned token client
         │
         ▼
Real Infrastructure Mutation (K8s API / GitOps Workflow Engine / ArgoCD)
         │
         ▼
Live State Verification (`VerificationEngine`)
         │
         ├── Verification PASSED ──► Status: COMPLETED (Audit Log + Full Timeline)
         │
         └── Verification FAILED
                  │
                  ▼
         Closed-Loop Re-Investigation (Attempt 2: Collect fresh live evidence)
                  │
                  ▼
         Safe Secondary Action Evaluation
                  │
                  ├── If Safe & Authorized ──► Re-execute & Re-verify
                  │
                  └── If Unresolved ────────► Status: ESCALATED to Operations Team
```

---

## 📋 Environment-Aware Scope Context (`app/agent/models.py`)

Every operational troubleshooting session creates and maintains a strongly typed `ScopeContext` with multi-environment support:

| Field | Type | Description |
| :--- | :--- | :--- |
| `environment` | `str` | `KUBERNETES` (default/on-premise) or `AWS_EKS`. |
| `aws_account_id` | `Optional[str]` | 12-digit AWS Account ID (e.g. `123456789012`). |
| `aws_account_name` | `Optional[str]` | Friendly account label (e.g. `Production AWS`). |
| `region` | `Optional[str]` | AWS Region for target cluster (e.g. `us-east-1`, `ap-south-1`). |
| `cluster` | `Optional[str]` | Active cluster identifier or EKS cluster name. |
| `namespace` | `str` | Target namespace (e.g. `devops-nexus-prod`). |
| `application` | `Optional[str]` | Target application (e.g. `gateway-service`). |
| `workload` | `Optional[str]` | Target deployment or workload name. |

---

## 📋 Autonomous Incident Model (`app/agent/models.py`)

Every operational troubleshooting session creates and maintains a strongly typed `AutonomousIncident` record:

| Field | Type | Description |
| :--- | :--- | :--- |
| `incident_id` | `str` | Unique incident identifier (e.g. `inc-7f8d12a4`). |
| `user_request` | `str` | Initial user problem prompt or alert payload. |
| `target_scope` | `ScopeContext` | Environment (`KUBERNETES`, `AWS_EKS`), cluster, namespace, workload. |
| `status` | `IncidentStatus` | `INVESTIGATING`, `DIAGNOSING`, `PLAN_GENERATED`, `AWAITING_APPROVAL`, `APPROVED`, `EXECUTING`, `VERIFYING`, `REMEDIATING`, `COMPLETED`, `FAILED`, `ESCALATED`. |
| `failure_category` | `FailureCategory` | One of 16 discrete failure classes. |
| `severity` | `str` | `Critical`, `High`, `Warning`, `Info`. |
| `confidence` | `Dict` | Score ($0-100\%$) and evidence quality (`HIGH`, `MEDIUM`, `LOW`). |
| `evidence` | `Dict` | Full multi-source empirical evidence graph. |
| `diagnosis` | `Dict` | Structured root cause and supporting evidence items. |
| `remediation_plan` | `RemediationPlan` | Ordered list of `RemediationAction`s with verification and rollback criteria. |
| `executed_actions` | `List[Dict]` | Audit trail of executed `ToolResult` outputs. |
| `verification_results` | `Dict` | Pre-action vs post-action state comparison snapshot. |
| `timeline` | `List[IncidentTimelineEntry]` | Chronological audit log with event timestamps and stages. |
| `final_outcome` | `str` | Final resolution narrative or escalation justification. |

---

## 🔍 15-Class Root Cause Analysis Engine (`RootCauseEngine`)

Deterministic multi-dimensional correlation matches empirical facts prior to LLM reasoning:

1. **`CrashLoopBackOff`**: Pod status `CrashLoopBackOff`, exit code $>0$, or repeated container restarts.
2. **`OOMKilled`**: Linux kernel exit code `137`, last state reason `OOMKilled`, or warning event `OOMKilled`.
3. **`ImagePullBackOff`**: Kubelet waiting reason `ImagePullBackOff` or back-off pulling image event.
4. **`ErrImagePull`**: Nonexistent image tag, registry connectivity timeout, or missing pull secret.
5. **`PendingPod`**: Pod stuck in `Pending` phase waiting for volume mounts or admission controllers.
6. **`FailedScheduling`**: Node resource pressure (`Insufficient cpu`, `Insufficient memory`, or untolerated taints).
7. **`DeploymentUnavailable`**: Deployment desired replicas $>0$ with $0$ ready replicas.
8. **`ReadinessProbeFailure`**: HTTP/TCP readiness probe failures blocking traffic routing.
9. **`LivenessProbeFailure`**: Liveness probe timeouts causing Kubelet to restart containers.
10. **`HighRestartCount`**: Workload with $\ge 5$ container restarts or namespace total $\ge 10$.
11. **`HighCPU`**: Prometheus CPU utilization gauge $>80\%$.
12. **`HighMemory`**: Prometheus memory gauge $>85\%$ (warning before OOM eviction).
13. **`ArgoCDOutOfSync`**: GitOps controller state `OutOfSync` or `Degraded`.
14. **`ArgoCDSyncFailure`**: ArgoCD sync operation failed due to Helm syntax or controller errors.
15. **`GitOpsConfigMismatch`**: Live deployment replica count diverges from Git repository source of truth.
16. **`HealthyWorkload`**: All pods running, probes passing, and GitOps controller synced.

---

## 🛠️ Remediation Planning & Idempotency (`RemediationPlanner`)

The `RemediationPlanner` maps diagnosed failure classes to strongly typed `ToolRegistry` actions with built-in idempotency:

* **Rollout Restart (`k8s.restart_deployment`)**: For `CrashLoopBackOff`, probe failures, or hung runtime state.
* **Scale Workload (`k8s.scale_deployment` / GitOps change engine)**: For `HighCPU`, `HighMemory`, or resource pressure. If GitOps-managed, generates a unified diff preview of `values.yaml` before applying.
* **ArgoCD Sync (`argocd.sync_application`)**: For `OutOfSync` or drift. **Idempotency Guard**: If ArgoCD is already `Synced`, swaps to safe `argocd.refresh_application` to prevent redundant controller load.
* **GitOps Rollback / Code Fix Escalation**: For `ImagePullBackOff` / `ErrImagePull`, flags invalid image tag for operator approval rather than attempting blind destructive mutations.

---

## 🛡️ Risk Gating & Authorization Policies

| Risk Tier | Examples | Execution Policy |
| :--- | :--- | :--- |
| **`READ_ONLY`** | `k8s.list_pods`, `prometheus.query`, `loki.query` | Executed automatically for all authorized roles. |
| **`LOW`** | `k8s.restart_deployment`, `argocd.refresh_application` | Executed automatically if user/agent has mutating RBAC role. |
| **`MEDIUM`** | `k8s.scale_deployment`, `argocd.sync_application` | Gated by policy; requires approval or explicit execution. |
| **`HIGH`** | `k8s.delete_pod`, destructive mutations, Git pushes | Always requires explicit confirmation token (`confirm_token`). |

---

## 🔄 Closed-Loop Verification & Safety Engine (`VerificationEngine`)

Verification evaluates live infrastructure state snapshots before and after execution:
* **Scale Verification**: Verifies `git_desired_replicas == target`, `deployment_ready_replicas >= target`, and `argocd_sync == 'Synced'`.
* **Restart Verification**: Verifies new pods created, ready count $>0$, and no immediate crash events.
* **Sync Verification**: Verifies ArgoCD application status transitions to `Synced` and `Healthy`.

**Verification Failure Closed-Loop Guard**:
If verification fails post-remediation, DevOps Nexus:
1. Does **not** return fake success.
2. Triggers an automated re-investigation to gather fresh telemetry.
3. If the workload remains unhealthy, transitions to `IncidentStatus.ESCALATED` with complete diagnostic history and alerts the operations team.

---

## 🌐 Autonomous Agent REST API Endpoints (`app/routers/agent.py`)

* `POST /api/v1/agent/troubleshoot`: Initiates autonomous multi-source investigation, runs 15-class root cause analysis, generates a remediation plan, and returns `AutonomousIncident`.
* `POST /api/v1/agent/remediate`: Executes approved remediation plan through `ToolRegistry` with live post-action verification.
* `GET /api/v1/agent/incidents`: Lists all stored incidents sorted chronologically.
* `GET /api/v1/agent/incidents/{incident_id}`: Retrieves full incident evidence graph, diagnosis, and actions.
* `GET /api/v1/agent/incidents/{incident_id}/timeline`: Fetches audit event timeline.
* `POST /api/v1/agent/incidents/{incident_id}/confirm`: Submits confirmation token to approve and execute gated actions.
* `POST /api/v1/agent/tools/execute`: Executes a single registered tool directly through RBAC and risk policy gating.
