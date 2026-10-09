# Dashboard "0 pods / 0 nodes until refresh" + "AWS/EKS not detected" — Root Cause Investigation

**Mode:** READ-ONLY diagnosis. No files were modified.
**Repo:** `/Users/manikandansrinivasan/pro/Deployment-Management-Troubleshooting-Platform`
**Scope:** Backend AWS/EKS + K8s data path (FastAPI) and frontend data fetching/loading-state handling (React/Vite).

---

## 1. Summary answer (TL;DR)

The intermittent zeros and "AWS account / cluster not detected" are **not random** — they are the direct result of three compounding design choices on the data path:

1. **The backend swallows every Kubernetes/AWS error and returns `success: true` with an empty list / all-zero metrics.** When the EKS client, STS credentials, or kube client aren't ready yet (cold start), the request does not fail — it returns `0`. The frontend has no way to tell "the cluster has 0 pods" apart from "the backend couldn't reach the cluster this time."

2. **The EKS Kubernetes client is built lazily on the first request and cached for ~10 minutes, with a silent fallback to the local cluster registry (which usually resolves to nothing/empty) when token generation fails.** The first request(s) after boot or after cache expiry hit the slow/cold path and frequently fall back to empty; a later refresh hits a warm cache or a now-ready credential and succeeds. This is the mechanism behind "wrong on first load, correct after a few refreshes."

3. **The frontend renders `0` immediately and treats empty responses as truth.** `Overview.tsx` seeds all counts to `0`, has a 2-second "safety timer" that force-clears the loading state regardless of whether data arrived, and `.catch(() => [])` / `.catch(() => zeros)` on every call. Pages like `Nodes.tsx` collapse "loading error" and "genuinely zero" into a single empty state. There is no distinction between **loading**, **error**, and **zero actual resources**.

Ranked by likelihood/impact:

| Rank | Root cause | Primary file(s) | Symptom explained |
|------|-----------|-----------------|-------------------|
| **1 (highest)** | Routers catch `KubernetesClientException` and return `success=True, data=[]` | `routers/k8s.py`, `routers/monitoring.py` | 0 pods/0 nodes/0 metrics with no error shown |
| **2** | Lazy per-request EKS client build + 10-min cache + silent fallback-to-empty | `clients/k8s_factory.py`, `clients/kubernetes.py` | "wrong first load, right after refresh"; cold-start race |
| **3** | Frontend seeds 0, 2s safety timer, `.catch(()=>[])`, no error state | `pages/Overview.tsx`, `pages/Nodes.tsx`, `services/api.ts` | 0 shown instead of spinner/error; AWS/cluster "not detected" banner |
| **4** | AWS account + EKS cluster "discovery" runs once at startup and can silently fail | `services/platform_initializer.py`, `aws/account_registry.py` | AWS account / cluster intermittently not detected |
| **5** | STS AssumeRole falls back to ambient creds and caches the result for 1h | `aws/credential_provider.py` | wrong-identity / empty EKS results that persist until cache clears |
| **6 (situational)** | CORS defaults to localhost-only origins | `shared/config.py`, `main.py` | "dashboard doesn't load at all" when served from any non-localhost host |

---

## 2. Evidence by question

### Q1 — Root cause of "0 pods / 0 nodes until refresh"

It is a combination of **(b) backend returning empty lists when a client/credentials aren't ready**, **(a) frontend rendering 0 during loading/error**, and **(d) a race between warm-cache/credential readiness and the first fetch**. All three are present.

**(b) Backend returns empty on any failure — the single biggest factor.**

`platform/backend/app/routers/k8s.py`:
- `list_nodes` (lines ~90–98): wraps `node_service.list_nodes(...)` and on `KubernetesClientException` does `return BaseResponse(success=True, data=[], ...)`.
- `list_pods` (lines ~100–120): same pattern — `success=True, data=[]` on failure.
- `list_namespaces` (lines ~29–45) and `list_deployments` (lines ~150–172): same.

`platform/backend/app/routers/monitoring.py`:
- `get_cluster_metrics` (lines ~22–45): `except Exception as e:` → returns `success=True` with `cpu/memory/disk/network = 0.0`.
- `get_metrics_range` (lines ~48–68): `except Exception` → `success=True, data={"values": []}`.

