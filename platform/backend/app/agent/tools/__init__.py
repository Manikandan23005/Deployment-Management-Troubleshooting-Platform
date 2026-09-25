# --- DevOps Tool System Package ---
from app.agent.tools.models import (
    ToolDefinition, ToolResult, ToolExecutionStatus, ToolCategory, OperationType
)
from app.agent.tools.permissions import tool_permission_manager, ToolPermissionManager
from app.agent.tools.registry import tool_registry, ToolRegistry
from app.agent.tools.kubernetes_tools import KUBERNETES_TOOLS
from app.agent.tools.prometheus_tools import PROMETHEUS_TOOLS
from app.agent.tools.loki_tools import LOKI_TOOLS
from app.agent.tools.argocd_tools import ARGOCD_TOOLS
from app.agent.tools.git_tools import GIT_TOOLS

def bootstrap_default_tool_registry(registry: ToolRegistry = tool_registry) -> ToolRegistry:
    """Registers all standard DevOps infrastructure tools into the Tool Registry."""
    all_tools = (
        KUBERNETES_TOOLS +
        PROMETHEUS_TOOLS +
        LOKI_TOOLS +
        ARGOCD_TOOLS +
        GIT_TOOLS
    )
    for tool in all_tools:
        try:
            registry.register(tool)
        except ValueError:
            pass  # Already registered
    return registry

# Bootstrap tools into global singleton on import
bootstrap_default_tool_registry(tool_registry)

__all__ = [
    "tool_registry",
    "ToolRegistry",
    "tool_permission_manager",
    "ToolPermissionManager",
    "ToolDefinition",
    "ToolResult",
    "ToolExecutionStatus",
    "ToolCategory",
    "OperationType",
    "bootstrap_default_tool_registry",
    "KUBERNETES_TOOLS",
    "PROMETHEUS_TOOLS",
    "LOKI_TOOLS",
    "ARGOCD_TOOLS",
    "GIT_TOOLS"
]
