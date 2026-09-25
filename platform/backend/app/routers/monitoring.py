# --- Observability REST Router ---
from fastapi import APIRouter, Request, Query, HTTPException, status
from typing import Optional
from app.schemas.responses import BaseResponse
from app.services.monitoring_service import monitoring_service
from app.services.log_service import log_service
from shared.exceptions import TelemetryFetchException
from fastapi import Depends
from app.dependencies.auth import get_current_user
from app.utils.observability import observability_metrics

router = APIRouter(
    prefix="/api/v1/monitoring",
    dependencies=[Depends(get_current_user)]
)

from app.services.scope_engine import scope_engine

@router.get("/metrics", response_model=BaseResponse)
async def get_cluster_metrics(
    request: Request,
    scope_mode: Optional[str] = Query("cluster"),
    namespace: Optional[str] = Query(None),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    """Retrieves cluster performance summary metrics."""
    request_id = getattr(request.state, "request_id", None)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        data = monitoring_service.get_cluster_metrics(scope)
        return BaseResponse(success=True, data=data, request_id=request_id)
    except Exception as e:
        return BaseResponse(
            success=True,
            data={
                "cpu_utilization": 0.0,
                "memory_utilization": 0.0,
                "disk_utilization": 0.0,
                "network_throughput_bytes": 0.0
            },
            request_id=request_id
        )

@router.get("/metrics/range", response_model=BaseResponse)
async def get_metrics_range(
    request: Request,
    metric_type: str = Query("cpu", pattern="^(cpu|memory|network|disk|requests|errors|latency|pods)$", description="Target metric telemetry type."),
    scope_mode: Optional[str] = Query("cluster"),
    namespace: Optional[str] = Query(None),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    time_range: Optional[str] = Query("1h")
):
    """Retrieves metrics range data points for graphic rendering."""
    request_id = getattr(request.state, "request_id", None)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        data = monitoring_service.get_performance_range(metric_type, scope, time_range)
        return BaseResponse(success=True, data={"values": data or []}, request_id=request_id)
    except Exception as e:
        return BaseResponse(success=True, data={"values": []}, request_id=request_id)

@router.get("/logs", response_model=BaseResponse)
async def get_logs(
    request: Request,
    pod: Optional[str] = Query("all", description="Target pod identifier."),
    container: Optional[str] = Query(None, description="Target container identifier."),
    search: Optional[str] = Query(None, description="Optional search keywords filter."),
    limit: int = Query(100, ge=1, le=1000, description="Log lines limit offset."),
    scope_mode: Optional[str] = Query("cluster"),
    namespace: Optional[str] = Query(None),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    """Retrieves container logs fetched from Loki logs indexes or Kubernetes API fallback."""
    request_id = getattr(request.state, "request_id", None)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        data = log_service.get_logs(pod, search=search, limit=limit, scope=scope, container=container)
        return BaseResponse(success=True, data=data or [], request_id=request_id)
    except Exception as e:
        return BaseResponse(success=True, data=[], request_id=request_id)

@router.get("/platform-metrics", response_model=BaseResponse)
async def get_platform_metrics(request: Request):
    """Retrieves custom platform instrumentation and latency performance metrics."""
    request_id = getattr(request.state, "request_id", None)
    return BaseResponse(
        success=True,
        data=observability_metrics.get_summary(),
        request_id=request_id
    )

@router.get("/alerts", response_model=BaseResponse)
async def get_alerts(
    request: Request,
    scope_mode: Optional[str] = Query("cluster"),
    namespace: Optional[str] = Query(None),
    app: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    """Retrieves active Prometheus AlertManager & Kubernetes workload firing alerts."""
    request_id = getattr(request.state, "request_id", None)
    try:
        scope = scope_engine.resolve_scope(scope_mode, namespace, app, domain)
        alerts = monitoring_service.get_active_alerts(scope)
        return BaseResponse(success=True, data=alerts or [], request_id=request_id)
    except Exception as e:
        return BaseResponse(success=True, data=[], request_id=request_id)
