# --- Strongly-Typed Loki Log Tools ---
import time
from typing import Dict, Any, List
from app.clients.loki import loki_client
from app.services.log_service import log_service
from app.agent.risk_policy import RiskLevel
from app.agent.tools.models import (
    ToolDefinition, ToolCategory, OperationType,
    LokiQueryInput, LokiRangeInput, LokiSearchErrorsInput
)

def handle_loki_query(params: LokiQueryInput) -> Dict[str, Any]:
    return loki_client.query_range(query_string=params.query, limit=params.limit)

def handle_loki_range(params: LokiRangeInput) -> Dict[str, Any]:
    return loki_client.query_range(
        query_string=params.query,
        limit=params.limit,
        start=params.start,
        end=params.end
    )

def handle_loki_search_errors(params: LokiSearchErrorsInput) -> List[Dict[str, Any]]:
    query_str = f'{{namespace="{params.namespace}"}} |= "error"'
    if params.application:
        query_str = f'{{namespace="{params.namespace}", app=~"{params.application}.*"}} |= "error"'
    
    res = loki_client.query_range(query_str, limit=params.limit)
    lines = []
    for stream in res.get("data", {}).get("result", []):
        pod_name = stream.get("stream", {}).get("pod", "app")
        for val in stream.get("values", []):
            lines.append({
                "timestamp": val[0],
                "pod": pod_name,
                "message": val[1]
            })
    return lines

LOKI_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="loki.query",
        description="Executes a LogQL query against Loki log streams.",
        category=ToolCategory.LOKI,
        provider="loki",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="logs:view",
        requires_confirmation=False,
        input_schema=LokiQueryInput,
        handler=handle_loki_query
    ),
    ToolDefinition(
        name="loki.query_range",
        description="Queries Loki log streams across a time window with limits.",
        category=ToolCategory.LOKI,
        provider="loki",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="logs:view",
        requires_confirmation=False,
        input_schema=LokiRangeInput,
        handler=handle_loki_range
    ),
    ToolDefinition(
        name="loki.search_errors",
        description="Searches for active error patterns and exception traces in namespace logs.",
        category=ToolCategory.LOKI,
        provider="loki",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="logs:view",
        requires_confirmation=False,
        input_schema=LokiSearchErrorsInput,
        handler=handle_loki_search_errors
    )
]