The low-level wrapper raises on failure (so the signal exists), but the router discards it:
`platform/backend/app/clients/kubernetes.py`
- `list_nodes` (lines ~29–34): `except Exception as e: raise KubernetesClientException(...)`.
- `list_pods` (lines ~36–43): same. These exceptions are the ones the router converts to empty `200 OK`.

**Net effect:** a cold/failed cluster call produces `HTTP 200 {"success": true, "data": []}`, indistinguishable from a real empty cluster.

**(d) Warm-cache / readiness race.** See Q2/`k8s_factory.py` below — the first request builds the client lazily and may fall back to empty; subsequent requests hit a populated cache. Service-level caches reinforce the "sticky after refresh" feel:
- `services/node_service.py` `list_nodes` (lines ~12–23): 15s TTL cache keyed by cluster.
- `services/pod_service.py` `list_pods` (lines ~19–27): 15s TTL cache.
- `services/cluster_state_cache.py`: background daemon starts with `time.sleep(2.0)` initial delay (`_daemon_loop`, lines ~38–46) and only refreshes every 15s, so the first ~2s after boot the warm snapshot is empty.

**(a) Frontend renders 0 during loading/error.** `platform/frontend/src/pages/Overview.tsx`:
- State seeded to zeros (lines ~15–18): `metrics` initialized to all-0.
- Every fetch is `.catch(() => [])` / `.catch(() => zeros)` (lines ~30–40) — errors become empty data silently.
- `useEffect` sets a **2-second safety timer** that calls `setLoading(false)` unconditionally (lines ~60–66), so even if the request is still in flight or failed, the UI drops the spinner and shows `0`.
- Cards render `${apps.length} active`, `${metrics.cpu_utilization.toFixed(1)}%`, etc. directly (lines ~120–126) with no "no data" vs "0" distinction.

### Q2 — Root cause of "AWS account / cluster not detected"

**Discovery runs once at startup and is best-effort/swallowed; the request-time EKS client build silently falls back to empty.**

Startup discovery — `platform/backend/app/services/platform_initializer.py` `initialize_platform` (lines ~13–90):
- Step 1 auto-detects local clusters; step 1.5 registers the default AWS account and tries `register_eks_cluster_as_target(...)`. The EKS link is wrapped in `except Exception as cluster_err: logger.debug(...)` (lines ~55–57) and the whole AWS block in `except Exception as aws_err: logger.warning(...)` (lines ~58–59). If AWS is slow/unavailable at boot, the account/cluster simply isn't registered and nothing surfaces to the UI.
- `main.py` `startup_event` (lines ~34–40) wraps the entire initializer in `try/except` and only logs a warning, so a failed bootstrap still starts the server in a degraded state.

Request-time EKS client resolution — `platform/backend/app/clients/k8s_factory.py` `get_clients` (lines ~70–200):
- Lazy build: EKS client is constructed on first use and cached ~10 min (`self._eks_client_cache`, lines ~140–150 and ~185–193).
- If the passed `cluster_id` isn't found, it **silently falls back** to the default cluster "rather than failing with 0 nodes / 0 pods" (lines ~110–120) — but if there's no AWS account registered yet it falls back to `cluster_registry.get_k8s_clients(cid)` (lines ~160–165), which for an EKS id typically yields an unusable/empty client.
- The entire EKS token+client build is wrapped in `try/except Exception` (lines ~195–205): on **any** failure it logs an error and caches a **fallback (often empty) client for 10 minutes**. So one cold-start failure poisons the cache for 10 minutes until it expires — which is exactly why "a few refreshes" eventually work (cache expiry + credentials now ready).

Account lookup — `platform/backend/app/aws/account_registry.py`:
- Accounts live in an **in-memory dict** (`_accounts`, `__init__` lines ~22–26) with no persistence; `_seed_default_accounts` (lines ~28–50) seeds a hard-coded default but swallows errors (`except Exception: logger.debug`). On restart the registry is empty until re-seeded, and if seeding throws, discovery has nothing to work with.

