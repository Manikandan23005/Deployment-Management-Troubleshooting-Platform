# --- Centralized Strongly-Typed DevOps Tool Registry ---
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pydantic
from app.agent.tools.models import (
    ToolDefinition, ToolResult, ToolExecutionStatus, ToolCategory
)
from app.agent.risk_policy import RiskLevel, risk_policy_engine
from app.agent.tools.permissions import tool_permission_manager
from app.services.authz_engine import AuthorizationException
from app.services.audit_service import audit_service
from app.core.logging import logger

class ToolRegistry:
    """Centralized registry and execution controller for all deterministic DevOps infrastructure tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Registers a strongly-typed tool definition. Rejects duplicate registrations."""
        if tool.name in self._tools:
            raise ValueError(f"DuplicateToolRegistration: Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name} [{tool.category.value}] (Risk: {tool.risk_level.value})")

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Retrieves a registered tool definition by unique name."""
        return self._tools.get(name)

    def list(self) -> List[ToolDefinition]:
        """Returns all registered tool definitions."""
        return list(self._tools.values())

    def find_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        """Filters registered tools by subsystem category."""
        return [t for t in self._tools.values() if t.category == category]

    def find_by_risk(self, risk: RiskLevel) -> List[ToolDefinition]:
        """Filters registered tools by risk level tier."""
        return [t for t in self._tools.values() if t.risk_level == risk]

    def find_by_permission(self, permission: str) -> List[ToolDefinition]:
        """Filters tools requiring a specific IAM permission."""
        return [t for t in self._tools.values() if t.required_permission == permission]

    def validate_input(self, tool_name: str, input_data: Dict[str, Any]) -> Any:
        """Validates input payload against the tool's Pydantic schema."""
        tool = self.get(tool_name)
        if not tool:
            raise KeyError(f"Unknown tool '{tool_name}'.")
        if tool.input_schema:
            try:
                return tool.input_schema(**input_data)
            except pydantic.ValidationError as e:
                raise ValueError(f"Invalid input for tool '{tool_name}': {str(e)}")
        return input_data

    def execute(
        self,
        tool_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        user_info: Optional[Dict[str, Any]] = None,
        confirm_token: Optional[str] = None,
        target_override: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        Executes a deterministic infrastructure tool with strict validation, RBAC checks, 
        risk gating, confirmation token enforcement, and audit logging.
        """
        input_data = input_data or {}
        user_info = user_info or {}
        username = user_info.get("username", "viewer")

        # 1. Tool Lookup
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                tool=tool_name,
                status=ToolExecutionStatus.UNKNOWN_TOOL,
                error=f"Tool '{tool_name}' is not registered in the ToolRegistry.",
                evidence_type="SYSTEM"
            )

        # 2. Input Validation
        try:
            validated_input = self.validate_input(tool_name, input_data)
        except Exception as e:
            return ToolResult(
                tool=tool_name,
                status=ToolExecutionStatus.INVALID_INPUT,
                error=str(e),
                evidence_type=tool.category.value
            )

        # Target metadata resolution
        target_ns = getattr(validated_input, "namespace", None) or (target_override or {}).get("namespace")
        target_app = (
            getattr(validated_input, "name", None) or 
            getattr(validated_input, "application", None) or 
            getattr(validated_input, "resource_name", None) or 
            (target_override or {}).get("application") or 
            (target_override or {}).get("resource_name")
        )

        target_metadata = {
            "environment": getattr(validated_input, "environment", None) or (target_override or {}).get("environment", "On-Premises"),
            "cluster_id": getattr(validated_input, "cluster_id", None) or (target_override or {}).get("cluster_id", "default"),
            "namespace": target_ns,
            "application": target_app
        }

        # 3. RBAC Permission Check
        try:
            tool_permission_manager.check_tool_permission(
                tool_name=tool_name,
                user_info=user_info,
                namespace=target_ns,
                application=target_app
            )
        except AuthorizationException as e:
            return ToolResult(
                tool=tool_name,
                status=ToolExecutionStatus.UNAUTHORIZED,
                error=f"RBAC Permission Denied: {e.detail}",
                evidence_type=tool.category.value,
                target=target_metadata
            )

        # 4. Risk & Confirmation Enforcement
        risk_eval = risk_policy_engine.evaluate_risk(
            action_type=tool_name,
            target_resource=target_app or "cluster",
            namespace=target_ns or "devops-nexus-prod",
            parameters=input_data
        )

        if (tool.requires_confirmation or risk_eval.get("requires_confirm_token")) and confirm_token != "CONFIRM":
            return ToolResult(
                tool=tool_name,
                status=ToolExecutionStatus.CONFIRMATION_REQUIRED,
                error="High-risk operational mutation requires explicit confirmation token 'CONFIRM'.",
                evidence_type=tool.category.value,
                target=target_metadata
            )

        # 5. Deterministic Handler Execution
        if not tool.handler:
            return ToolResult(
                tool=tool_name,
                status=ToolExecutionStatus.EXECUTION_FAILED,
                error=f"Tool '{tool_name}' has no registered handler implementation.",
                evidence_type=tool.category.value,
                target=target_metadata
            )

        if hasattr(validated_input, "cluster_id") and not getattr(validated_input, "cluster_id", None):
            if target_metadata.get("cluster_id") and target_metadata.get("cluster_id") != "default":
                try:
                    setattr(validated_input, "cluster_id", target_metadata["cluster_id"])
                except Exception:
                    pass

        try:
            output = tool.handler(validated_input)

            # 6. Audit Logging for Mutating / Privileged Tools
            if tool.operation_type == "MUTATE" or tool.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]:
                audit_service.log_action(
                    username=username,
                    role_name=user_info.get("role", "Operator"),
                    action=f"tool_exec_{tool_name.replace('.', '_')}",
                    target_resource=f"{target_ns or 'cluster'}/{target_app or 'resource'}",
                    ai_assisted=True
                )

            return ToolResult(
                tool=tool_name,
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                evidence_type=tool.category.value,
                target=target_metadata
            )
        except Exception as e:
            logger.error(f"Tool execution failed for '{tool_name}': {str(e)}")
            return ToolResult(
                tool=tool_name,
                status=ToolExecutionStatus.EXECUTION_FAILED,
                error=str(e),
                evidence_type=tool.category.value,
                target=target_metadata
            )

    def execute_parallel(
        self,
        tool_calls: List[Dict[str, Any]],
        user_info: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """Executes multiple read-only tools concurrently using thread pools."""
        results: List[ToolResult] = []
        if not tool_calls:
            return results

        def _run_single(call_spec: Dict[str, Any]) -> ToolResult:
            name = call_spec.get("tool")
            inputs = call_spec.get("input", {})
            target = call_spec.get("target")
            return self.execute(
                tool_name=name,
                input_data=inputs,
                user_info=user_info,
                target_override=target
            )

        with ThreadPoolExecutor(max_workers=min(len(tool_calls), 8)) as executor:
            futures = [executor.submit(_run_single, call) for call in tool_calls]
            for f in as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as e:
                    results.append(ToolResult(
                        tool="unknown",
                        status=ToolExecutionStatus.EXECUTION_FAILED,
                        error=str(e),
                        evidence_type="SYSTEM"
                    ))
        return results

tool_registry = ToolRegistry()
