# Gate Nexus dashboard fetches on cluster readiness and soften first-load 401

The DevOps Nexus dashboard was rendering confident zeros (0 pods, 0 nodes, empty deployments) on a fresh load and only showing real data after one or more manual refreshes, with janky navigation that occasionally bounced to `/login`. The fix (commit `1defa8a`) is frontend-only: it gates each page's first data fetch on a new `ClusterContext.initialized` flag so fetches fire only once both the auth token and the active cluster are available, softens the 401 response interceptor so a transient token-less first-load 401 no longer triggers a full-page reload, removes a 2-second zero-timer in Overview, and adds a dev-only docker-compose bind mount plus vite polling so host edits actually reach the running container. The brief's primary suspect — a localStorage key mismatch — does not exist in the code: writer and reader agree on both `session_token` and `nexus_active_cluster_id`.

Watch for: nothing blocking. One minor behavioral note (likely) — Logs' `fetchLogsData` still early-returns while `!isConnected`, so it leans entirely on the newly-added `isConnected`/`initialized` deps to re-fire; this is correct but worth understanding. **Verdict**: APPROVED

## High-level view

The core design is a single readiness gate. `ClusterContext` already resolved the active cluster asynchronously and persisted its id to `localStorage` before flipping an `initialized` flag in its `finally` block. Every data page now consumes that flag and holds a loading state until it flips, then fetches with `Authorization` and `X-Cluster-ID` already attached by the request interceptor. This converts a fresh load into the same ordered sequence a post-refresh load already had.

The key-mismatch hypothesis from the brief is false and correctly left alone. The request interceptor reads `session_token` and `nexus_active_cluster_id`; `ClusterContext` and `api.login()` write those exact keys. No key change was made because none was needed — the right call.

The 401 interceptor change is the fix for the navigation jank. Previously any 401, including the token-less first-load race, cleared session state and did a `window.location.href` full-document reload. It now only clears and redirects when a token was actually present on the request, and uses `replace` instead of `href`. This is a fail-safe direction: a genuinely rejected token still logs out, but a transient race no longer reload-storms.

Deployments was the worst offender and is the most substantive gating fix: it previously keyed its effect only on `getScopeParams()`, which does not change when the cluster resolves, so it fetched once (often before ready) and stuck at 0 forever. It now consumes `useCluster` and adds `initialized` + `activeCluster?.id` to its deps.

The docker-compose bind mount and vite polling are dev-environment wiring, not application logic. They explain the "changes not reflected" symptom (a baked image with no source mount) and are scoped to the frontend service only.

<details>
<summary>Issues (2)</summary>

1. **Duplicate `setLoading(true)` sources in Deployments** (possible, non-blocking) — `fetchDeployments` now calls `setLoading(true)` on every invocation including the 10s-style re-fetches; confirm this does not flash a skeleton over already-rendered data on scope changes. Cosmetic only.
2. **Logs relies on `isConnected` gating rather than `initialized` directly** (likely, non-blocking) — `fetchLogsData` early-returns while `!isConnected`; the added deps make it re-fire correctly when the cluster resolves, but the two gates (`isConnected` vs `initialized`) coexist. Works as written; worth a glance if Logs ever shows stale empty state.

</details>

<details>
<summary>Details</summary>

### Readiness gate via ClusterContext.initialized

`ClusterContext.refreshClusters()` resolves the cluster list, selects the saved or default cluster, writes `nexus_active_cluster_id` to `localStorage`, and only then flips `setInitialized(true)` in its `finally` block. Because the id is persisted before the flag flips, any page effect gated on `initialized` is guaranteed to run after both the token (written by `api.login()` before navigation) and the cluster id are in place, so the request interceptor attaches `Authorization` and `X-Cluster-ID` on the very first fetch.

Overview, Pods, and Nodes each take the same shape: consume `initialized` from `useCluster`, initialize `loading=true`, early-return from the fetch effect while `!initialized`, and add `initialized` to the effect deps. The uniformity is the point — a fresh load now holds a skeleton instead of resolving getters that swallow not-ready state into `[]`/0.

```
Login writes session_token ──► navigate(/overview)
          │
ProtectedRoute (reads session_token) ──► ClusterProvider mounts
          │
refreshClusters(): resolve cluster ──► write nexus_active_cluster_id ──► setInitialized(true)
          │
page effect (gated on initialized) ──► fetch with Authorization + X-Cluster-ID set ──► real data, first render
```

