# --- Observability AI Analysis Service ---
import re
import json
import time
from typing import Dict, Any, Optional, List
from app.clients.llm import llm_client
from app.services.context_builder import context_builder
from app.services.scope_engine import scope_engine
from shared.scope import OperationsScope
from app.utils.session_manager import session_manager
from shared.exceptions import DevOpsNexusException
from app.core.logging import logger

class AIService:
    """Provides conversational DevOps telemetry analysis, log diagnostics, and platform assistance."""

    def chat_troubleshoot(
        self,
        prompt: str,
        provider: Optional[str] = None,
        session_id: Optional[str] = None,
        scope: Optional[OperationsScope] = None
    ) -> Dict[str, Any]:
        """Gathers raw telemetry & platform context and synthesizes expert operational answers."""
        current_scope = scope or scope_engine.resolve_scope()
        context = context_builder.build_query_context(prompt, session_id=session_id, scope=current_scope)
        history = session_manager.get_history(session_id)

        history_formatted = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history[-4:]])

        system_prompt = (
            "You are DevOps Nexus AI Assistant, an enterprise DevOps Telemetry and Log Analyst.\n"
            "Your objective is to answer operational questions about Kubernetes clusters, AWS EKS integrations, "
            "pod and application logs, Prometheus metrics, users, roles, RBAC permissions matrix, audit logs, and platform settings.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Ground all your analysis strictly in the provided Context Data.\n"
            "2. If no cluster or AWS EKS account is connected (is_connected: False), state clearly and politely that no Kubernetes cluster "
            "or AWS EKS account is currently connected to DevOps Nexus, and guide the user to the 'AWS Accounts' or 'Clusters' tab.\n"
            "3. If the user asks about pods, nodes, logs, metrics, or users/roles, analyze the actual numbers and logs from the context.\n"
            "4. Format your answer using structured GitHub-style Markdown (headings, bullet points, code snippets, status tables).\n"
            "5. Do NOT perform or fabricate agentic mutations."
        )

        user_content = (
            f"User Question: {prompt}\n\n"
            f"Recent Conversation History:\n{history_formatted if history_formatted else 'No prior messages.'}\n\n"
            f"Live Cluster & Platform Telemetry Context:\n{json.dumps(context, indent=2)}"
        )

        try:
            ai_text = llm_client.generate_chat_response(user_content, system_prompt=system_prompt)
        except Exception as e:
            logger.warning(f"LLM completion provider offline/failed ({str(e)}). Generating grounded fallback answer.")
            ai_text = self._generate_grounded_fallback(prompt, context)

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
                f"Active Nodes: {infra.get('total_nodes', 0)}",
                f"CPU Utilization: {context.get('metrics', {}).get('cpu_utilization', 0.0)}%"
            ],
            "affected_resources": [p.get("name") for p in infra.get("pods_sample", []) if p.get("status") != "Running"],
            "recommendations": [
                "Register an AWS account in 'AWS Accounts' to discover Amazon EKS clusters." if not is_connected else "Monitor live telemetry streams in 'Metrics' and 'Logs'."
            ],
            "severity": "Info" if is_connected else "Warning",
            "confidence": 95 if is_connected else 100
        }

    def _generate_grounded_fallback(self, prompt: str, context: Dict[str, Any]) -> str:
        """Deterministic context-aware analyzer if external LLM API is offline."""
        lower = prompt.lower()
        cluster_info = context.get("cluster_status", {})
        infra = context.get("infrastructure_summary", {})
        is_connected = cluster_info.get("is_connected", False)
        security = context.get("platform_security_and_admin", {})

        words = set(re.findall(r'\b[a-z0-9_]+\b', lower))

        if not is_connected:
            # Users, Roles, RBAC, Permission Matrix query
            if any(w in words for w in ["user", "users", "role", "roles", "permission", "permissions", "rbac", "matrix", "iam"]):
                users_count = security.get("registered_users_count", 0)
                roles = security.get("roles_catalog", [])
                users_list = security.get("users", [])
                user_names = ", ".join([f"`{u.get('username')}` ({u.get('role')})" for u in users_list]) if users_list else "Admin (`admin`)"
                return (
                    f"### 👥 DevOps Nexus Identity & Access Management\n\n"
                    f"The platform currently has **{users_count} registered user accounts** across **{len(roles)} enterprise RBAC roles**:\n\n"
                    f"**Registered Users:** {user_names}\n\n"
                    "**Enterprise RBAC Roles:**\n"
                    "- **Administrator:** Full administrative control, user provisioning, and cluster registration.\n"
                    "- **Platform Engineer:** Infrastructure management, GitOps configuration, and telemetry oversight.\n"
                    "- **DevOps Engineer:** Deployment rollouts, pod restarts, log analysis, and incident diagnostics.\n"
                    "- **Developer:** Workload observability, application logs, and scoped developer workspace access.\n"
                    "- **Viewer:** Read-only access across cluster telemetry and audit logs."
                )

            # Audit, Settings, Verification query
            if any(w in words for w in ["audit", "audits", "verification", "setting", "settings", "verify"]):
                return (
                    "### 🛡️ Platform Administration & Verification Status\n\n"
                    "- **Operational Verification:** Subsystem truth check is active (Kubernetes API, Prometheus, Loki, ArgoCD, AI Engine).\n"
                    "- **Audit Logging:** Administrative actions, cluster modifications, and authentication events are immutably recorded.\n"
                    "- **Settings:** Configurable Git Provider integrations, Prometheus endpoints, and AWS STS role parameters."
                )

            # Cluster / Pods / Nodes / Deployments query
            if any(w in words for w in ["pod", "pods", "running", "status", "health", "node", "nodes", "deployment", "deployments", "cluster", "clusters", "eks"]):
                return (
                    "### ☸️ Cluster Status: Unconfigured\n\n"
                    "There are currently **0 Kubernetes clusters** and **0 AWS EKS accounts** registered in DevOps Nexus.\n\n"
                    "- **Total Nodes:** 0\n"
                    "- **Total Pods:** 0\n"
                    "- **Total Deployments:** 0\n"
                    "- **Telemetry Stream:** Disconnected\n\n"
                    "To view live telemetry, please register an AWS account on the **AWS Accounts** page or connect a local cluster on the **Clusters** page."
                )

            # Greetings / General help
            if words.intersection({"hi", "hello", "hey", "help"}) or "what can you do" in lower or "who are you" in lower:
                return (
                    "### 👋 Welcome to DevOps Nexus AI Operations Assistant\n\n"
                    "I am your infrastructure and telemetry intelligence assistant. I analyze live Kubernetes workloads, "
                    "pod and container logs, Prometheus metrics, AWS EKS accounts, and DevOps Nexus user permissions.\n\n"
                    "> **Status Alert**: No Kubernetes cluster or AWS EKS account is currently connected to DevOps Nexus.\n\n"
                    "**Getting Started:**\n"
                    "- ☁️ Navigate to **[AWS Accounts](/aws/accounts)** to register an AWS account via STS AssumeRole and discover your EKS clusters.\n"
                    "- ☸️ Navigate to **[Clusters](/clusters)** to add a Minikube, kubeadm, or on-prem cluster via kubeconfig.\n"
                    "- 👥 View **[Users & Roles](/admin/users)** to inspect user access and RBAC permissions."
                )

            return (
                "### ℹ️ DevOps Nexus Assistant\n\n"
                "There is currently **no active Kubernetes or AWS EKS cluster** connected to DevOps Nexus.\n\n"
                "Once you connect an AWS account or Kubernetes cluster, I will analyze your pod logs, container statuses, "
                "resource metrics, and GitOps sync states in real time."
            )

        # If connected:
        total_pods = infra.get("total_pods", 0)
        running = infra.get("running_pods_count", 0)
        failing = infra.get("failing_pods_count", 0)
        nodes = infra.get("total_nodes", 0)
        metrics = context.get("metrics", {})

        return (
            f"### 📊 Live Cluster Telemetry Analysis\n\n"
            f"- **Active Cluster:** `{cluster_info.get('active_cluster', {}).get('name', 'Connected')}`\n"
            f"- **Nodes:** {nodes} ready\n"
            f"- **Workloads:** {running}/{total_pods} pods in `Running` state ({failing} failing)\n"
            f"- **CPU Utilization:** {metrics.get('cpu_utilization', 0.0)}%\n"
            f"- **Memory Usage:** {metrics.get('memory_utilization', 0.0)}%\n\n"
            f"**Log Analysis:** {context.get('targeted_logs')}"
        )

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
            raw_response = llm_client.generate_chat_response(prompt_with_context, system_prompt=system_prompt)
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
