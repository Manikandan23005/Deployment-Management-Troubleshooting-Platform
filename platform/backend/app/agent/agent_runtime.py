# --- Canonical Agent Runtime ---
import datetime
import asyncio
from typing import Dict, Any, List, Optional
from app.agent.target_resolver import target_resolver
from app.agent.risk_policy import risk_policy_engine
from app.agent.action_planner import action_planner
from app.agent.verification_engine import verification_engine
from app.agent.root_cause_engine import root_cause_engine
from app.agent.remediation_planner import remediation_planner
from app.agent.incident_store import incident_store
from app.agent.remediation_engine import remediation_engine
from app.agent.models import AutonomousIncident
from app.clients.llm import llm_client
from app.core.logging import logger
from app.agent.tools import tool_registry

class AgentRuntime:
    """Canonical Agentic DevOps Runtime unifying intent detection, target resolution, 
    evidence collection, correlation, risk evaluation, action planning, verification, and reasoning."""

    def __init__(self):
        from app.services.ai_agent_pipeline import ai_agent_pipeline
        self.intent_engine = ai_agent_pipeline.intent_engine
        self.planner = ai_agent_pipeline.planner
        self.scheduler = ai_agent_pipeline.scheduler
        self.correlation_engine = ai_agent_pipeline.correlation_engine
        self.confidence_engine = ai_agent_pipeline.confidence_engine
        self.remediation_planner = ai_agent_pipeline.remediation_planner
        self.reasoning_engine = ai_agent_pipeline.reasoning_engine
        self.target_resolver = target_resolver
        self.risk_policy = risk_policy_engine
        self.action_planner = action_planner
        self.verification_engine = verification_engine
        self.tool_registry = tool_registry
        self.root_cause_engine = root_cause_engine
        self.incident_store = incident_store
        self.remediation_engine = remediation_engine

    def execute_tool(
        self,
        tool_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        user_info: Optional[Dict[str, Any]] = None,
        confirm_token: Optional[str] = None
    ):
        """Executes a single infrastructure tool through the permission and risk-aware Tool Registry."""
        return self.tool_registry.execute(
            tool_name=tool_name,
            input_data=input_data,
            user_info=user_info,
            confirm_token=confirm_token
        )

    def troubleshoot(
        self,
        prompt: str,
        resource_name: Optional[str] = None,
        namespace: Optional[str] = None,
        cluster_id: Optional[str] = None,
        auto_remediate: bool = False,
        user_info: Optional[Dict[str, Any]] = None,
        confirm_token: Optional[str] = None
    ) -> AutonomousIncident:
        """Starts an autonomous troubleshooting incident investigation with root cause failure analysis and remediation planning."""
        return self.remediation_engine.start_investigation(
            prompt=prompt,
            resource_name=resource_name,
            namespace=namespace,
            cluster_id=cluster_id,
            auto_remediate=auto_remediate,
            user_info=user_info,
            confirm_token=confirm_token
        )

    def remediate(
        self,
        incident_id: str,
        user_info: Optional[Dict[str, Any]] = None,
        confirm_token: Optional[str] = None
    ) -> AutonomousIncident:
        """Executes the approved remediation plan for an existing incident with live verification."""
        return self.remediation_engine.execute_remediation(
            incident_id=incident_id,
            user_info=user_info,
            confirm_token=confirm_token
        )

    def get_incident(self, incident_id: str) -> Optional[AutonomousIncident]:
        """Fetches an existing autonomous incident record."""
        return self.incident_store.get(incident_id)

    def execute_investigation(
        self,
        prompt: str,
        resource_name: Optional[str] = None,
        namespace: Optional[str] = None,
        cluster_id: Optional[str] = None,
        scope: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Runs an evidence-first, deterministic investigation pipeline (backward-compatible)."""
        
        # 1. Intent Detection
        intent = self.intent_engine.classify_intent(prompt)
        
        # 2. Target Resolution
        target_info = self.target_resolver.resolve_target(
            prompt=prompt,
            resource_name=resource_name,
            namespace=namespace,
            cluster_id=cluster_id,
            scope=scope
        )

        # 3. Investigation Plan Generation
        investigation_steps = self.planner.create_plan(
            intent=intent,
            prompt=prompt,
            target_resource=target_info["resource_name"]
        )

        # 4. Live Evidence Collection
        evidence = self.scheduler.execute_tools_parallel(
            target_name=target_info["resource_name"],
            namespace=target_info["namespace"],
            cluster_id=target_info["cluster_id"]
        )

        # 5. Correlation & Diagnosis
        diagnosis = self.correlation_engine.correlate(evidence)

        # 6. Honest Confidence & Evidence Quality Evaluation
        confidence = self.confidence_engine.calculate_confidence(
            evidence_flags=evidence.get("evidence_flags", {}),
            tools_attempted=evidence.get("tools_attempted", 1),
            tools_failed=evidence.get("tools_failed", 0),
            fallbacks_used=evidence.get("fallbacks_used", []),
            correlation_certainty=diagnosis.get("certainty", 0.5)
        )

        # Cap quality at MEDIUM if telemetry (Prometheus or Loki) failed
        prom_status = evidence.get("prometheus_status", "FAILED_TELEMETRY")
        loki_status = evidence.get("loki_status", "FAILED_TELEMETRY")
        if prom_status == "FAILED_TELEMETRY" or loki_status == "FAILED_TELEMETRY":
            if confidence["quality"] == "HIGH":
                confidence["quality"] = "MEDIUM"
                confidence["score"] = min(confidence["score"], 79.0)

        # 7. Action Plan Generation if actionable
        suggested_plan = None
        action_needed = intent in ["REMEDIATION", "ROLLBACK", "SYNC"] or "fix" in prompt.lower() or "restart" in prompt.lower() or "scale" in prompt.lower()
        if action_needed or diagnosis.get("incident_type") not in ["HealthyWorkload", "GeneralChat"]:
            action_type = "restart_deployment" if "restart" in prompt.lower() else ("scale_deployment" if "scale" in prompt.lower() else "sync_argocd")
            suggested_plan = self.action_planner.create_action_plan(
                intent=intent,
                target_info=target_info,
                action_type=action_type
            )

        # 8. Reasoning & Response Generation
        remediation_spec = self.remediation_planner.plan_remediation(
            incident_type=diagnosis.get("incident_type", "HealthyWorkload"),
            resource_name=target_info["resource_name"],
            evidence=evidence
        )

        exec_summary, root_cause_text = self.reasoning_engine.synthesize_response(
            prompt, evidence, diagnosis, intent, target_info["resource_name"], target_info["namespace"], "cluster"
        )

        verified_evidence_items = []
        if evidence.get("pod"):
            verified_evidence_items.append(f"Pod '{evidence['pod']['name']}' is in status '{evidence['pod']['status']}' with {evidence['pod']['restarts']} restarts.")
        if evidence.get("deployment"):
            verified_evidence_items.append(f"Deployment '{evidence['deployment']['name']}' has {evidence['deployment']['ready_replicas']}/{evidence['deployment']['replicas']} replicas ready.")
        if evidence.get("argocd"):
            verified_evidence_items.append(f"ArgoCD Application '{evidence['argocd']['name']}' sync is '{evidence['argocd']['sync_status']}' and health is '{evidence['argocd']['health_status']}'.")
        
        # Telemetry evidence reporting
        verified_evidence_items.append(f"Prometheus Telemetry Status: {prom_status}")
        verified_evidence_items.append(f"Loki Central Log Stream Status: {loki_status}")

        return {
            "intent": intent,
            "target": target_info,
            "investigation_steps": investigation_steps,
            "evidence": evidence,
            "diagnosis": diagnosis,
            "confidence": confidence,
            "evidence_quality": confidence["quality"],
            "root_cause": root_cause_text,
            "executive_summary": exec_summary,
            "recommended_remediation": diagnosis.get("recommendation", "No remediation required."),
            "risk_assessment": diagnosis.get("severity", "Info"),
            "verified_evidence": verified_evidence_items,
            "supporting_evidence": [f"Fallbacks used: {f}" for f in evidence.get("fallbacks_used", [])],
            "affected_resources": [f"{target_info['namespace']}/{target_info['resource_name']}"],
            "suggested_plan": suggested_plan
        }

agent_runtime = AgentRuntime()