### Deployments: the stuck-at-zero case

Deployments previously keyed its fetch effect on `JSON.stringify(getScopeParams())` alone. That value does not change when the cluster finishes loading, so the single pre-ready fetch returned nothing and the page stayed at 0 until a manual refresh forced a re-render. It now imports `useCluster`, early-returns while `!initialized`, and lists `initialized` and `activeCluster?.id` in its deps, so it re-fires exactly when the cluster resolves. This is the change that most directly addresses the reported symptom.

### Softened 401 interceptor

The old interceptor cleared `session_token`/`user_role`/`username` and did `window.location.href = '/login'` on any 401 — including the token-less first-load race before the app is initialized — which produced full-document reloads that read as slow, janky navigation needing several refreshes. The new interceptor computes `hadToken` from `localStorage.getItem('session_token')` and only clears state and redirects when a token was actually present, using `window.location.replace('/login')` to avoid stacking history and re-triggering reloads. A token-less 401 is now ignored. This is the correct fail-safe direction: real token rejection still logs the user out; a transient race does not.

### Overview 2-second zero-timer removed

Overview previously set a 2s `setTimeout` that force-cleared `loading` regardless of whether data had arrived, which could blank the spinner and expose zeros before the fetch resolved. That timer is gone, `loading` now initializes to `true`, and both the initial fetch effect and the 10s auto-refresh interval early-return while `!initialized` so neither races the cluster resolution.

### Key-mismatch hypothesis is false (verified)

The brief named a suspected mismatch — token read as `session_token`, cluster as `nexus_active_cluster_id`. Reading the code: the request interceptor reads `session_token` for the Bearer header and `nexus_active_cluster_id` for `X-Cluster-ID`; `api.login()` writes `session_token` and `ClusterContext` writes `nexus_active_cluster_id`. Writer and reader agree everywhere. No key change was made, which is correct — there was nothing to reconcile. (The apparent duplicate `setItem` lines in a grep of ClusterContext are a grep display artifact, not duplicated source.)

### Scope stayed frontend-only, no secrets

Commit `1defa8a` touches five page components, `api.ts`, `vite.config.ts`, and the `platform-frontend` service in `docker-compose.yml` (bind mount, anonymous `node_modules` volume, `CHOKIDAR_USEPOLLING`). No backend file and no AWS config is in this commit; the backend/Bedrock/Groq changes live in separate earlier commits. A name-only scan of the commit shows no `.env`, secret, credential, `.pem`, or token files, and the verification note records the gitleaks pre-commit hook ran clean and was not bypassed.

### Verification evidence

The coder's note records real curl evidence against the running backend (login token len 196, `GET /clusters` resolving `cluster-0aac719f`, pods=32, deployments=21, nodes=2, metrics cpu/mem non-zero, and a token-less 401 confirming the softened interceptor path), a clean `npm run build` (1578 modules, no type errors), and an HMR probe confirming the bind mount delivers host edits into the container. This evidence lines up with the diff; no re-run was necessary.

</details>

<details>
<summary>File map</summary>

- `platform/frontend/src/context/ClusterContext.tsx` — (unchanged in this commit) source of the `initialized` flag; writes `nexus_active_cluster_id` before flipping it.
- `platform/frontend/src/services/api.ts` — 401 interceptor only clears/redirects when a token was present; `replace` not `href`.
- `platform/frontend/src/pages/Overview.tsx` — gate on `initialized`, init `loading=true`, remove 2s zero-timer, no-op auto-refresh until ready.
- `platform/frontend/src/pages/Deployments.tsx` — consume `useCluster`, gate + re-fire on `initialized`/`activeCluster?.id`.
- `platform/frontend/src/pages/Pods.tsx` — consume `initialized`, init `loading=true`, gate first fetch.
- `platform/frontend/src/pages/Nodes.tsx` — consume `initialized`, gate first fetch.
- `platform/frontend/src/pages/Logs.tsx` — add `initialized`/`activeCluster?.id` to pod-list and logs effect deps.
- `platform/frontend/vite.config.ts` — `server.watch.usePolling` for macOS container file events.
- `docker-compose.yml` — `platform-frontend` bind mount + node_modules volume + polling env (dev wiring).

Full diff: `git show 1defa8a`.

</details>
