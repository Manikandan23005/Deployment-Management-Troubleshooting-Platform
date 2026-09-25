# --- Agent REST Router for Autonomous DevOps Troubleshooting & Remediation ---
from fastapi import APIRouter, Request, HTTPException, status, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from app.schemas.responses import BaseResponse
from app.dependencies.auth import get_current_user
from app.agent.agent_runtime import agent_runtime
from app.agent.incident_store import incident_store
from app.agent.models import AutonomousIncident, IncidentTimelineEntry
from app.core.logging import logger

router = APIRouter(
    prefix="/api/v1/agent",
    dependencies=[Depends(get_current_user)]
)

class TroubleshootRequest(BaseModel):
    prompt: str = Field(..., description="Operational problem prompt or alert message.")
    resource_name: Optional[str] = Field(None, description="Optional target service/pod/deployment name.")
    namespace: Optional[str] = Field("devops-nexus-prod", description="Kubernetes namespace.")
    cluster_id: Optional[str] = Field("default", description="Cluster identifier.")
    auto_remediate: bool = Field(False, description="Whether to automatically apply remediation if allowed by policy.")
    confirm_token: Optional[str] = Field(None, description="Confirmation token for medium/high risk operations.")

class RemediateRequest(BaseModel):
    incident_id: str = Field(..., description="The ID of the incident to execute remediation for.")
    confirm_token: Optional[str] = Field(None, description="Confirmation token if plan requires confirmation.")

class ConfirmRequest(BaseModel):
    confirm_token: str = Field(..., description="Security confirmation approval token.")

class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(..., description="Registered ToolRegistry tool name.")
    input_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Typed inputs for tool.")
    confirm_token: Optional[str] = Field(None, description="Confirmation token if tool is HIGH/MEDIUM risk.")

@router.post("/troubleshoot", response_model=BaseResponse)
async def troubleshoot_incident(request: Request, body: TroubleshootRequest):
    """Starts autonomous investigation, performs 15-class root cause analysis, and plans safe remediation."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)
    cluster_id = request.headers.get("X-Cluster-ID") or body.cluster_id or "default"

    try:
        incident = agent_runtime.troubleshoot(
            prompt=body.prompt,
            resource_name=body.resource_name,
            namespace=body.namespace,
            cluster_id=cluster_id,
            auto_remediate=body.auto_remediate,
            user_info=user_dict,
            confirm_token=body.confirm_token
        )
        return BaseResponse(success=True, data=incident.model_dump(), request_id=request_id)
    except Exception as e:
        logger.error(f"Troubleshoot API error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/remediate", response_model=BaseResponse)
async def remediate_incident(request: Request, body: RemediateRequest):
    """Executes the approved remediation plan through the ToolRegistry and performs post-action verification."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)

    try:
        incident = agent_runtime.remediate(
            incident_id=body.incident_id,
            user_info=user_dict,
            confirm_token=body.confirm_token
        )
        return BaseResponse(success=True, data=incident.model_dump(), request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Remediate API error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/incidents", response_model=BaseResponse)
async def list_incidents(request: Request, limit: int = Query(50, ge=1, le=100)):
    """Lists all stored autonomous incidents sorted by latest first."""
    request_id = getattr(request.state, "request_id", None)
    incidents = incident_store.list_all(limit=limit)
    return BaseResponse(success=True, data=[inc.model_dump() for inc in incidents], request_id=request_id)

@router.get("/incidents/{incident_id}", response_model=BaseResponse)
async def get_incident(request: Request, incident_id: str):
    """Fetches a specific autonomous incident record with its complete evidence graph and execution status."""
    request_id = getattr(request.state, "request_id", None)
    incident = incident_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
    return BaseResponse(success=True, data=incident.model_dump(), request_id=request_id)

@router.get("/incidents/{incident_id}/timeline", response_model=BaseResponse)
async def get_incident_timeline(request: Request, incident_id: str):
    """Retrieves the chronological audit timeline for an incident."""
    request_id = getattr(request.state, "request_id", None)
    incident = incident_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
    return BaseResponse(
        success=True, 
        data={"incident_id": incident_id, "timeline": [t.model_dump() for t in incident.timeline]},
        request_id=request_id
    )

@router.post("/incidents/{incident_id}/confirm", response_model=BaseResponse)
async def confirm_incident_remediation(request: Request, incident_id: str, body: ConfirmRequest):
    """Submits confirmation approval token and executes gated remediation."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)

    try:
        incident = agent_runtime.remediate(
            incident_id=incident_id,
            user_info=user_dict,
            confirm_token=body.confirm_token
        )
        return BaseResponse(success=True, data=incident.model_dump(), request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Confirm remediation error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/tools/execute", response_model=BaseResponse)
async def execute_tool_direct(request: Request, body: ToolExecuteRequest):
    """Directly executes a registered tool through the RBAC and Risk Policy Engine."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)

    result = agent_runtime.execute_tool(
        tool_name=body.tool_name,
        input_data=body.input_data,
        user_info=user_dict,
        confirm_token=body.confirm_token
    )
    return BaseResponse(success=result.success, data=result.model_dump(), request_id=request_id)
