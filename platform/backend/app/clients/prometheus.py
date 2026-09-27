# --- Prometheus Client Wrapper with Direct HTTP & K8s Proxy Dual-Mode Support ---
import time
import httpx
import json
import ast
from typing import Dict, Any, Optional, List, Tuple
from app.core.settings import settings
from app.core.logging import logger
from shared.exceptions import TelemetryFetchException

class PrometheusClient:
    """Sends queries to Prometheus HTTP API endpoints with fast fail-over, K8s Service Proxy support, and honest empty states."""
    def __init__(self):
        self.default_url = settings.PROMETHEUS_URL or "http://localhost:9090"
        self._last_check_time = 0.0
        self._is_reachable = False
        self._cached_base_url = self.default_url
        self._use_k8s_proxy = False
        self._working_candidate: Optional[Tuple[str, str]] = None

    def _query_k8s_proxy(self, endpoint_path: str, query_params: Optional[List[Tuple[str, str]]] = None, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Queries Prometheus via Kubernetes CoreV1 API service proxy as native fallback for remote/EKS clusters."""
        try:
            from app.clients.kubernetes import k8s_client
            clients = k8s_client.get_clients(cluster_id)
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]

            header_params = {}
            v1.api_client.update_params_for_auth(header_params, None, ["BearerToken"])

            # Candidate services in monitoring namespace
            candidates = [
                ("monitoring", "prometheus-service:web"),
                ("monitoring", "prometheus-service:9090"),
                ("monitoring", "kube-prometheus-stack-prometheus:http-web"),
                ("monitoring", "kube-prometheus-stack-prometheus:9090"),
                ("monitoring", "prometheus-k8s:web"),
                ("default", "prometheus-service:9090")
            ]
            if self._working_candidate:
                ordered_candidates = [self._working_candidate] + [c for c in candidates if c != self._working_candidate]
            else:
                ordered_candidates = candidates

            last_err = None
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
                            return ast.literal_eval(res) if isinstance(res, str) else res
                except Exception as ex:
                    last_err = ex
                    continue

            if last_err:
                raise last_err
        except Exception as e:
            logger.debug(f"Prometheus K8s proxy query failed: {str(e)}")
            raise TelemetryFetchException(f"Prometheus query failed: {str(e)}")

        raise TelemetryFetchException("Prometheus service proxy endpoint unreachable.")

    def _check_reachability(self, cluster_id: Optional[str] = None) -> bool:
        """Fast non-blocking reachability check supporting both direct HTTP and Kubernetes service proxy."""
        now = time.time()
        if (now - self._last_check_time < 20.0) and self._is_reachable:
            return self._is_reachable

        try:
            from app.services.cluster_registry import cluster_registry
            if not cluster_registry.list_clusters():
                self._is_reachable = False
                return False
        except Exception:
            pass

        # 1. Check direct HTTP
        try:
            with httpx.Client(timeout=0.3) as client:
                resp = client.get(f"{self.default_url}/api/v1/query?query=up")
                if resp.status_code == 200:
                    self._is_reachable = True
                    self._use_k8s_proxy = False
                    self._last_check_time = now
                    return True
        except Exception:
            pass

        # 2. Check K8s API Proxy
        try:
            res = self._query_k8s_proxy("api/v1/query", [("query", "up")], cluster_id=cluster_id)
            if res and res.get("status") == "success":
                self._is_reachable = True
                self._use_k8s_proxy = True
                self._last_check_time = now
                return True
        except Exception:
            pass

        self._is_reachable = False
        self._last_check_time = now
        return False

    def query(self, query_string: str, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Runs instantaneous vector queries against Prometheus."""
        if not self._check_reachability(cluster_id=cluster_id):
            raise TelemetryFetchException("Prometheus unreachable or no active cluster configured.")

        if getattr(self, "_use_k8s_proxy", False):
            return self._query_k8s_proxy("api/v1/query", [("query", query_string)], cluster_id=cluster_id)

        url = f"{self._cached_base_url}/api/v1/query"
        params = {"query": query_string}
        try:
            with httpx.Client(timeout=0.8) as client:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.debug(f"Direct Prometheus query failed ({str(e)}), trying K8s proxy...")

        return self._query_k8s_proxy("api/v1/query", [("query", query_string)], cluster_id=cluster_id)

    def query_range(self, query_string: str, start: float, end: float, step: str = "15s", cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Runs range queries against Prometheus."""
        if not self._check_reachability(cluster_id=cluster_id):
            raise TelemetryFetchException("Prometheus unreachable or no active cluster configured.")

        params = [
            ("query", query_string),
            ("start", str(start)),
            ("end", str(end)),
            ("step", step)
        ]

        if getattr(self, "_use_k8s_proxy", False):
            return self._query_k8s_proxy("api/v1/query_range", params, cluster_id=cluster_id)

        url = f"{self._cached_base_url}/api/v1/query_range"
        p_dict = {"query": query_string, "start": str(start), "end": str(end), "step": step}
        try:
            with httpx.Client(timeout=0.8) as client:
                response = client.get(url, params=p_dict)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.debug(f"Direct Prometheus range query failed ({str(e)}), trying K8s proxy...")

        return self._query_k8s_proxy("api/v1/query_range", params, cluster_id=cluster_id)

    def get_alerts(self, cluster_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetches active firing & pending alerts from Prometheus AlertManager/Alerts API."""
        if not self._check_reachability(cluster_id=cluster_id):
            return {"status": "success", "data": {"alerts": []}}

        if getattr(self, "_use_k8s_proxy", False):
            try:
                return self._query_k8s_proxy("api/v1/alerts", [], cluster_id=cluster_id)
            except Exception:
                return {"status": "success", "data": {"alerts": []}}

        url = f"{self._cached_base_url}/api/v1/alerts"
        try:
            with httpx.Client(timeout=0.8) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        try:
            return self._query_k8s_proxy("api/v1/alerts", [], cluster_id=cluster_id)
        except Exception:
            return {"status": "success", "data": {"alerts": []}}

prometheus_client = PrometheusClient()
