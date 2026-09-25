# --- Autonomous Troubleshooting & Closed-Loop Remediation Engine ---
import datetime
import uuid
from typing import Dict, Any, Optional, List
from app.agent.models import (
    AutonomousIncident, 
    IncidentStatus, 
    FailureCategory, 
    FailureReason,
    ScopeContext, 
    RemediationPlan, 
    RemediationAction
)
from app.agent.incident_store import incident_store
from app.agent.target_resolver import target_resolver
from app.agent.root_cause_engine import root_cause_engine
from app.agent.remediation_planner import remediation_planner
from app.agent.risk_policy import risk_policy_engine, RiskLevel
from app.agent.verification_engine import verification_engine
from app.agent.tools import tool_registry
from app.services.audit_service import audit_service
from app.core.logging import logger

class AutonomousRemediationEngine:
    """Orchestrates end-to-end autonomous operational troubleshooting, deterministic failure analysis, 
    policy-gated remediation execution through ToolRegistry, post-action verification, and closed-loop re-investigation."""

    def __init__(self):
        from app.services.ai_agent_pipeline import ai_agent_pipeline
        self.intent_engine = ai_agent_pipeline.intent_engine
        self.planner = ai_agent_pipeline.planner
        self.scheduler = ai_agent_pipeline.scheduler
        self.confidence_engine = ai_agent_pipeline.confidence_engine
        self.reasoning_engine = ai_agent_pipeline.reasoning_engine
        self.target_resolver = target_resolver
        self.root_cause_engine = root_cause_engine
        self.remediation_planner = remediation_planner
        self.verification_engine = verification_engine
        self.tool_registry = tool_registry
        self.incident_store = incident_store

    def start_investigation(
        self,
        prompt: str,
        resource_name: Optional[str] = None,
        namespace: Optional[str] = None,
        cluster_id: Optional[str] = None,
        auto_remediate: bool = False,
        user_info: Optional[Dict[str, Any]] = None,
        confirm_token: Optional[str] = None
    ) -> AutonomousIncident:
        """Runs initial multi-source investigation and deterministic root cause diagnosis."""
        
        # 1. Intent Detection
        intent = self.intent_engine.classify_intent(prompt)

        # 2. Target Scope Resolution
        target_info = self.target_resolver.resolve_target(
            prompt=prompt,
            resource_name=resource_name,
            namespace=namespace,
            cluster_id=cluster_id
        )

        scope = ScopeContext(
            environment=target_info.get("environment", "KUBERNETES"),
            cluster_id=target_info.get("cluster_id", "default"),
            namespace=target_info.get("namespace", "devops-nexus-prod"),
            application=target_info.get("resource_name"),
            workload=target_info.get("resource_name"),
            resource_kind=target_info.get("resource_kind", "deployment")
        )

        # Initialize Incident Model
        incident = AutonomousIncident(
            user_request=prompt,
            intent=intent,
            target_scope=scope,
            status=IncidentStatus.INVESTIGATING
        )
        self.incident_store.save(incident)
        self.incident_store.add_timeline_event(
            incident.incident_id,
            IncidentStatus.INVESTIGATING,
            f"Initialized operational troubleshooting investigation for target '{scope.application}' in namespace '{scope.namespace}'."
        )

        # 3. Dynamic Investigation Plan Generation
        investigation_steps = self.planner.create_plan(
            intent=intent,
            prompt=prompt,
            target_resource=scope.application
        )

        # 4. Multi-Source Parallel Evidence Collection
        evidence = self.scheduler.execute_tools_parallel(
            target_name=scope.application or "auth-service",
            namespace=scope.namespace,
            cluster_id=scope.cluster_id
        )
        incident.evidence = evidence

        # 5. Deterministic Root Cause Analysis
        self.incident_store.add_timeline_event(
            incident.incident_id,
            IncidentStatus.DIAGNOSING,
            f"Analyzing collected telemetry across Kubernetes, ArgoCD, Prometheus, and Loki."
        )
        diagnosis = self.root_cause_engine.diagnose(evidence)
        incident.diagnosis = diagnosis
        incident.failure_category = diagnosis.get("failure_category", FailureCategory.UNKNOWN_FAILURE)
        incident.severity = diagnosis.get("severity", "Info")

        # 6. Confidence Scoring
        confidence = self.confidence_engine.calculate_confidence(
            evidence_flags=evidence.get("evidence_flags", {}),
            tools_attempted=evidence.get("tools_attempted", 1),
            tools_failed=evidence.get("tools_failed", 0),
            fallbacks_used=evidence.get("fallbacks_used", []),
            correlation_certainty=diagnosis.get("certainty", 0.85)
        )
        incident.confidence = confidence

        # 7. Remediation Planning
        plan = self.remediation_planner.build_plan(
            incident_id=incident.incident_id,
            target_scope=scope,
            diagnosis=diagnosis,
            evidence=evidence,
            user_intent=intent
        )
        incident.remediation_plan = plan

        if plan:
            self.incident_store.add_timeline_event(
                incident.incident_id,
                IncidentStatus.PLAN_GENERATED,
                f"Generated remediation plan '{plan.plan_id}' with risk level '{plan.risk_level}'. Requires confirmation: {plan.requires_confirmation}."
            )
            incident.status = IncidentStatus.AWAITING_APPROVAL if plan.requires_confirmation else IncidentStatus.PLAN_GENERATED
        else:
            if incident.failure_category == FailureCategory.HEALTHY_WORKLOAD:
                incident.status = IncidentStatus.COMPLETED
                incident.final_outcome = f"Workload '{scope.application}' is verified healthy. No remediation required."
            else:
                incident.status = IncidentStatus.PLAN_GENERATED
                incident.final_outcome = f"Diagnosis completed. {diagnosis.get('probable_cause')}"

        self.incident_store.save(incident)

        # 8. Auto-Remediate if requested and permitted
        if auto_remediate and plan:
            if not plan.requires_confirmation or confirm_token:
                return self.execute_remediation(
                    incident_id=incident.incident_id,
                    user_info=user_info,
                    confirm_token=confirm_token
                )

        return incident

    def execute_remediation(
        self,
        incident_id: str,
        user_info: Optional[Dict[str, Any]] = None,
        confirm_token: Optional[str] = None
    ) -> AutonomousIncident:
        """Executes the remediation plan associated with an incident through the ToolRegistry and performs live verification."""
        
        incident = self.incident_store.get(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID '{incident_id}' not found.")

        plan = incident.remediation_plan
        if not plan or not plan.actions:
            incident.status = IncidentStatus.FAILED
            incident.final_outcome = "No executable remediation actions available in plan."
            self.incident_store.save(incident)
            return incident

        # Check authorization / Role checks
        user = user_info or {"username": "autonomous-agent", "role": "admin"}
        user_role = user.get("role", "viewer")
        
        if user_role == "viewer":
            incident.status = IncidentStatus.FAILED
            incident.final_outcome = f"Execution blocked: User role '{user_role}' lacks permission for infrastructure remediation."
            self.incident_store.add_timeline_event(
                incident.incident_id,
                IncidentStatus.FAILED,
                f"RBAC Authorization failed: Viewer role cannot execute mutations.",
                {"user": user}
            )
            self.incident_store.save(incident)
            return incident

        # Mark Status as EXECUTING
        self.incident_store.add_timeline_event(
            incident.incident_id,
            IncidentStatus.EXECUTING,
            f"Beginning controlled execution of remediation plan '{plan.plan_id}'."
        )

        target_res = incident.target_scope.application or "auth-service"
        namespace = incident.target_scope.namespace
        cluster_id = incident.target_scope.cluster_id

        # Capture pre-action snapshot
        pre_snapshot = self.verification_engine.capture_state_snapshot(
            target_resource=target_res,
            namespace=namespace,
            cluster_id=cluster_id
        )

        all_actions_succeeded = True
        failed_action_obj: Optional[RemediationAction] = None

        for action in plan.actions:
            action.status = "running"
            
            # Execute through ToolRegistry
            tool_res = self.tool_registry.execute(
                tool_name=action.tool_name,
                input_data=action.inputs,
                user_info=user,
                confirm_token=confirm_token
            )

            action.result = tool_res.model_dump()

            if not tool_res.success:
                action.status = "failed"
                all_actions_succeeded = False
                failed_action_obj = action
                self.incident_store.add_timeline_event(
                    incident.incident_id,
                    IncidentStatus.FAILED,
                    f"Action '{action.tool_name}' failed during execution: {tool_res.error}",
                    {"tool_result": action.result}
                )
                break
            else:
                action.status = "completed"
                incident.executed_actions.append(action.model_dump())
                self.incident_store.add_timeline_event(
                    incident.incident_id,
                    IncidentStatus.EXECUTING,
                    f"Successfully executed tool '{action.tool_name}'. Output: {tool_res.data}"
                )

        if not all_actions_succeeded:
            incident.status = IncidentStatus.FAILED
            incident.final_outcome = f"Remediation tool execution failed: {failed_action_obj.result.get('error') if failed_action_obj else 'Unknown error'}"
            self.incident_store.save(incident)
            return incident

        # 9. Post-Action Verification Engine
        self.incident_store.add_timeline_event(
            incident.incident_id,
            IncidentStatus.VERIFYING,
            f"Verifying live cluster state transitions against expected desired state."
        )

        # Primary verification
        first_action = plan.actions[0]
        action_type_key = "scale_deployment" if "scale" in first_action.tool_name else ("restart_deployment" if "restart" in first_action.tool_name else "sync_argocd")
        
        verification = self.verification_engine.verify_action_execution(
            target_resource=target_res,
            action_type=action_type_key,
            before_snapshot=pre_snapshot,
            namespace=namespace,
            cluster_id=cluster_id,
            expected_params=first_action.inputs
        )
        incident.verification_results = verification

        # 10. Closed-Loop Evaluation
        if verification.get("verified", False):
            incident.status = IncidentStatus.COMPLETED
            incident.final_outcome = f"Remediation successful and verified: {verification.get('verification_summary')}"
            self.incident_store.add_timeline_event(
                incident.incident_id,
                IncidentStatus.COMPLETED,
                f"Verification PASSED: {verification.get('verification_summary')}",
                verification
            )
        else:
            # Closed-Loop Re-Investigation (Attempt 2)
            self.incident_store.add_timeline_event(
                incident.incident_id,
                IncidentStatus.REMEDIATING,
                f"Initial verification failed. Triggering re-investigation and safe secondary action evaluation."
            )

            # Re-collect live evidence
            new_evidence = self.scheduler.execute_tools_parallel(
                target_name=target_res,
                namespace=namespace,
                cluster_id=cluster_id
            )
            new_diagnosis = self.root_cause_engine.diagnose(new_evidence)

            # If still failing, escalate safely rather than looping blindly
            incident.status = IncidentStatus.ESCALATED
            incident.final_outcome = f"Verification failed post-remediation. Workload state: {new_diagnosis.get('probable_cause')}. Escalated to operations team."
            self.incident_store.add_timeline_event(
                incident.incident_id,
                IncidentStatus.ESCALATED,
                f"Closed-loop safety guard triggered: Workload not healthy after remediation. Escalating with full audit history.",
                {"re_investigation": new_diagnosis}
            )

        # Record in central Audit Log
        try:
            audit_service.log_action(
                user=user.get("username", "autonomous-agent"),
                action=f"AUTONOMOUS_REMEDIATION_{incident.status.value}",
                details={
                    "incident_id": incident.incident_id,
                    "target": incident.target_scope.model_dump(),
                    "actions": incident.executed_actions,
                    "status": incident.status.value,
                    "final_outcome": incident.final_outcome
                }
            )
        except Exception as e:
            logger.debug(f"Audit log write: {str(e)}")

        self.incident_store.save(incident)
        return incident

remediation_engine = AutonomousRemediationEngine()
