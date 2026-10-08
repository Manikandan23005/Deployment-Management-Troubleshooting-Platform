# --- Real-Time Continuous Cluster State Cache & Background Daemon ---
import time
import threading
from typing import Dict, Any, List, Optional
# pyrefly: ignore [missing-import]
from app.core.logging import logger

class ClusterStateCache:
    """Maintains a warm, continuous in-memory snapshot of live Kubernetes cluster state,
    telemetry metrics, GitOps deployments, and platform health. Refreshes asynchronously
    in the background so that AI Copilot queries resolve instantly in < 5ms without blocking
    on remote cloud API calls."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_refresh: float = 0.0
        self._cached_context: Optional[Dict[str, Any]] = None
        self._daemon_started: bool = False
        self._refresh_interval: float = 15.0  # refresh every 15 seconds

    def start_background_daemon(self):
        """Starts the continuous background polling daemon once at platform startup."""
        with self._lock:
            if self._daemon_started:
                return
            self._daemon_started = True

        thread = threading.Thread(target=self._daemon_loop, daemon=True, name="ClusterStateCacheDaemon")
        thread.start()
        logger.info("ClusterStateCache continuous background ingestion daemon started.")

    def _daemon_loop(self):
        # Initial delay to let DB and cluster registry initialize
        time.sleep(2.0)
        while True:
            try:
                self.refresh_now()
            except Exception as e:
                logger.warning(f"Background cluster state refresh notice: {str(e)}")
            time.sleep(self._refresh_interval)

    def refresh_now(self) -> Dict[str, Any]:
        """Polls cluster services and updates the in-memory state snapshot."""
        # pyrefly: ignore [missing-import]
        from app.services.context_builder import context_builder
        # Build query context for a general cluster inquiry
        new_context = context_builder.build_query_context(
            prompt="cluster state overview",
            session_id="system_background_cache"
        )
        with self._lock:
            self._cached_context = new_context
            self._last_refresh = time.time()
        return new_context

    def get_context(self, prompt: str, session_id: Optional[str] = None, scope: Optional[Any] = None) -> Dict[str, Any]:
        """Returns the warm in-memory cluster state snapshot instantly (< 1ms).
        Uses stale-while-revalidate pattern so user requests never block on cloud API calls."""
        with self._lock:
            cached = self._cached_context
            last_ts = self._last_refresh

        now = time.time()
        # If cache exists, return it immediately (< 0.5ms)
        if cached:
            # If stale (> 30s), trigger background async refresh
            if now - last_ts > 30.0:
                threading.Thread(target=self.refresh_now, daemon=True, name="AsyncCacheRefresh").start()

            res = dict(cached)
            # pyrefly: ignore [missing-import]
            from app.services.context_builder import context_builder
            # pyrefly: ignore [missing-import]
            from app.utils.session_manager import session_manager

            target_svc = session_manager.resolve_target_service(session_id, prompt)
            res["query_categories"] = context_builder.classify_query(prompt)
            res["current_prompt"] = prompt
            res["targeted_service"] = target_svc

            all_pods = res.get("infrastructure_summary", {}).get("pods_sample", [])
            target_pod_name = None
            target_ns = "devops-nexus-prod"
            if target_svc:
                for p in all_pods:
                    p_name = p.get("name", "")
                    if target_svc in p_name:
                        target_pod_name = p_name
                        target_ns = p.get("namespace", "devops-nexus-prod")
                        break
            if not target_pod_name and all_pods:
                target_pod_name = all_pods[0].get("name")
                target_ns = all_pods[0].get("namespace", "devops-nexus-prod")

            res["targeted_pod"] = target_pod_name
            res["targeted_namespace"] = target_ns
            return res

        # Only on initial cold start before first background cycle finishes
        try:
            return self.refresh_now()
        except Exception:
            # pyrefly: ignore [missing-import]
            from app.services.context_builder import context_builder
            return context_builder.build_query_context(prompt, session_id=session_id, scope=scope)

cluster_state_cache = ClusterStateCache()
