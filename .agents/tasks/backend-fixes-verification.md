# Backend Reliability Fixes — Verification Note

Date: 2026-10-08
Branch: `main`
Git author (repo-local): `Manikandan23005 <manikandan20684455@gmail.com>`
AWS account: `605294565283` only (unchanged). EKS cluster `devops-nexus-prod`, region `ap-south-1`.

Backend rebuilt and restarted with:
```
docker compose up -d --build platform-backend
```
Result: image built, `devops-nexus-backend` recreated and started.

---

## BUG 1 — Missing Postgres driver (psycopg v3)

Root cause: `DATABASE_URL` uses the bare `postgresql://` scheme, so SQLAlchemy 2.0 selects the
default DBAPI `psycopg` (v3). The manifest only shipped `psycopg2-binary`, so startup logged
`PostgreSQL connection initialization failed: No module named 'psycopg'`, which disabled the
DB-backed cluster/user/audit persistence.

Fix: added `psycopg = {extras = ["binary"], version = "^3.1.18"}` to root `pyproject.toml`
(the manifest the Docker image installs from via Poetry). Kept `psycopg2-binary` untouched.

Verification:
```
$ docker exec devops-nexus-backend python -c "import psycopg; print(psycopg.__version__)"
3.3.6

$ docker logs devops-nexus-backend | grep -iE "psycopg|Successfully connected to PostgreSQL"
[INFO] Successfully connected to PostgreSQL and initialized tables.
# (no "No module named 'psycopg'" error in the post-rebuild startup)
```
API login returns a token:
```
POST /api/v1/auth/login {"username":"admin","password":"DevOpsNexus@123"}
-> success:true, data.token = <196-char JWT>
```
Note: the login payload returns the token under `data.token` (existing contract), not a
top-level `access_token`. Authenticated calls with `Authorization: Bearer <data.token>` succeed.

---

## BUG 2 — EKS cluster never registered at runtime

Root cause chain: the cluster registry is populated at startup by
`platform_initializer.initialize_platform()` step 1.5
(`aws_account_registry.register_eks_cluster_as_target(...)` which DOES call
`cluster_registry.add_cluster(...)`). Two things made this fragile/empty:
1. Any failure in that registration was swallowed at `logger.debug` level (invisible), and
2. with BUG 1 unfixed the registry was in-memory only (not persisted to Postgres), so it was
   lost on restart and depended entirely on the one swallowed startup call.

Fix:
- BUG 1 fix makes the registry DB-backed (clusters persist to the `clusters` table).
- In `platform_initializer.py`: raised the swallowed EKS-link failure from `debug` to `warning`
  so a real failure is visible, and added a post-bootstrap registry verification log
  (`Cluster Registry populated with N cluster(s)` / loud warning if empty).

Verification:
```
$ docker exec devops-nexus-backend python -c "from app.services.cluster_registry import cluster_registry; print(len(cluster_registry.list_clusters()))"
1

$ docker logs devops-nexus-backend | grep -E "Linked persistent EKS|Cluster Registry populated"
[INFO] ✅ Linked persistent EKS cluster 'devops-nexus-prod' as active target.
[INFO] ✅ Cluster Registry populated with 1 cluster(s).
```
Authenticated API (Bearer token from login):
```
GET /api/v1/k8s/nodes            -> success:true, 2 nodes
GET /api/v1/k8s/pods             -> success:true, 32 pods
GET /api/v1/monitoring/logs?pod=all -> success:true, 100 log lines (K8s API fallback path;
                                       Loki URL is intentionally unresolvable from compose)
GET /api/v1/monitoring/metrics   -> success:true, error:None
```

---

## BUG 3 — Error-swallowing masks failures as success

Root cause: read endpoints caught exceptions and returned `success:true` with empty/zero data,
so a genuine client/metrics failure was indistinguishable from a truly empty cluster.

Fix: on a genuine failure these endpoints now return `success:false` with an `error`
(`ErrorDetail`) carrying the original exception message, while still returning `success:true`
with empty data when the cluster legitimately has no such resources (the Kubernetes client
raises `KubernetesClientException` only on real SDK failures and returns empty lists on a
successful-but-empty API response). Response shape stays `BaseResponse` (backward compatible).

