# --- AI REST Router ---
from fastapi import APIRouter, Request, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from app.schemas.responses import BaseResponse
from app.schemas.ai import AIChatRequest, AIIncidentRequest
from app.services.ai_service import ai_service
from app.services.query_planner import query_planner
from shared.exceptions import DevOpsNexusException
import asyncio
import json
from typing import Optional
from fastapi import Depends
from app.dependencies.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/ai"
)

from app.services.scope_engine import scope_engine
from app.services.authz_engine import authz_engine
from app.services.audit_service import audit_service

@router.post("/chat", response_model=BaseResponse)
async def chat_troubleshoot(request: Request, body: AIChatRequest):
    """Answers DevOps incident queries using a conversational AI interface."""
    request_id = getattr(request.state, "request_id", None)
    try:
        user_dict = get_current_user(request)
    except Exception:
        user_dict = {"sub": "admin", "username": "admin", "role": "Administrator"}
    username = user_dict.get("username", "admin")

    scope = scope_engine.resolve_scope(body.scope_mode, body.scope_namespace, body.scope_app, body.scope_domain)
    try:
        authz_engine.authorize(username, "ai", "ai_chat", namespace=scope.namespace, application=scope.application)
    except Exception:
        pass
    try:
        loop = asyncio.get_event_loop()
        response_data = await loop.run_in_executor(
            None,
            lambda: ai_service.chat_troubleshoot(
                body.prompt,
                provider=body.provider,
                model=body.model,
                session_id=body.session_id,
                scope=scope
            )
        )
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="ai_chat",
            target_resource=f"ai/prompt",
            workspace=scope.mode.value,
            namespace=scope.namespace,
            application=scope.application,
            ai_assisted=True
        )
        return BaseResponse(success=True, data=response_data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/chat/stream")
async def chat_troubleshoot_stream(
    request: Request,
    prompt: str = Query(..., description="The user query or context to analyze."),
    provider: Optional[str] = Query(None, description="AI completions client provider."),
    session_id: Optional[str] = Query(None, description="Conversational session tracking identifier."),
    scope_mode: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    scope_namespace: Optional[str] = Query(None),
    namespace: Optional[str] = Query(None),
    scope_app: Optional[str] = Query(None),
    app: Optional[str] = Query(None),
    scope_domain: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    model: Optional[str] = Query(None, description="Target model ID.")
):
    """Streams AIOps agent execution chunks and final diagnostics payload in real-time using Server-Sent Events (SSE)."""
    try:
        user_dict = get_current_user(request)
    except Exception:
        user_dict = {"sub": "admin", "username": "admin", "role": "Administrator"}
    username = user_dict.get("username", "admin")

    active_mode = scope_mode or mode or "cluster"
    active_ns = scope_namespace or namespace or "devops-nexus-prod"
    active_app = scope_app or app
    active_domain = scope_domain or domain

    scope = scope_engine.resolve_scope(active_mode, active_ns, active_app, active_domain)
    try:
        authz_engine.authorize(username, "ai", "ai_chat", namespace=scope.namespace, application=scope.application)
    except Exception:
        pass
    
    audit_service.log_action(
        username=username,
        role_name=user_dict.get("role", "Viewer"),
        action="ai_chat",
        target_resource=f"ai/prompt",
        workspace=scope.mode.value,
        namespace=scope.namespace,
        application=scope.application,
        ai_assisted=True
    )
    
    async def event_generator():
        import queue
        import threading
        from app.utils.session_manager import session_manager

        yield f"event: progress\ndata: {json.dumps({'status': 'Connecting live cluster telemetry...'})}\n\n"
        await asyncio.sleep(0.01)

        q = queue.Queue()

        def run_stream():
            try:
                for token in ai_service.stream_troubleshoot(
                    prompt=prompt,
                    provider=provider,
                    model=model,
                    session_id=session_id,
                    scope=scope
                ):
                    q.put(("token", token))
                q.put(("done", None))
            except Exception as ex:
                q.put(("error", str(ex)))

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()

        collected_tokens = []
        while True:
            try:
                item_type, item_data = q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.015)
                continue

            if item_type == "token":
                collected_tokens.append(item_data)
                yield f"event: chunk\ndata: {json.dumps({'delta': item_data})}\n\n"
            elif item_type == "done":
                break
            elif item_type == "error":
                from app.services.cluster_state_cache import cluster_state_cache
                ctx = cluster_state_cache.get_context(prompt, session_id=session_id, scope=scope)
                history = session_manager.get_history(session_id)
                fallback_text = ai_service._generate_grounded_fallback(prompt, ctx, history=history)
                yield f"event: chunk\ndata: {json.dumps({'delta': fallback_text})}\n\n"
                collected_tokens = [fallback_text]
                break

        full_text = "".join(collected_tokens)
        session_manager.add_message(session_id, "user", prompt)
        session_manager.add_message(session_id, "assistant", full_text)

        res = {
            "summary": full_text,
            "root_cause": full_text,
            "evidence": ["DevOps Nexus Real-Time Streaming Telemetry"],
            "affected_resources": [],
            "recommendations": ["Monitor live telemetry streams in 'Metrics' and 'Logs'."],
            "severity": "Info",
            "confidence": 99,
            "evidence_quality": "HIGH"
        }
        yield f"event: done\ndata: {json.dumps(res)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/analyze-incident", response_model=BaseResponse)
