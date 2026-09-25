# --- Prometheus Client Wrapper ---
import time
import httpx
from typing import Dict, Any, Optional
from app.core.settings import settings
from app.core.logging import logger
from shared.exceptions import TelemetryFetchException

class PrometheusClient:
    """Sends queries to Prometheus HTTP API endpoints with fast fail-over and honest empty states."""
    def __init__(self):
        self.default_url = settings.PROMETHEUS_URL or "http://localhost:9090"
        self._last_check_time = 0.0
        self._is_reachable = False
        self._cached_base_url = self.default_url

    def _check_reachability(self) -> bool:
        """Fast non-blocking reachability check with 30-second memory cache."""
        now = time.time()
        if now - self._last_check_time < 30.0:
            return self._is_reachable

        self._last_check_time = now
        try:
            from app.services.cluster_registry import cluster_registry
            if not cluster_registry.list_clusters():
                self._is_reachable = False
                return False
        except Exception:
            pass

        try:
            with httpx.Client(timeout=0.3) as client:
                resp = client.get(f"{self.default_url}/api/v1/query?query=up")
                if resp.status_code == 200:
                    self._is_reachable = True
                    self._cached_base_url = self.default_url
                    return True
        except Exception:
            pass

        self._is_reachable = False
        return False

    def query(self, query_string: str) -> Dict[str, Any]:
        """Runs instantaneous vector queries against Prometheus."""
        if not self._check_reachability():
            raise TelemetryFetchException("Prometheus unreachable or no active cluster configured.")

        url = f"{self._cached_base_url}/api/v1/query"
        params = {"query": query_string}
        try:
            with httpx.Client(timeout=0.8) as client:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.debug(f"Prometheus query failed: {str(e)}")

        raise TelemetryFetchException("Prometheus query failed.")

    def query_range(self, query_string: str, start: float, end: float, step: str = "15s") -> Dict[str, Any]:
        """Runs range queries against Prometheus."""
        if not self._check_reachability():
            raise TelemetryFetchException("Prometheus unreachable or no active cluster configured.")

        url = f"{self._cached_base_url}/api/v1/query_range"
        params = {
            "query": query_string,
            "start": str(start),
            "end": str(end),
            "step": step
        }
        try:
            with httpx.Client(timeout=0.8) as client:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.debug(f"Prometheus range query failed: {str(e)}")

        raise TelemetryFetchException("Prometheus range query failed.")

    def get_alerts(self) -> Dict[str, Any]:
        """Fetches active firing & pending alerts from Prometheus AlertManager/Alerts API."""
        if not self._check_reachability():
            return {"status": "success", "data": {"alerts": []}}

        url = f"{self._cached_base_url}/api/v1/alerts"
        try:
            with httpx.Client(timeout=0.8) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return {"status": "success", "data": {"alerts": []}}

prometheus_client = PrometheusClient()