Frontend "not detected" banner — `platform/frontend/src/pages/Overview.tsx`:
- `isConnected = !!activeCluster && clusters.length > 0` (line ~24) and the header shows "Connecting Cluster..." when `activeCluster` is null (lines ~110–118).
- `platform/frontend/src/context/ClusterContext.tsx` `refreshClusters` (lines ~37–72): on any error or empty response it sets `clusters = []` and `activeCluster = null` (`catch` lines ~63–66), which renders the "not detected" state. Combined with the backend returning empty on cold start, the cluster appears "not detected" until a later refresh succeeds.

### Q3 — Root cause of "dashboard not loading at all"

Most likely contributors:

1. **CORS defaults are localhost-only.** `platform/shared/config.py` line 8: `CORS_ORIGINS` defaults to `http://localhost:3000,:5173,:8000,127.0.0.1:3000,:5173`. `main.py` (lines ~93–101) builds `allow_origins` from this. If the dashboard is served from any other hostname/IP/port (e.g. a LAN IP, a NodePort like `:30080`, or a deployed domain), **every API call is blocked by CORS** and the dashboard shows no data / fails to load. The frontend default API base is `http://localhost:8000` (`services/api.ts` line 5, `VITE_API_URL` fallback) — a mismatch between where the browser runs and `localhost` will break it.
2. **Blocking synchronous AWS/K8s calls on the request path.** `k8s_factory.generate_eks_token` and `credential_provider.get_temporary_credentials` perform synchronous boto3/STS network calls inside `async` route handlers (via sync service calls). With **no explicit timeout** on STS/EKS calls, a slow AWS endpoint can hang the first request for a long time, making the dashboard appear to "not load." (`aws/credential_provider.py` `get_temporary_credentials` lines ~30–120 — `boto3.client("sts")` with default timeouts; `aws/eks_service.py` `list_clusters` lines ~11–30 — no client-side timeout config.)
3. **401 hard redirect loop.** `services/api.ts` response interceptor (lines ~30–42): on any 401 it clears tokens and does `window.location.href = '/login'`. If the token expires or the first call races auth, the user is bounced to login — perceived as "dashboard won't load."

No evidence of a startup dependency that crashes the process (startup is wrapped in try/except), so "not loading at all" is most plausibly **CORS/origin mismatch** or a **hung first request** rather than a backend crash.

### Q4 — Sites that silently swallow exceptions and return 0/empty on the dashboard data path

Backend:
- `routers/k8s.py`: `list_namespaces`, `list_nodes`, `list_pods`, `list_deployments`, `list_ingresses` — each `except KubernetesClientException: return BaseResponse(success=True, data=[])`.
- `routers/monitoring.py`: `get_cluster_metrics` → `except Exception` returns all-zero metrics; `get_metrics_range` → `except Exception` returns `{"values": []}`.
- `clients/k8s_factory.py` `get_clients`: `except Exception` → caches an (often empty) fallback client for 10 min.
- `aws/credential_provider.py` `get_temporary_credentials`: on `ClientError`, silently falls back to ambient `boto3.Session` creds and caches them for 1h (lines ~95–110).
- `services/platform_initializer.py`: EKS target link and whole AWS block swallowed to `debug`/`warning`.
- `aws/account_registry.py` `_seed_default_accounts`, audit writes: `except Exception` → `debug`/`pass`.
- `services/cluster_state_cache.py` `_daemon_loop` and `get_context`: `except Exception` → warn / rebuild.

Frontend (`services/api.ts`): nearly every getter uses `catch (e) { console.warn(...) } return []` (or returns a hard-coded zero/default object). Notably `getClusterMetrics` returns all-zero metrics on failure; `getNodes`, `getPods`, `getApplications`, `getNamespaces`, `getAlerts` return `[]`.
Frontend (`Overview.tsx`): per-promise `.catch(() => [])` / `.catch(() => zeros)` plus a `try/catch` that only `console.error`s.

### Q5 — Does the frontend distinguish loading / error / zero-resources?

