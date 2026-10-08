# --- Observability AI Analysis Service ---
import re
import json
import time
from typing import Dict, Any, Optional, List
# pyrefly: ignore [missing-import]
from app.clients.llm import llm_client
# pyrefly: ignore [missing-import]
from app.clients.ai import ai_client
# pyrefly: ignore [missing-import]
from app.core.settings import settings
# pyrefly: ignore [missing-import]
from app.services.context_builder import context_builder
# pyrefly: ignore [missing-import]
from app.services.scope_engine import scope_engine
# pyrefly: ignore [missing-import]
from shared.scope import OperationsScope
# pyrefly: ignore [missing-import]
from app.utils.session_manager import session_manager
# pyrefly: ignore [missing-import]
from app.core.logging import logger

class AIService:
    """Provides conversational DevOps telemetry analysis, log diagnostics, and platform assistance."""

    # Providers served by the OpenAI-compatible AIClient (not AWS Bedrock).
    _OPENAI_COMPATIBLE_PROVIDERS = {"groq", "openai", "ollama", "lmstudio"}

    def _invoke_llm(
        self,
        prompt: str,
        system_prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Routes a chat completion to the correct engine based on the selected provider.

        Non-Bedrock providers (groq/openai/ollama/lmstudio) go through the
        OpenAI-compatible AIClient; everything else uses the AWS Bedrock client.
        """
        resolved = (provider or getattr(settings, "AI_PROVIDER", None) or "bedrock").lower()
        if resolved in self._OPENAI_COMPATIBLE_PROVIDERS:
            return ai_client.generate_chat_response(prompt, system_prompt=system_prompt, provider=resolved)
        return llm_client.generate_chat_response(prompt, system_prompt=system_prompt, provider=resolved, model=model)

    def chat_troubleshoot(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        scope: Optional[OperationsScope] = None
    ) -> Dict[str, Any]:
        """Gathers raw telemetry & platform context and synthesizes expert operational answers."""
        current_scope = scope or scope_engine.resolve_scope()
        # pyrefly: ignore [missing-import]
        from app.services.cluster_state_cache import cluster_state_cache
        context = cluster_state_cache.get_context(prompt, session_id=session_id, scope=current_scope)
        history = session_manager.get_history(session_id)

        history_formatted = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history[-4:]])

        system_prompt = (
            "You are DevOps Nexus AI Operations Assistant, an enterprise DevOps Telemetry and Log Analyst.\n"
            "Your objective is to answer the user's operational questions with 100% precision about Kubernetes clusters, "
            "AWS EKS workloads, GitOps source of truth (ArgoCD), pod and container logs, Prometheus metrics, users, roles, "
            "RBAC permissions matrix, and audit trails.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. DIRECTLY ANSWER THE SPECIFIC QUESTION ASKED in the very first sentence with exact counts and facts. For example, if asked 'How many pods are managed by the gitops?', state the exact number immediately (e.g. 'There are currently 8 pods managed by GitOps...').\n"
            "2. Distinguish clearly between GitOps-managed workloads (ArgoCD reconciled microservices in devops-nexus-prod like auth-service, frontend-service, etc.) and native Kubernetes-managed workloads (such as argocd-*, prometheus-*, kube-system).\n"
            "3. Format your answer using structured GitHub-flavored Markdown: bold key numbers, use concise bullet points, Markdown tables for workload comparisons, and code spans for resource names.\n"
            "4. Ground every single claim strictly in the provided Live Cluster & Platform Telemetry Context JSON. Do not hallucinate resources not present in context.\n"
            "5. If no cluster or AWS EKS account is connected (is_connected: False), state clearly and politely that no Kubernetes cluster is currently connected and guide the user to 'AWS Accounts' or 'Clusters'."
        )

        user_content = (
            f"User Question: {prompt}\n\n"
            f"Recent Conversation History:\n{history_formatted if history_formatted else 'No prior messages.'}\n\n"
            f"Live Cluster & Platform Telemetry Context:\n{json.dumps(context, indent=2)}"
        )

        try:
            ai_text = self._invoke_llm(user_content, system_prompt=system_prompt, provider=provider, model=model)
        except Exception as e:
            logger.info(f"LLM provider ({provider or 'default'}) fallback active: {str(e)}")
            ai_text = self._generate_grounded_fallback(prompt, context, history=history)

        # Store session conversation history
        session_manager.add_message(session_id, "user", prompt)
        session_manager.add_message(session_id, "assistant", ai_text)

        # Build response payload
        cluster_info = context.get("cluster_status", {})
        infra = context.get("infrastructure_summary", {})
        is_connected = cluster_info.get("is_connected", False)

        return {
            "summary": ai_text,
            "root_cause": ai_text,
            "evidence": [
                f"Cluster Connection: {'Online' if is_connected else 'Offline / No Cluster Configured'}",
                f"Active Pods: {infra.get('total_pods', 0)} total ({infra.get('running_pods_count', 0)} Running)",
                f"GitOps Managed Pods: {infra.get('gitops_managed_pods_count', 0)} pods",
                f"Active Nodes: {infra.get('total_nodes', 0)}",
                f"CPU Utilization: {context.get('metrics', {}).get('cpu_utilization', 0.0)}%"
            ],
            "affected_resources": [p.get("name") for p in infra.get("pods_sample", []) if p.get("status") != "Running"],
            "recommendations": [
                "Register an AWS account in 'AWS Accounts' to discover Amazon EKS clusters." if not is_connected else "Monitor live telemetry streams in 'Metrics' and 'Logs'."
            ],
            "severity": "Info" if is_connected else "Warning",
            "confidence": 98 if is_connected else 100,
            "evidence_quality": "HIGH" if is_connected else "MEDIUM"
        }

    def _generate_grounded_fallback(self, prompt: str, context: Dict[str, Any], history: Optional[List[Dict[str, str]]] = None) -> str:
        """Conversational Kubernetes Jarvis engine providing multi-turn reasoning and incident remediation."""
        # pyrefly: ignore [missing-import]
        from app.services.k8s_jarvis_engine import k8s_jarvis_engine
        return k8s_jarvis_engine.answer_query(prompt, context, history or [])

    def analyze_incident(
        self,
        pod_name: str,
        namespace: str,
        logs: str = "",
        metrics: Optional[Dict[str, Any]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs automated root-cause analysis on a pod failure incident."""
        context = context_builder.build_incident_context(pod_name, namespace)
        
        system_prompt = (
            "You are DevOps Nexus AI Assistant, an enterprise AIOps engine. "
            "Perform root cause analysis on the provided pod failure context.\n"
            "Output your entire response as a single, valid JSON object matching the AIStructuredResponse schema."
        )
        
        prompt_with_context = (
            f"Incident Analysis Request for Pod {pod_name} in namespace {namespace}:\n"
            f"Target Logs:\n{logs}\n\n"
            f"Target Metrics:\n{json.dumps(metrics or {})}\n\n"
            f"Target Events:\n{json.dumps(events or [])}\n\n"
            f"Full Cluster Context:\n{json.dumps(context, indent=2)}"
        )

        try:
            raw_response = self._invoke_llm(prompt_with_context, system_prompt=system_prompt, provider=provider)
            return self._parse_json_response(raw_response)
        except Exception:
            return {
                "summary": f"Incident Diagnostics for {pod_name}",
                "root_cause": f"Logs and lifecycle inspection for pod '{pod_name}' in namespace '{namespace}'.",
                "evidence": [f"Pod: {pod_name}", f"Namespace: {namespace}"],
                "affected_resources": [pod_name],
                "recommendations": ["Inspect container logs and verify resource requests."],
                "severity": "Warning",
                "confidence": 90
            }

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()
        
        try:
            return json.loads(cleaned)
        except Exception:
            return {
                "summary": "AI Diagnostics Completed",
                "root_cause": cleaned,
                "evidence": ["Raw completions text payload"],
                "affected_resources": [],
                "recommendations": ["Review live logs directly"],
                "severity": "Info",
                "confidence": 85
            }

ai_service = AIService()