- `app/routers/k8s.py`: `list_namespaces`, `list_nodes`, `list_pods`, `list_deployments`,
  `list_ingresses` → `success:false` + `error.code=KUBERNETES_CLIENT_ERROR` on
  `KubernetesClientException`.
- `app/routers/monitoring.py`: `get_cluster_metrics`, `get_metrics_range`, `get_logs`,
  `get_alerts` → `success:false` + error code (`METRICS_FETCH_ERROR` / `LOG_FETCH_ERROR` /
  `ALERTS_FETCH_ERROR`) on genuine failure, data shape preserved.

The original cause is preserved through `app/clients/kubernetes.py` (unchanged — it already
wraps and re-raises `KubernetesClientException` with the SDK message).

Verification (injected a genuine client failure):
```
$ docker exec devops-nexus-backend python -c "<patch node_service.list_nodes to raise KubernetesClientException('Failed to list worker nodes: (401) Unauthorized token')>"
[ERROR] Node listing failed: Failed to list worker nodes: (401) Unauthorized token
nodes success= False | error= KUBERNETES_CLIENT_ERROR | Failed to list worker nodes: (401) Unauthorized token
```
Live (healthy cluster) calls still return `success:true` with real data (see BUG 2).

Frontend: `platform/frontend/src/services/api.ts` getters already guard on
`response.data.success` and fall through to a safe empty result when `success` is false, so the
new `success:false` responses are handled without crashing or rendering stale data. No frontend
change was required (task said minimal / no rewrite).

---

## BUG 4 — Bedrock AI config region/model + fragile verification gate

Fix:
- `platform/shared/config.py`: `BEDROCK_REGION` default → `ap-south-1`,
  `BEDROCK_MODEL_ID` default → `apac.amazon.nova-pro-v1:0`; added `AWS_REGION` field
  (default `ap-south-1`).
- `docker-compose.yml`: backend `BEDROCK_REGION` default → `ap-south-1`,
  `BEDROCK_MODEL_ID` default → `apac.amazon.nova-pro-v1:0`.
- `.env.example`: documented `BEDROCK_REGION`, `BEDROCK_MODEL_ID`, `AWS_REGION`.
- `platform/backend/app/clients/llm.py`:
  - `_resolve_region()` now falls back to `AWS_REGION` (then `DEFAULT_AWS_REGION`, then
    `ap-south-1`) instead of hardcoded `us-east-1`.
  - `candidate_models` now uses APAC profiles
    (`apac.amazon.nova-pro-v1:0`, `apac.amazon.nova-lite-v1:0`,
    `apac.anthropic.claude-3-5-sonnet-20241022-v2:0`).
  - Removed the hard `_bedrock_verified` block in `_generate_bedrock_response`; it now attempts
    the real converse call and surfaces the ACTUAL AWS error string in the raised
    `DevOpsNexusException` instead of the generic "pending AWS account verification".

IMPORTANT: Bedrock in this account currently returns an account-level
`Operation not allowed` (expected — the user is unblocking model access separately via the
console/CLI). This is NOT a task failure; the task scope is correct config + honest errors.

Verification:
```
$ docker exec devops-nexus-backend python -c "from app.clients.llm import llm_client; print(llm_client._resolve_region())"
ap-south-1
$ ... settings.BEDROCK_MODEL_ID -> apac.amazon.nova-pro-v1:0
$ ... settings.AWS_REGION      -> ap-south-1

$ docker exec devops-nexus-backend python -c "<call llm_client.generate_chat_response('ping test', ...)>"
RAISED: AWS Bedrock model invocation failed in region 'ap-south-1': An error occurred
        (ValidationException) when calling the Converse operation: Operation not allowed
contains_generic_pending = False
contains_real_aws_text   = True
```
The error now carries the real AWS reason, so the UI shows the true cause.

---

## Cleanup
No temporary debug logging left behind. The only new logs are intentional, useful startup
diagnostics (BUG 2 registry population / EKS-link warning).