**No.** It conflates all three:
- `Overview.tsx`: single `loading` boolean, no `error` state; the 2s safety timer force-ends loading; empty/zero data renders identically to real data. There is no "failed to load" UI.
- `Nodes.tsx` (lines ~66–96): ternary is `loading ? <Loading/> : nodes.length === 0 ? <EmptyState "No active Kubernetes cluster connection detected"> : <Table/>`. A transient backend error (returned as `[]`) renders the **same** "no cluster detected" empty state as a genuinely node-less cluster — directly producing the "AWS/cluster not detected" complaint.
- `ClusterContext.tsx`: errors collapse to `clusters=[]`, `activeCluster=null` with only a `console.warn`; no retry, no error surface.

---

## 3. Conclusions & recommended fixes

Fixes are ordered to match the ranked table. Each is a recommendation only; nothing was implemented.

**Fix 1 — Stop masking failures as empty success (backend).**
In `routers/k8s.py` and `routers/monitoring.py`, distinguish "cluster unreachable / client not ready" from "zero resources." Return a non-200 (e.g. 503) or `success=true` **with an explicit status flag** like `{"data": [], "cluster_ready": false, "reason": "..."}`. Do **not** return bare empty lists on `KubernetesClientException`. This is the smallest change with the largest impact and unblocks the frontend from telling the two cases apart.

**Fix 2 — Make the EKS client path fail loudly and retry, not cache-empty (backend).**
In `clients/k8s_factory.py` `get_clients`: do **not** cache the fallback empty client for 10 minutes on exception (lines ~195–205). Either (a) propagate the error so the router can report "not ready," or (b) retry token generation with backoff and only cache a **working** client. Add explicit timeouts to boto3 STS/EKS clients (botocore `Config(connect_timeout, read_timeout, retries)`) so a cold call can't hang the request. Warm the EKS client during `startup_event` so the first user request isn't the cold path.

**Fix 3 — Add real loading/error/empty states (frontend).**
In `Overview.tsx`: remove the 2s `setLoading(false)` safety timer (or only use it to flip to an *error* state, not a *success/zero* state); add an `error` state; stop `.catch(() => [])` masking — on failure, set `error` and show a retry UI instead of `0`. In `Nodes.tsx` (and `Pods`, `Clusters`, `AWSAccounts`), separate `error` from `empty`: show "Couldn't reach the cluster — retrying" on error vs "No nodes" only when the backend confirms the cluster is reachable and genuinely empty (requires Fix 1's `cluster_ready` flag). Consider the long-absent shared data-fetching hook (`frontend/src/hooks/` is README-only) to centralize loading/error/retry.

**Fix 4 — Make AWS/EKS discovery resilient and observable.**
In `platform_initializer.py` / `account_registry.py`: persist registered AWS accounts (DB, like clusters) so a restart doesn't lose them; add a health/status endpoint that reports whether the default account seeded and whether the EKS target linked, and surface it in the UI. Add a lightweight background re-discovery (similar to `cluster_state_cache`) so a boot-time AWS failure self-heals without manual refresh. Replace `logger.debug` on the EKS link failure with a visible warning + status flag.

**Fix 5 — Review the STS ambient-credential fallback.**
In `credential_provider.py` `get_temporary_credentials` (lines ~95–110): falling back to ambient `boto3.Session` creds and caching for 1h can mask a broken AssumeRole and return data for the wrong identity (or empty). Recommend: only fall back when explicitly configured, shorten the fallback cache TTL, and record `credential_source` so the UI can warn when running on fallback creds.

**Fix 6 — Fix CORS/origin configuration for non-localhost deployments.**
Set `CORS_ORIGINS` (via env) to the actual origin the dashboard is served from, and set `VITE_API_URL` to the reachable backend URL. The localhost-only default in `shared/config.py` line 8 will block the app whenever it's not served from localhost — a strong candidate for "dashboard doesn't load at all." Verify the browser's Network tab for CORS/preflight failures.

---

## 4. Verification notes (for whoever implements)

- Backend lives at `platform/backend` (FastAPI); frontend at `platform/frontend` (Vite/React/TS). Root `pyproject.toml` + `poetry.lock` present.
- To confirm Fix 1 behavior, exercise `GET /api/v1/k8s/nodes` and `/pods` with the cluster intentionally unreachable and observe the current `success:true, data:[]` response (that is the bug), then assert the new behavior.
- `frontend/src/hooks/` currently contains only a README — there is **no** shared data-fetching/polling hook, so loading/error logic is duplicated and inconsistent across pages.
