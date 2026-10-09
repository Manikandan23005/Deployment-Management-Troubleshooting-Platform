# Backend reliability fixes: Postgres driver, EKS registration visibility, honest read-endpoint errors, Bedrock APAC config

Four backend bugs behind the "dashboard shows 0 pods / 0 nodes" and non-working AI symptoms were fixed across four commits on `main` (`2db553b`, `c5eebd3`, `e91d901`, `c061e65`). The changes add the psycopg v3 driver so the Postgres-backed cluster/user/audit layer actually initializes, make the swallowed EKS-registration failure visible and verify the registry is populated at startup, convert read endpoints from fail-open (masking failures as empty success) to fail-closed (`success:false` + error), and repoint Bedrock from `us-east-1`/`us.*` to `ap-south-1`/`apac.amazon.nova-pro-v1:0` while removing the hard verification gate that masked the real AWS error. The approach is minimal and surgical — no rewrites, config defaults changed in place, error branches rewritten rather than restructured. Watch for: the login contract returns the JWT under `data.token`, not a top-level `access_token` (confirmed) — the verification note calls this out, so authenticated checks used the right field; and Bedrock still returns an account-level `Operation not allowed` at runtime (confirmed, expected per task scope — config and error honesty are what's in scope, not model entitlement).

**Verdict**: APPROVED

## High-level view

BUG 1 is a one-line manifest addition (`psycopg[binary] ^3.1.18`) to the root `pyproject.toml`, which is the manifest the Docker image installs from via Poetry; `psycopg2-binary` is left untouched. The bare `postgresql://` URL makes SQLAlchemy 2.0 pick the v3 DBAPI, which was absent — so the fix targets the actual driver SQLAlchemy selects. Evidence shows `psycopg 3.3.6` importable in the container and a successful PostgreSQL init.

BUG 2 is addressed indirectly plus a visibility change. The registry was already populated at startup by `platform_initializer` step 1.5, but any failure there was logged at `debug` (invisible) and the registry was in-memory only, so a single swallowed call was the whole story. The fix raises that failure to `warning` and adds a post-bootstrap check that logs the registry count (or a loud warning if empty); combined with BUG 1 making the registry DB-backed, the dashboard data paths now have a populated registry. Evidence shows `list_clusters()` returning 1 and `/k8s/nodes`, `/k8s/pods`, `/monitoring/logs` returning real data.

BUG 3 flips the read endpoints in `k8s.py` and `monitoring.py` from fail-open to fail-closed. A genuine client/metrics failure now returns `success:false` with an `ErrorDetail` carrying the original message, while a truly-empty cluster still returns `success:true` with empty data — the distinction rests on the Kubernetes client raising only on real SDK failures. The response stays `BaseResponse`-shaped so it's backward compatible.

BUG 4 moves Bedrock config to the Mumbai region and APAC Nova profile across `config.py`, `docker-compose.yml`, and `.env.example`, fixes the region fallback to use `AWS_REGION` instead of hardcoded `us-east-1`, switches the candidate-model fallbacks to APAC profiles, and removes the hard `_bedrock_verified` block so the real converse call runs and surfaces the actual AWS error. The runtime `Operation not allowed` is an account entitlement issue outside this task's scope.

<details>
<summary>Issues (1)</summary>

1. **Login token field name (informational)** — The login response exposes the JWT under `data.token`, not `access_token`. Not a defect in this change; flagged so downstream consumers and the task's "returns an access_token" criterion are read against the actual contract.

</details>

<details>
<summary>Details</summary>

### psycopg v3 driver added to the manifest SQLAlchemy actually uses

The root `pyproject.toml` gains `psycopg = {extras = ["binary"], version = "^3.1.18"}` alongside the retained `psycopg2-binary`. This matters because `DATABASE_URL` uses the bare `postgresql://` scheme, which makes SQLAlchemy 2.0 resolve to the v3 `psycopg` DBAPI — the module that was missing and threw `No module named 'psycopg'`, disabling DB-backed persistence. Adding the driver to the root manifest (the one the image installs from via Poetry, confirmed by the accompanying `poetry.lock` update bringing in `psycopg_binary-3.3.6` wheels) is the correct target. Evidence: `import psycopg` reports `3.3.6` in the container and startup logs `Successfully connected to PostgreSQL and initialized tables` with the prior error gone (confirmed via verification note; lock + manifest diff confirmed by read).

### EKS registration failure made visible, registry population verified

The registry population already lived in `platform_initializer` step 1.5. The real defect was observability: the EKS-link failure was caught at `logger.debug`, so when it failed the registry silently stayed empty and every Kubernetes data path short-circuited to empty — the direct cause of "0 pods / 0 nodes." The fix raises that branch to `logger.warning` with the real reason, and adds a step 1.6 that reads back `cluster_registry.list_clusters()` and logs either `Cluster Registry populated with N cluster(s)` or a loud empty-registry warning. Paired with BUG 1 making the registry DB-backed rather than lost on restart, the data paths now start with a populated registry. Evidence shows `list_clusters()` == 1 and nodes/pods/logs returning non-empty authenticated results (confirmed via note; initializer diff confirmed by read). This is a diagnosis-and-visibility fix rather than a behavior rewrite, since the registration call itself was already present.

### Read endpoints flipped from fail-open to fail-closed

Both `k8s.py` (`list_namespaces`, `list_nodes`, `list_pods`, `list_deployments`, `list_ingresses`) and `monitoring.py` (`get_cluster_metrics`, `get_metrics_range`, `get_logs`, `get_alerts`) previously caught the failure and returned `success:true` with empty/zero data, so a genuine 401/connection failure looked identical to an empty cluster. They now return `success:false` with an `ErrorDetail` carrying `str(e)` and a specific code (`KUBERNETES_CLIENT_ERROR`, `METRICS_FETCH_ERROR`, `LOG_FETCH_ERROR`, `ALERTS_FETCH_ERROR`), and log at `error` instead of `warning`. The truly-empty-cluster case stays `success:true` because the Kubernetes client raises `KubernetesClientException` only on real SDK failures and returns empty lists on a successful-but-empty response — so the empty-vs-failed distinction is preserved. The original cause survives because `app/clients/kubernetes.py` is unchanged and already re-raises with the SDK message. Response stays `BaseResponse` with the same `data` shape (empty list / zeroed metrics dict / `{"values": []}`), so it's backward compatible.

One asymmetry worth noting (confirmed, non-blocking): `k8s.py` catches the narrow `KubernetesClientException`, while `monitoring.py` catches broad `Exception`. The monitoring endpoints will therefore surface any unexpected error as `success:false` — the correct fail-closed direction, so the broader catch is acceptable here. The injected-failure evidence shows a `(401) Unauthorized` propagating as `success:false | KUBERNETES_CLIENT_ERROR` with the original message intact.

### Bedrock repointed to ap-south-1 / APAC Nova, verification gate removed

`config.py` defaults move to `BEDROCK_REGION=ap-south-1` and `BEDROCK_MODEL_ID=apac.amazon.nova-pro-v1:0`, a new `AWS_REGION=ap-south-1` field is added, and `docker-compose.yml` + `.env.example` are brought in line. In `llm.py`, a new `_resolve_region()` falls back through `BEDROCK_REGION → AWS_REGION → DEFAULT_AWS_REGION → "ap-south-1"`, eliminating the previous hardcoded `us-east-1` fallback in both the verifier and the generate path. The `candidate_models` fallback list is now entirely APAC inference profiles (`apac.amazon.nova-pro-v1:0`, `apac.amazon.nova-lite-v1:0`, `apac.anthropic.claude-3-5-sonnet-20241022-v2:0`). Most importantly for honest error reporting, the `_generate_bedrock_response` hard block on `_bedrock_verified` (which raised the generic "pending AWS account verification") is removed, so the real converse call runs and a failure surfaces the actual AWS error string. Evidence shows `_resolve_region()` == `ap-south-1`, the model/region settings resolve correctly, and a failed call raises with the real `(ValidationException) ... Operation not allowed` text, with `contains_generic_pending == False`. The runtime `Operation not allowed` is an account-level entitlement block the user handles separately and is explicitly out of scope — config correctness and error honesty are both satisfied (confirmed by note; llm/config/compose diffs confirmed by read).

### Account scope, secrets, history

No AWS account other than `605294565283` appears in the added lines — the only other 12-digit sequences in the diff are substrings of SHA256 hashes in `poetry.lock`, not account IDs (confirmed by grep). No `.env` file is committed (confirmed — only `.env.example` changed). The four commits are ordinary additions on `main` with no history rewrite, and the verification note prints no secret values (tokens referenced by length/field name only).

### Not tested / not independently re-run

Per task constraints the Docker build and full verification suite were not re-run; this review relies on the coder's verification note plus the committed diff. The BUG 3 fail-closed path was demonstrated by an injected failure rather than a naturally failing cluster, and the empty-but-healthy `success:true` path is asserted from the client's documented behavior rather than exercised in the note. These are acceptable given the no-re-run constraint and the evidence provided.

</details>

<details>
<summary>File map</summary>

- `pyproject.toml` — add `psycopg[binary] ^3.1.18` (BUG 1)
- `poetry.lock` — resolved psycopg v3 wheels + tzdata bump (BUG 1)
- `platform/backend/app/services/platform_initializer.py` — raise swallowed EKS-link failure to warning; add registry population verification (BUG 2)
- `platform/backend/app/routers/k8s.py` — fail-closed `success:false` + `ErrorDetail` on `KubernetesClientException` (BUG 3)
- `platform/backend/app/routers/monitoring.py` — fail-closed `success:false` + error code on genuine failure (BUG 3)
- `platform/shared/config.py` — Bedrock region/model defaults to ap-south-1 / apac Nova; add `AWS_REGION` (BUG 4)
- `docker-compose.yml` — backend Bedrock env defaults to ap-south-1 / apac Nova (BUG 4)
- `platform/backend/app/clients/llm.py` — `_resolve_region()` AWS_REGION fallback, APAC candidate models, remove hard verification gate (BUG 4)
- `.env.example` — document BEDROCK_REGION, BEDROCK_MODEL_ID, AWS_REGION (BUG 4)
- Frontend files (`ClusterContext.tsx`, `AWSAccounts.tsx`, `Nodes.tsx`, `Overview.tsx`, `Pods.tsx`), `account_registry.py`, `argocd.py`, `k8s_factory.py`, `cluster_registry.py` — part of pre-existing `af3730e` on origin/main, outside the four task commits; not reviewed here.

Full diff: `git diff af3730e..c061e65`

</details>
