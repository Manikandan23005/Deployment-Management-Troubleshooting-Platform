# --- Strongly-Typed Prometheus Telemetry Tools ---
import time
from typing import Dict, Any, List
from app.clients.prometheus import prometheus_client
from app.services.monitoring_service import monitoring_service
from app.agent.risk_policy import RiskLevel
from app.agent.tools.models import (
    ToolDefinition, ToolCategory, OperationType,
    PrometheusQueryInput, PrometheusRangeInput, PrometheusClusterMetricsInput
)

def handle_prometheus_query(params: PrometheusQueryInput) -> Dict[str, Any]:
    return prometheus_client.query(params.query)

def handle_prometheus_range(params: PrometheusRangeInput) -> Dict[str, Any]:
    end_ts = params.end or time.time()
    start_ts = params.start or (end_ts - 3600.0)
    return prometheus_client.query_range(
        query_string=params.query,
        start=start_ts,
        end=end_ts,
        step=params.step
    )

def handle_prometheus_cluster_metrics(params: PrometheusClusterMetricsInput) -> Dict[str, Any]:
    return monitoring_service.get_cluster_metrics()

PROMETHEUS_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="prometheus.query",
        description="Executes an instantaneous PromQL vector query against Prometheus.",
        category=ToolCategory.PROMETHEUS,
        provider="prometheus",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="metrics:view",
        requires_confirmation=False,
        input_schema=PrometheusQueryInput,
        handler=handle_prometheus_query
    ),
    ToolDefinition(
        name="prometheus.query_range",
        description="Executes a PromQL range matrix query across a specified time window.",
        category=ToolCategory.PROMETHEUS,
        provider="prometheus",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="metrics:view",
        requires_confirmation=False,
        input_schema=PrometheusRangeInput,
        handler=handle_prometheus_range
    ),
    ToolDefinition(
        name="prometheus.cluster_metrics",
        description="Queries aggregate cluster CPU, memory, disk, and network telemetry metrics.",
        category=ToolCategory.PROMETHEUS,
        provider="prometheus",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="metrics:view",
        requires_confirmation=False,
        input_schema=PrometheusClusterMetricsInput,
        handler=handle_prometheus_cluster_metrics
    )
]
