# Frontend Data-Loading Fix — Verification Note

Scope: DevOps Nexus **frontend only** (plus the frontend's docker-compose/vite wiring).
Backend was NOT changed. Work done directly on `main`. AWS account config untouched
(only `605294565283` referenced). No `.env`/secrets committed; gitleaks pre-commit hook
was NOT bypassed.

## 1. localStorage key audit (brief's PRIMARY suspect — key mismatch — is FALSE)

Confirmed by reading code, not assumed:

| What | Key written | Key read | Match? |
|------|-------------|----------|--------|
| JWT token | `api.login()` → `localStorage.setItem('session_token', token)` | request interceptor → `localStorage.getItem('session_token')` → `Authorization: Bearer` | ✅ same |
| Active cluster id | `ClusterContext.refreshClusters()` / `setActiveCluster()` → `localStorage.setItem('nexus_active_cluster_id', id)` | request interceptor → `localStorage.getItem('nexus_active_cluster_id')` → `X-Cluster-ID` | ✅ same |

**Before == After for the keys** — no key change was needed or made. The real causes were a
first-fetch race, a stale container with no source mount, and a hard 401 full-page reload.

`ClusterContext.refreshClusters()` writes `nexus_active_cluster_id` inside the body and only
flips `setInitialized(true)` in the `finally` block afterwards, so the cluster id is persisted
BEFORE `initialized` becomes true and before any page fetch runs.

## 2. Root causes fixed

1. **Stale container (no hot-reload).** `docker inspect devops-nexus-frontend` showed
   `Mounts: []` and the container had been up ~8h serving a baked `COPY . .` snapshot — host
   edits never reached it. This matches "you are not updated the nexus container... changes not
   reflected."
2. **First-fetch race → confident zeros.** Pages fired their first fetch on mount before
   `ClusterContext` resolved `activeCluster`, and getters swallow not-ready states into `[]`/0,
   so a fresh load rendered `0` until a manual refresh.
3. **Deployments never re-fetched on cluster resolve.** It did not consume `useCluster`; its only
   effect dep was `JSON.stringify(getScopeParams())`, which does not change when the cluster
   finishes loading → stuck at 0 permanently until manual refresh (worst offender).
4. **Overview 2s zero-timer** force-cleared `loading` after 2s regardless of data arrival.
5. **401 hard reload.** The response interceptor did `window.location.href = '/login'` on ANY
   401 — including the transient first-load 401 before the token is usable — causing a full-page
   reload storm that looked like slow/janky navigation and "needs several refreshes."

## 3. Files changed

- `docker-compose.yml` — `platform-frontend`: added bind mount `./platform/frontend:/app`,
  anonymous volume `/app/node_modules`, and `CHOKIDAR_USEPOLLING=true`. (Backend service untouched.)
- `platform/frontend/vite.config.ts` — `server.watch.usePolling=true` (interval 300ms) so edits
  on the host are detected inside the Docker container on macOS.
- `platform/frontend/src/services/api.ts` — 401 interceptor now only clears session + redirects
  when a token was actually present on the request; uses `window.location.replace('/login')`
  (single, no history/reload storm). A 401 with no token (first-load race) is ignored.
- `platform/frontend/src/pages/Overview.tsx` — consume `initialized`; gate first fetch on it;
  init `loading=true`; removed the 2s zero-timer; auto-refresh no-ops until initialized.
- `platform/frontend/src/pages/Deployments.tsx` — import/use `useCluster`; gate first fetch on
  `initialized`; added `initialized` + `activeCluster?.id` to effect deps; `setLoading(true)` on
  each fetch (already init `true`).
- `platform/frontend/src/pages/Pods.tsx` — consume `initialized`; init `loading=true`; gate first
  fetch; added `initialized` to deps.
- `platform/frontend/src/pages/Nodes.tsx` — consume `initialized`; gate first fetch; added
  `initialized` to deps (already init `loading=true`).
- `platform/frontend/src/pages/Logs.tsx` — consume `initialized`; added `initialized` +
  `activeCluster?.id` to the pods-list and logs effects so they re-fire when the cluster resolves.

AI page (`AI.tsx`) intentionally unchanged: it has no mount-time data fetch (chat is user-driven;
effects are only typing animation / localStorage sync / auto-scroll), so it does not block
navigation. Remaining AI latency is Groq LLM response time (expected, out of scope).

No wrong GitOps endpoint paths remain:
`grep -rn "gitops/applications|gitops/deployments" platform/frontend/src` → **no matches**.
Frontend uses `/api/v1/gitops/argocd/applications` and `/api/v1/k8s/deployments`.

## 4. Before / after behavior

- **Before:** fresh load of Overview/Pods/Nodes/Deployments showed 0 / "No data" until one or
  more manual refreshes; navigation felt slow and occasionally bounced to /login (full reload).
- **After:** each page holds a loading/skeleton state until `ClusterContext.initialized`, then
  fetches with the token + `X-Cluster-ID` already set, so real data appears on the FIRST render.
  Deployments re-fetches when the cluster resolves. The 401 interceptor no longer reloads on the
  transient first-load 401, so navigation stays client-side (XHR, not document reloads).

## 5. Build

`cd platform/frontend && npm run build` (tsc + vite):
```
✓ 1578 modules transformed.
dist/assets/index-s7h7jb8r.js   467.23 kB │ gzip: 121.83 kB
✓ built in 4.24s
```
No type errors across all edited pages.

## 6. Hot-reload verification (stale-container fix)

```
docker compose up -d platform-frontend
docker inspect devops-nexus-frontend --format '{{json .Mounts}}'
# → bind mount Source=.../platform/frontend Destination=/app  (RW), plus /app/node_modules volume
```
Edited a probe string in `Overview.tsx` (`Unified Cluster Control HMRPROBE`), saved, container log:
```
[vite] hmr update /src/pages/Overview.tsx, /src/index.css
```
HMR fired through the bind mount — host edits now reach the container with no image rebuild.
Probe string reverted.

## 7. curl evidence — exact frontend request shapes (real login)

Login (admin), token captured from `data.token` (len 196):
```
POST /api/v1/auth/login {"username":"admin","password":"DevOpsNexus@123"} → success, token OK
```
Active cluster resolved exactly as `ClusterContext` would (default cluster):
```
GET /api/v1/clusters → cluster-0aac719f (is_default=True, name=devops-nexus-prod)
```
Exact pods request the frontend makes on a fresh load (default scope `cluster`,
`X-Cluster-ID` from the resolved cluster):
```
GET /api/v1/k8s/pods?scope_mode=cluster
  Authorization: Bearer <token>
  X-Cluster-ID: cluster-0aac719f
→ success=True  pod_count=32
```
Other pages (same auth + X-Cluster-ID):
```
GET /api/v1/k8s/deployments?scope_mode=cluster      → count=21
GET /api/v1/k8s/nodes                               → count=2
GET /api/v1/monitoring/metrics?scope_mode=cluster   → cpu=1.85  mem=18.87
```
Transient first-load race (NO token) — confirms the softened interceptor is correct to ignore it:
```
GET /api/v1/k8s/pods?scope_mode=cluster  (no Authorization header) → HTTP 401
```
The new interceptor sees no `session_token` present and does NOT clear state or redirect, so the
first-load 401 no longer triggers a full-page reload.

## 8. First-load sequence trace (reasoned)

1. `Login.handleLogin` → `api.login()` writes `session_token` to localStorage, then
   `navigate('/overview')`.
2. `ProtectedRoute` reads `session_token` (now present) → mounts `ClusterProvider` → `ScopeProvider`
   → the page.
3. `ClusterProvider` mounts with `initialized=false`, calls `refreshClusters()` (request interceptor
   now attaches the token) → resolves the default cluster, writes `nexus_active_cluster_id`, then
   sets `initialized=true`.
4. Each page effect is gated on `initialized`: it holds `loading=true` until the flag flips, then
   fetches with `Authorization` + `X-Cluster-ID` already set → real data on first render. No
   "0 until refresh," and Deployments re-fetches because `initialized`/`activeCluster?.id` are now
   in its deps.

## 9. Commits
<!-- filled in after commit -->