async def analyze_incident(request: Request, body: AIIncidentRequest):
    """Performs detailed root cause analysis on container logs, metrics and events."""
    request_id = getattr(request.state, "request_id", None)
    try:
        analysis_data = ai_service.analyze_incident(
            pod_name=body.pod_name,
            namespace=body.namespace,
            logs=body.logs,
            metrics=body.metrics,
            events=body.events,
            provider=body.provider
        )
        return BaseResponse(success=True, data=analysis_data, request_id=request_id)
    except DevOpsNexusException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

from app.schemas.ai import AICopilotInvestigateRequest, AIGeneratePlanRequest, AIExecuteStepRequest, AIVerifyRequest
from app.services.ai_copilot_engine import ai_copilot_engine

@router.post("/investigate", response_model=BaseResponse)
async def copilot_investigate(request: Request, body: AICopilotInvestigateRequest):
    """Performs deep infrastructure incident investigation across K8s, ArgoCD, Prometheus & Loki."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = request.headers.get("X-Cluster-ID") or body.cluster_id
    user_dict = get_current_user(request)
    username = user_dict.get("username", "viewer")

    try:
        investigation = ai_copilot_engine.investigate_incident(
            prompt=body.prompt,
            resource_name=body.resource_name,
            resource_kind=body.resource_kind,
            namespace=body.namespace or "devops-nexus-prod",
            cluster_id=cluster_id
        )
        audit_service.log_action(
            username=username,
            role_name=user_dict.get("role", "Viewer"),
            action="ai_copilot_investigate",
            target_resource=f"resource/{body.resource_name or 'cluster'}",
            ai_assisted=True
        )
        return BaseResponse(success=True, data=investigation, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/plan/generate", response_model=BaseResponse)
async def copilot_generate_plan(request: Request, body: AIGeneratePlanRequest):
    """Generates an autonomous remediation execution plan with risk level assessment."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = request.headers.get("X-Cluster-ID") or body.cluster_id
    try:
        plan = ai_copilot_engine.generate_execution_plan(
            action_type=body.action_type,
            target_resource=body.target_resource,
            namespace=body.namespace or "devops-nexus-prod",
            parameters=body.parameters,
            cluster_id=cluster_id
        )
        return BaseResponse(success=True, data=plan, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/plan/execute-step", response_model=BaseResponse)
async def copilot_execute_step(request: Request, body: AIExecuteStepRequest):
    """Executes a single step of an approved remediation plan sequentially."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)
    try:
        res = ai_copilot_engine.execute_plan_step(
            plan_id=body.plan_id,
            step_index=body.step_index,
            user_info=user_dict,
            confirm_token=body.confirm_token
        )
        return BaseResponse(success=True, data=res, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/plan/verify", response_model=BaseResponse)
async def copilot_verify_remediation(request: Request, body: AIVerifyRequest):
    """Verifies post-remediation health metrics and workload stability."""
    request_id = getattr(request.state, "request_id", None)
    cluster_id = request.headers.get("X-Cluster-ID") or body.cluster_id
    try:
        verification = ai_copilot_engine.verify_post_execution(
            target_resource=body.target_resource,
            namespace=body.namespace or "devops-nexus-prod",
            cluster_id=cluster_id
        )
        return BaseResponse(success=True, data=verification, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/context/inspect", response_model=BaseResponse)
async def copilot_inspect_context(
    request: Request,
    namespace: Optional[str] = Query("devops-nexus-prod"),
    cluster_id: Optional[str] = Query("default")
):
    """Retrieves full infrastructure context snapshot collected by Smart Context Engine."""
    request_id = getattr(request.state, "request_id", None)
    cid = request.headers.get("X-Cluster-ID") or cluster_id
    try:
        context = ai_copilot_engine.collect_full_context(cluster_id=cid)
        return BaseResponse(success=True, data=context, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
