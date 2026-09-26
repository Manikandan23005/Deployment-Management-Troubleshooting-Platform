# DevOps Nexus — Unified EKS & On-Premises Architecture & Observability Guide

## 1. Unified Control Plane Overview

DevOps Nexus operates as a single, unified DevOps and autonomous troubleshooting control plane capable of governing workloads across both **Amazon EKS** and **On-Premises Kubernetes**.

```
                        DEVOPS NEXUS CONTROL PLANE
                                     │
                              AgentRuntime
                                     │
                              TargetResolver
                                     │
                              ScopeContext
                                     │
                   ┌─────────────────┴─────────────────┐
                   │                                   │
              Amazon EKS                    On-Premises Kubernetes
       (AWS Account: 605294565283)            (Cluster: onprem-prod)
                   │                                   │
            KubernetesClient                    KubernetesClient
                   │                                   │
       ┌───────────┼───────────┐           ┌───────────┼───────────┐
       │           │           │           │           │           │
      K8s       Metrics       Logs        K8s       Metrics       Logs
    (K8s API) (Prometheus)   (Loki)     (K8s API) (Prometheus)   (Loki)
       │           │           │           │           │           │
       └───────────┼───────────┘           └───────────┼───────────┘
                   │                                   │
                   └─────────────────┬─────────────────┘
                                     │
                           Evidence Correlation
                                     │
                             Root Cause Engine
                                     │
                            Remediation Planner
                                     │
                             RiskPolicyEngine
                                     │
                               ToolRegistry
                                     │
                            VerificationEngine
```

---

## 2. Observability Architecture on Amazon EKS (Phase 8)

The EKS Observability stack runs in the dedicated `monitoring` namespace and collects cluster, node, container, and application signals:

```
                                 Amazon EKS
                                     │
               ┌─────────────────────┼─────────────────────┐
               │                     │                     │
            Metrics                Logs                 Events
               │                     │                     │
          Prometheus               Loki              Kubernetes API
          (v2.53.0)              (v3.0.0)                  │
               │                     │                     │
               │               Promtail (DaemonSet)        │
               │                     │                     │
               └─────────────────────┼─────────────────────┘
                                     │
                                  Grafana
                                 (v11.0.0)
                                     │
                               Alertmanager
                                     │
                                DevOps Nexus
                                     │
                             Root Cause Engine
```

### 2.1 Prometheus Telemetry
- **Endpoint**: `http://prometheus-service.monitoring.svc.cluster.local:9090`
- **Scrape Targets**: Kubernetes node metrics (`node-exporter`), container cAdvisor metrics, Kubernetes API server, kube-state-metrics, and application `/metrics` endpoints.
- **Alert Rules**:
  - `HighErrorRate`: HTTP 5xx error rate > 5% over 5m
  - `PodCrashLoopBackOff`: Repeated container restart loops
  - `DeploymentReplicaMismatch`: Ready replicas < desired replicas
  - `NodeNotReady`: Node status not Ready > 2m

### 2.2 Centralized Logging (Loki + Promtail)
- **Loki Endpoint**: `http://loki-service.monitoring.svc.cluster.local:3100`
- **Collector**: Promtail DaemonSet mounted to `/var/log/pods` on all worker nodes.
- **Labels**: `namespace`, `pod`, `container`, `app`.
- **Zero-Drop LogQL**: Queried directly by `LokiClient` and `loki.query` tool.

### 2.3 Grafana Dashboards
- **Endpoint**: `http://grafana-service.monitoring.svc.cluster.local:3000`
- **Pre-provisioned Dashboards**:
  - Cluster Overview (Node CPU/Memory, Pod counts, Network I/O)
  - Application Telemetry (Request throughput, 5xx errors, P95/P99 latency)
  - Kubernetes Health (CrashLoopBackOff, OOMKilled, Pod Restarts, Probe status)

---

## 3. Autonomous Multi-Dimensional Root Cause Correlation

The `RootCauseEngine` correlates 5 independent dimensions before rendering deterministic diagnoses:

1. **Kubernetes API State**: Pod phase, container exit codes, termination reasons, events.
2. **Prometheus Metrics**: Error rate %, CPU/Memory utilization gauges, restart rate.
3. **Loki Logs**: Unhandled exception traces, HTTP 500 error logs, database timeouts.
4. **ArgoCD GitOps State**: Sync status (`Synced`, `OutOfSync`, `Failed`), health status.
5. **Git Repository Desired State**: Target values YAML, replica counts, image tags.

### Example Correlation Matrix:

| Incident Pattern | K8s State | Prometheus Metric | Loki Log | ArgoCD State | Root Cause Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OOMKilled** | Exit Code 137, OOMKilled | Memory > 95% | "Out of memory" | Synced | `FailureCategory.OOM_KILLED` |
| **CrashLoopBackOff** | CrashLoopBackOff, Restarts > 0 | Crash count high | Stacktrace / Error | Synced | `FailureCategory.CRASH_LOOP_BACKOFF` |
| **ImagePullBackOff** | ImagePullBackOff / ErrImagePull | N/A | "Failed to pull" | Synced | `FailureCategory.IMAGE_PULL_BACKOFF` |
| **App HTTP 500** | Pod Running & Ready (1/1) | 5xx Rate > 5% | 500 Exception trace | Synced | `FailureCategory.HIGH_ERROR_RATE` / `APPLICATION_EXCEPTION` |
| **GitOps Drift** | Replicas = 1 | N/A | N/A | OutOfSync (Git = 3) | `FailureCategory.GITOPS_CONFIG_MISMATCH` |

---

## 4. Unified Multi-Environment Operations (Phase 9)

### 4.1 Target Resolution (`TargetResolver`)
- Natural language queries like `"Check gateway in EKS prod"` resolve to:
  ```json
  {
    "environment": "Amazon EKS",
    "environment_type": "AWS_EKS",
    "cluster_id": "devops-nexus-prod",
    "namespace": "devops-nexus-prod",
    "application": "gateway",
    "aws_account_id": "605294565283",
    "region": "ap-south-1"
  }
  ```
- Natural language queries like `"Check gateway in on-prem"` resolve to:
  ```json
  {
    "environment": "On-Premises Kubernetes",
    "environment_type": "ON_PREM_KUBERNETES",
    "cluster_id": "onprem-prod",
    "namespace": "devops-nexus-prod",
    "application": "gateway"
  }
  ```
- Ambiguous prompts without target workloads trigger clear clarification requests.

### 4.2 Cross-Environment Workload Comparison
Operators can execute side-by-side factual comparisons across EKS and On-Premises environments:
```python
report = target_resolver.compare_workload_environments("gateway", envs=["AWS_EKS", "ON_PREM_KUBERNETES"])
```

### 4.3 Verified Remediation Flow
Every remediation action (scale, restart, GitOps sync) is validated through `VerificationEngine`:
1. **Pre-Action Snapshot**: Pods, ArgoCD sync, Git desired state, firing alerts.
2. **Execution**: Mediated exclusively through strongly-typed `ToolRegistry` with RBAC and Risk evaluation.
3. **Post-Action Verification**: Pod ready states, ArgoCD reconciliation, Prometheus error clearance, and telemetry stabilization.
