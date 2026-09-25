# --- Loki Client Wrapper ---
import time
import httpx
from typing import Dict, Any, Optional
from app.core.settings import settings
from app.core.logging import logger
from app.services.port_supervisor import port_supervisor
from app.clients.kubernetes import k8s_client

class LokiClient:
    """Sends queries to Loki LogQL HTTP API endpoints with non-blocking reachability checks."""
    def __init__(self):
        self.base_url = settings.LOKI_URL or "http://localhost:3100"
        self._last_check = 0.0
        self._is_reachable = False

    def _check_reachability(self) -> bool:
        if time.time() - self._last_check < 30.0:
            return self._is_reachable
        try:
            with httpx.Client(timeout=0.3) as client:
                res = client.get(f"{self.base_url}/ready")
                self._is_reachable = (res.status_code == 200)
        except Exception:
            self._is_reachable = False
        self._last_check = time.time()
        return self._is_reachable

    def query_range(self, query_string: str, limit: int = 100, start: Optional[float] = None, end: Optional[float] = None) -> Dict[str, Any]:
        """Queries log streams over a range with LogQL parameters."""
        if not self._check_reachability():
            return {"status": "success", "data": {"resultType": "streams", "result": []}}

        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {
            "query": query_string,
            "limit": str(limit)
        }
        if start:
            params["start"] = str(int(start * 1e9))
        if end:
            params["end"] = str(int(end * 1e9))

        headers = {"X-Scope-OrgID": "fake"}
        try:
            with httpx.Client(timeout=0.8, headers=headers) as client:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return {"status": "success", "data": {"resultType": "streams", "result": []}}

loki_client = LokiClient()
