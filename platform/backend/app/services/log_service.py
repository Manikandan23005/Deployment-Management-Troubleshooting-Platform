# --- Loki & K8s Pod Logs Aggregator Service with Cluster Context ---
import time
from typing import List, Dict, Any, Optional
from app.clients.loki import loki_client
from app.services.pod_service import pod_service
from shared.exceptions import TelemetryFetchException
from app.core.logging import logger

class LogService:
    def get_logs(
        self,
        pod_name: str,
        search: Optional[str] = None,
        limit: int = 100,
        scope: Optional[Any] = None,
        container: Optional[str] = None,
        cluster_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries Loki log streams for pods, with live Kubernetes API log stream fallback."""
        try:
            from app.services.cluster_registry import cluster_registry
            if not cluster_registry.list_clusters():
                return []
        except Exception:
            return []

        result = []

        # 1. Format LogQL selector
        logql_clause = []
        if scope:
            from app.services.scope_engine import scope_engine
            target_namespaces = scope.get_effective_namespaces()
            if target_namespaces:
                ns_regex = "|".join(target_namespaces)
                logql_clause.append(f'namespace=~"{ns_regex}"')
            
            scope_mode = getattr(scope, "mode", None)
            mode_val = getattr(scope_mode, "value", str(scope_mode or "")) if scope_mode else "cluster"
            if mode_val == "app" and scope.application:
                logql_clause.append(f'app=~"{scope.application}.*"')
                
        if pod_name and pod_name != "all" and not pod_name.startswith("{"):
            logql_clause.append(f'pod="{pod_name}"')
            
        if container:
            logql_clause.append(f'container="{container}"')
            
        if logql_clause:
            logql = "{" + ", ".join(logql_clause) + "}"
        else:
            logql = '{app=~".+"}'

        if search:
            logql += f' |= "{search}"'

        # 2. Try Loki Query
        try:
            res = loki_client.query_range(logql, limit=limit, cluster_id=cluster_id)
            for stream in res.get("data", {}).get("result", []):
                pod = stream.get("stream", {}).get("pod") or stream.get("stream", {}).get("app") or pod_name
                for val in stream.get("values", []):
                    msg = val[1]
                    if not search or search.lower() in msg.lower():
                        result.append({
                            "timestamp": self._nano_to_iso(val[0]),
                            "pod": pod,
                            "message": msg
                        })
            if result:
                return result[:limit]
        except TelemetryFetchException as e:
            logger.debug(f"Loki query note ({str(e)}). Falling back to live Kubernetes API pod logs.")
        except Exception as e:
            logger.debug(f"Loki log parse note ({str(e)}).")

        # 3. Fallback to Live Kubernetes API Pod Logs
        try:
            pods = pod_service.list_pods(cluster_id=cluster_id)
            if scope:
                from app.services.scope_engine import scope_engine
                target_pods = scope_engine.filter_pods(pods, scope)
            else:
                target_pods = pods

            if pod_name and pod_name != "all" and not pod_name.startswith("{"):
                matched = [p for p in target_pods if pod_name.lower() in p.get("podName", "").lower() or pod_name.lower() in p.get("name", "").lower()]
                if matched:
                    target_pods = matched

            for p in target_pods[:8]:
                p_name = p.get("podName") or p.get("name")
                ns = p.get("namespace", "devops-nexus-prod")
                try:
                    logs_text = pod_service.get_pod_logs(ns, p_name, tail_lines=30, container=container, cluster_id=cluster_id)
                    if logs_text:
                        lines = logs_text.strip().split("\n")
                        for l in lines:
                            if not l.strip():
                                continue
                            if search and search.lower() not in l.lower():
                                continue
                            result.append({
                                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                "pod": p_name,
                                "message": l.strip()
                            })
                except Exception as e:
                    logger.debug(f"Could not read logs for pod {p_name}: {str(e)}")

            if result:
                return result[:limit]
        except Exception as e:
            logger.warning(f"K8s pod log fallback warning: {str(e)}")

        return []

    def _nano_to_iso(self, nano_str: str) -> str:
        try:
            seconds = float(nano_str) / 1e9
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(seconds))
        except Exception:
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

log_service = LogService()
