# Frontend Data-Loading & Stale-Container Fix Plan

Target: DevOps Nexus frontend only (plus the frontend's docker-compose/Dockerfile wiring). Backend is confirmed healthy and MUST NOT change. Work on `main`, no worktree, no feature branch.

## Root cause (verified in code, not assumed)

The brief's PRIMARY suspect (localStorage key mismatch) is **FALSE**. Verified exact keys:

- `api.login()` writes the JWT under `session_token` (from `response.data.data.token`). (`platform/frontend/src/services/api.ts`)
- The request interceptor READS `localStorage.getItem('session_token')` for `Authorization` and `localStorage.getItem('nexus_active_cluster_id')` for `X-Cluster-ID`. Same keys. (`api.ts`)
- `ClusterContext` writes `nexus_active_cluster_id` immediately when clusters load and in `setActiveCluster`. Same key. (`platform/frontend/src/context/ClusterContext.tsx`)
- `ProtectedRoute` reads `session_token`; login writes the token BEFORE `navigate('/overview')`, so the token exists by the time pages mount.

So keys are consistent and the token is present. The real causes are:

1. **STALE CONTAINER (primary cause of "changes not reflected / needs rebuild").** `docker inspect devops-nexus-frontend` shows `Mounts: []` — there is NO source bind mount. The frontend `Dockerfile` does `COPY . .` and runs `npm run dev` against that baked-in snapshot. `docker-compose.yml` `platform-frontend` service has no `volumes:`. Result: host source edits never reach the container; the dev server serves an 8-hour-old build. This is exactly the user's "you are not updated the nexus container to the latest updates." Nothing in the frontend source can hot-reload until this is fixed.

2. **First-fetch race → confident zeros (primary cause of "0 until several refreshes").** `ClusterProvider` mounts fresh on each full page load with `activeCluster = null`. Pages fire their first fetch immediately on mount, before `activeCluster` resolves. Every `api.*` getter swallows errors/early states into `[]` or zero-metrics, and pages hold only a boolean `loading`, so a not-ready first fetch renders a confident `0` / "No data" instead of a loading or retry state. The fetch is retried only when a dependency changes.

3. **`Deployments.tsx` never re-fetches when the cluster resolves.** It does not import `useCluster`; its effect dep is only `[JSON.stringify(getScopeParams())]`. Scope params do not change when the cluster finishes loading, so it fetches exactly once (often before ready) and stays at 0 permanently until a manual refresh. This is the worst offender and matches "Deployments 0 active."

4. **Overview's 2-second safety timer** (`Overview.tsx`) force-sets `loading=false` after 2s regardless of whether data arrived, rendering zeros early.

5. **401 interceptor hard reload.** `api.ts` response interceptor does `window.location.href = '/login'` on any 401, forcing a full-page reload. During the first-load race a stray 401 (or a slow token-not-yet-usable moment) triggers a full reload, which looks like "slow / needs several refreshes."

6. **Endpoint paths are already correct.** `getApplications` uses `/api/v1/gitops/argocd/applications` and `getDeployments` uses `/api/v1/k8s/deployments`. No bare `/gitops/applications` or `/gitops/deployments` calls exist. Hypothesis #5 needs no change (verification item included to confirm).

## Fix strategy (minimal, targeted)

Gate every page's first fetch on `ClusterContext.initialized` and re-fire when `activeCluster?.id` resolves; stop swallowing not-ready states into zeros; make the stale container hot-reload. No redesign, no backend changes.

---

# Implementation Plan

- [ ] 1. Make the frontend container hot-reload host source (fixes "changes not reflected / needs rebuild").
      Add a bind mount of the frontend source and an anonymous volume for `node_modules` to the `platform-frontend` service, and enable Vite polling so file events propagate on macOS/Docker. In `docker-compose.yml` under `platform-frontend`, add:
      `volumes: ["./platform/frontend:/app", "/app/node_modules"]` and under `environment` add `- CHOKIDAR_USEPOLLING=true` and `- VITE_API_URL=http://localhost:8000` (keep existing). Do NOT change the backend service.
      Files: docker-compose.yml
      Verify: `docker compose up -d platform-frontend` then `docker inspect devops-nexus-frontend --format '{{json .Mounts}}'` shows the `./platform/frontend` bind mount. Edit a visible string in `platform/frontend/src/pages/Overview.tsx` (e.g. the "Unified Cluster Control" heading), save, and confirm the browser at http://localhost:3000/overview hot-reloads the change within a few seconds WITHOUT an image rebuild. Revert the probe string.

- [ ] 2. Soften the 401 response interceptor so it does not force a full-page reload (reduces "slow / several refreshes").
      In `api.ts` response interceptor, keep clearing `session_token`/`user_role`/`username` on 401, but replace the hard `window.location.href = '/login'` with a guarded client-side redirect that only runs when NOT already on `/login` AND a token was actually present before this response (avoid redirect loops and avoid reloading during the first-load race when no token-expiry actually occurred). Use `window.location.replace('/login')` only in that guarded case so no history entry/full reload storm occurs.
      Files: platform/frontend/src/services/api.ts
      Verify: with the app running, log in and navigate Overview→Pods→Deployments→Nodes repeatedly; confirm no unexpected bounce to /login and no full-page reload loop (Network tab shows XHR calls, not document reloads). With an expired/removed token, confirm a single clean redirect to /login.

- [ ] 3. Expose a readiness gate from ClusterContext and persist the active cluster id synchronously.
      `ClusterContext` already exposes `initialized` and `activeCluster`, and already writes `nexus_active_cluster_id` when clusters load — confirm this is set BEFORE `initialized` flips true (it is, inside the same `refreshClusters`). No structural change needed here beyond confirming `initialized` is consumed by pages (items 4-8). If any adjustment is needed, ensure `localStorage.setItem('nexus_active_cluster_id', ...)` runs before `setInitialized(true)`.
      Files: platform/frontend/src/context/ClusterContext.tsx
      Verify: `cd platform/frontend && npm run build` (tsc + vite build) succeeds with no type errors.

- [ ] 4. Gate Overview's fetch on readiness and remove the premature 2s zero-timer.
      In `Overview.tsx`: consume `initialized` from `useCluster()`. In the mount effect, return early (keep `loading=true`) until `initialized` is true; include `initialized` in the effect deps so it fires once ready. Remove the `setTimeout(... setLoading(false), 2000)` safety timer (or extend it to only clear loading, never to mask missing data). Keep the 10s auto-refresh interval but have it no-op until `initialized`.
      Files: platform/frontend/src/pages/Overview.tsx
      Verify: hard-refresh http://localhost:3000/overview; the dashboard shows a loading state then real numbers (Deployments count > 0, non-zero CPU/Memory from `/api/v1/monitoring/metrics`) on the FIRST load without manual refresh.

- [ ] 5. Fix Deployments to re-fetch when the cluster resolves (worst zero offender).
      In `Deployments.tsx`: import and use `useCluster()`; add `activeCluster?.id` and `initialized` to the fetch effect deps; gate the first fetch until `initialized` is true. Keep the existing `getScopeParams()` dep. Initialize `loading` to `true`.
      Files: platform/frontend/src/pages/Deployments.tsx
      Verify: hard-refresh http://localhost:3000/deployments; the KPI counts and table populate on first load (backend returns 21 deployments) without manual refresh; switching away and back keeps data.

- [ ] 6. Gate Pods fetch on readiness.
      In `Pods.tsx`: consume `initialized` from `useCluster()`; in `loadPods`/the mount effect, wait until `initialized` is true before the first fetch; add `initialized` to effect deps (keep `activeCluster?.id` and the scope dep). Initialize `loading` to `true` so the skeleton shows instead of an instant "No Active Pods".
      Files: platform/frontend/src/pages/Pods.tsx
      Verify: hard-refresh http://localhost:3000/pods; the KPI cards and table show 32 pods on first load (skeleton while loading, never a premature "No Active Pods").

- [ ] 7. Gate Nodes fetch on readiness.
      In `Nodes.tsx`: consume `initialized` from `useCluster()`; wait until `initialized` before first fetch; add `initialized` to the effect deps (keep `activeCluster?.id`).
      Files: platform/frontend/src/pages/Nodes.tsx
      Verify: hard-refresh http://localhost:3000/nodes; 2 nodes render on first load without manual refresh.

- [ ] 8. Gate Logs' pods-list fetch on readiness and re-fire when connection resolves.
      In `Logs.tsx`: the mount effect already guards on `isConnected` but returns without retrying; add `initialized` and `activeCluster?.id` to that effect's deps so it re-runs once the cluster resolves (currently it can run once while `isConnected` is false and never retry). Keep the scope dep.
      Files: platform/frontend/src/pages/Logs.tsx
      Verify: hard-refresh http://localhost:3000/logs; the pod dropdown populates on first load without manual refresh.

- [ ] 9. Confirm no wrong GitOps endpoint paths remain (hypothesis #5 — verification only).
      No code change expected. Confirm the frontend uses `/api/v1/gitops/argocd/applications` and `/api/v1/k8s/deployments` only.
      Files: (none — verification)
      Verify: `grep -rn "gitops/applications\|gitops/deployments" platform/frontend/src` returns no matches; `grep -rn "gitops/argocd/applications" platform/frontend/src/services/api.ts` confirms the correct path. (This grep is a scope check, not the feature verification — the build in item 10 is the real gate.)

- [ ] 10. Full frontend build + smoke verification of the whole fix.
      Run the production build to catch type/compile regressions across all edited pages, then do the live smoke test through the hot-reloading container.
      Files: (none — verification)
      Verify: `cd platform/frontend && npm run build` succeeds. Then with the container running (item 1), log in as admin and load Overview, Pods, Nodes, Deployments, Logs each via a hard refresh: every page shows real data on the FIRST load (no zeros-then-refresh), and navigating between pages does not require refreshes or bounce to /login. Write `/Users/manikandansrinivasan/pro/Deployment-Management-Troubleshooting-Platform/.agents/tasks/frontend-dataload-review.json` only via the review step.

## Notes / assumptions

- AI page slowness: `AI.tsx` does not fire a data fetch on mount (chat is user-driven) and does not block navigation, so no change is needed there; the remaining AI latency is Groq LLM response time, which is expected and out of scope for this data-loading fix.
- `ScopeContext` keys (`ops_scope_mode`, `ops_selected_ns`, `ops_selected_app`, `ops_selected_domain`) are self-consistent (same key written and read) and default sensibly; no change needed.
- All page changes follow the same pattern (consume `initialized`, gate first fetch, add it to deps). If a page already imports `useCluster`, only the deps/gate change; otherwise add the import.
