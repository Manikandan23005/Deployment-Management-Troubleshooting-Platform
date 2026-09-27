# --- Loki Client Wrapper with Direct HTTP & K8s Proxy Dual-Mode Support ---
import time
import httpx
import json
import ast
from typing import Dict, Any, Optional, List, Tuple
from app.core.settings import settings
from app.core.logging import logger

class LokiClient:
    """Sends queries to Loki LogQL HTTP API endpoints with non-blocking reachability checks and K8s Proxy fallback."""
    def __init__(self):
        self.base_url = settings.LOKI_URL or "http://localhost:3100"
        self._last_check = 0.0
        self._is_reachable = False
        self._use_k8s_proxy = False
        self._working_candidate: Optional[Tuple[str, str]] = None

    def _query_k8s_proxy(self, endpoint_path: str, query_params: Optional[List[Tuple[str, str]]] = None, cluster_id: Optional[str] = None) -> Any:
        try:
            from app.clients.kubernetes import k8s_client
            clients = k8s_client.get_clients(cluster_id)
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]

            header_params = {"X-Scope-OrgID": "fake"}
            v1.api_client.update_params_for_auth(header_params, None, ["BearerToken"])

            candidates = [
                ("monitoring", "loki-service:3100"),
                ("monitoring", "loki-service:http-metrics"),
                ("logging-lab", "loki:3100"),
                ("monitoring", "loki:3100"),
                ("default", "loki-service:3100")
            ]
            if self._working_candidate:
                ordered_candidates = [self._working_candidate] + [c for c in candidates if c != self._working_candidate]
            else:
                ordered_candidates = candidates

            for ns, svc_port in ordered_candidates:
                try:
                    res = v1.api_client.call_api(
                        "/api/v1/namespaces/{namespace}/services/{name}/proxy/{path}", "GET",
                        path_params={"namespace": ns, "name": svc_port, "path": endpoint_path},
                        query_params=query_params or [],
                        header_params=header_params,
                        response_type="str",
                        auth_settings=["BearerToken"],
                        _return_http_data_only=True
                    )
                    if res:
                        self._working_candidate = (ns, svc_port)
                        try:
                            return json.loads(res) if isinstance(res, str) else res
                        except Exception:
                            try:
                                return ast.literal_eval(res) if isinstance(res, str) else res
                            except Exception:
                                return res
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Loki K8s proxy query note: {str(e)}")
        return None

    def _check_reachability(self, cluster_id: Optional[str] = None) -> bool:
        now = time.time()
        if (now - self._last_check < 20.0) and self._is_reachable:
            return self._is_reachable

        try:
            from app.services.cluster_registry import cluster_registry
            if not cluster_registry.list_clusters():
                self._is_reachable = False
                return False
        except Exception:
            pass

        # 1. Direct HTTP check
        try:
            with httpx.Client(timeout=0.3) as client:
                res = client.get(f"{self.base_url}/ready")
                if res.status_code == 200:
                    self._is_reachable = True
                    self._use_k8s_proxy = False
                    self._last_check = now
                    return True
        except Exception:
            pass

        # 2. K8s Proxy check
        try:
            res = self._query_k8s_proxy("ready", cluster_id=cluster_id)
            if res and ("ready" in str(res).lower() or isinstance(res, dict)):
                self._is_reachable = True
                self._use_k8s_proxy = True
                self._last_check = now
                return True
        except Exception:
            pass

        self._is_reachable = False
        self._last_check = now
        return False

    def query_range(self, query_string: str, limit: int = 100, start: Optional[float] = None, end: Optional[float] = None, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Queries log streams over a range with LogQL parameters."""
        if not self._check_reachability(cluster_id=cluster_id):
            return {"status": "success", "data": {"resultType": "streams", "result": []}}

        params = [("query", query_string), ("limit", str(limit))]
        if start:
            params.append(("start", str(int(start * 1e9))))
        if end:
            params.append(("end", str(int(end * 1e9))))

        if getattr(self, "_use_k8s_proxy", False):
            res = self._query_k8s_proxy("loki/api/v1/query_range", params, cluster_id=cluster_id)
            if isinstance(res, dict) and res.get("status") == "success":
                return res

        url = f"{self.base_url}/loki/api/v1/query_range"
        p_dict = {"query": query_string, "limit": str(limit)}
        if start:
            p_dict["start"] = str(int(start * 1e9))
        if end:
            p_dict["end"] = str(int(end * 1e9))

        headers = {"X-Scope-OrgID": "fake"}
        try:
            with httpx.Client(timeout=0.8, headers=headers) as client:
                response = client.get(url, params=p_dict)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        res = self._query_k8s_proxy("loki/api/v1/query_range", params, cluster_id=cluster_id)
        if isinstance(res, dict) and res.get("status") == "success":
            return res

        return {"status": "success", "data": {"resultType": "streams", "result": []}}

loki_client = LokiClient()
