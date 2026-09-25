# --- Strongly-Typed Kubernetes Tools ---
from typing import Dict, Any, List
from app.clients.kubernetes import k8s_client
from app.services.pod_service import pod_service
from app.services.deployment_service import deployment_service
from app.services.node_service import node_service
from app.services.namespace_service import namespace_service
from app.agent.risk_policy import RiskLevel
from app.agent.tools.models import (
    ToolDefinition, ToolCategory, OperationType,
    ListNamespacesInput, ListPodsInput, GetPodInput, GetPodLogsInput,
    ListDeploymentsInput, GetDeploymentInput, ScaleDeploymentInput, RestartDeploymentInput,
    DeletePodInput, ListServicesInput, GetServiceInput, ListNodesInput, GetNodeInput, ListEventsInput
)

def handle_list_namespaces(params: ListNamespacesInput) -> List[Dict[str, Any]]:
    return namespace_service.list_namespaces(cluster_id=params.cluster_id)

def handle_list_pods(params: ListPodsInput) -> List[Dict[str, Any]]:
    pods = pod_service.list_pods(namespace=params.namespace, cluster_id=params.cluster_id)
    if params.namespace and params.namespace != "all":
        return [p for p in pods if p.get("namespace") == params.namespace]
    return pods

def handle_get_pod(params: GetPodInput) -> Dict[str, Any]:
    return pod_service.describe_pod(params.namespace, params.name, cluster_id=params.cluster_id)

def handle_get_pod_logs(params: GetPodLogsInput) -> str:
    return pod_service.get_pod_logs(
        namespace=params.namespace,
        name=params.name,
        tail_lines=params.tail_lines,
        container=params.container,
        cluster_id=params.cluster_id
    )

def handle_list_deployments(params: ListDeploymentsInput) -> List[Dict[str, Any]]:
    return deployment_service.list_deployments(namespace=params.namespace, cluster_id=params.cluster_id)

def handle_get_deployment(params: GetDeploymentInput) -> Dict[str, Any]:
    deps = deployment_service.list_deployments(namespace=params.namespace, cluster_id=params.cluster_id)
    matched = [d for d in deps if d.get("name") == params.name]
    if matched:
        return matched[0]
    return {"name": params.name, "namespace": params.namespace, "status": "NotFound"}

def handle_scale_deployment(params: ScaleDeploymentInput) -> Dict[str, Any]:
    return deployment_service.scale_deployment(
        namespace=params.namespace,
        name=params.name,
        replicas=params.replicas,
        cluster_id=params.cluster_id
    )

def handle_restart_deployment(params: RestartDeploymentInput) -> Dict[str, Any]:
    return deployment_service.restart_deployment(
        namespace=params.namespace,
        name=params.name,
        cluster_id=params.cluster_id
    )

def handle_delete_pod(params: DeletePodInput) -> Dict[str, Any]:
    k8s_client.delete_pod(namespace=params.namespace, name=params.name, cluster_id=params.cluster_id)
    return {"success": True, "message": f"Pod '{params.name}' deleted in namespace '{params.namespace}'."}

def handle_list_services(params: ListServicesInput) -> List[Dict[str, Any]]:
    try:
        raw = k8s_client.list_services(namespace=params.namespace, cluster_id=params.cluster_id)
        return [{"name": s.metadata.name, "namespace": s.metadata.namespace, "type": s.spec.type} for s in raw]
    except Exception:
        return []

def handle_get_service(params: GetServiceInput) -> Dict[str, Any]:
    raw = k8s_client.list_services(namespace=params.namespace, cluster_id=params.cluster_id)
    matched = [s for s in raw if s.metadata.name == params.name]
    if matched:
        s = matched[0]
        return {"name": s.metadata.name, "namespace": s.metadata.namespace, "type": s.spec.type, "cluster_ip": s.spec.cluster_ip}
    return {"name": params.name, "namespace": params.namespace, "status": "NotFound"}

def handle_list_nodes(params: ListNodesInput) -> List[Dict[str, Any]]:
    return node_service.list_nodes(cluster_id=params.cluster_id)

def handle_get_node(params: GetNodeInput) -> Dict[str, Any]:
    nodes = node_service.list_nodes(cluster_id=params.cluster_id)
    matched = [n for n in nodes if n.get("name") == params.name]
    if matched:
        return matched[0]
    return {"name": params.name, "status": "NotFound"}

def handle_list_events(params: ListEventsInput) -> List[Dict[str, Any]]:
    try:
        raw_events = k8s_client.get_pod_events(
            namespace=params.namespace or "devops-nexus-prod",
            pod_name=params.resource_name or "",
            cluster_id=params.cluster_id
        )
        return [{"type": e.type, "reason": e.reason, "message": e.message} for e in raw_events]
    except Exception:
        return []

# Register Tool Definitions
KUBERNETES_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="k8s.list_namespaces",
        description="Lists all accessible Kubernetes namespaces in the cluster.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="namespaces:view",
        requires_confirmation=False,
        input_schema=ListNamespacesInput,
        handler=handle_list_namespaces
    ),
    ToolDefinition(
        name="k8s.list_pods",
        description="Lists Kubernetes pods with runtime health status, restart counts, and node placements.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="pods:view",
        requires_confirmation=False,
        input_schema=ListPodsInput,
        handler=handle_list_pods
    ),
    ToolDefinition(
        name="k8s.get_pod",
        description="Retrieves comprehensive specifications, container states, and event logs for a specific pod.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="pods:view",
        requires_confirmation=False,
        input_schema=GetPodInput,
        handler=handle_get_pod
    ),
    ToolDefinition(
        name="k8s.get_pod_logs",
        description="Streams trailing logs from a pod container via the Kubernetes API.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="logs:view",
        requires_confirmation=False,
        input_schema=GetPodLogsInput,
        handler=handle_get_pod_logs
    ),
    ToolDefinition(
        name="k8s.list_deployments",
        description="Lists Kubernetes deployments with replica counts and GitOps ownership metadata.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="deployments:view",
        requires_confirmation=False,
        input_schema=ListDeploymentsInput,
        handler=handle_list_deployments
    ),
    ToolDefinition(
        name="k8s.get_deployment",
        description="Retrieves deployment state, strategy, and replica availability.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="deployments:view",
        requires_confirmation=False,
        input_schema=GetDeploymentInput,
        handler=handle_get_deployment
    ),
    ToolDefinition(
        name="k8s.scale_deployment",
        description="Scales the desired replica count for a deployment.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.MUTATE,
        risk_level=RiskLevel.MEDIUM,
        required_permission="deployments:scale_deployment",
        requires_confirmation=False,
        input_schema=ScaleDeploymentInput,
        handler=handle_scale_deployment
    ),
    ToolDefinition(
        name="k8s.restart_deployment",
        description="Triggers a rolling restart rollout of the target deployment.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.MUTATE,
        risk_level=RiskLevel.LOW,
        required_permission="deployments:restart_deployment",
        requires_confirmation=False,
        input_schema=RestartDeploymentInput,
        handler=handle_restart_deployment
    ),
    ToolDefinition(
        name="k8s.delete_pod",
        description="Deletes a Kubernetes pod to trigger automated container recreation.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.MUTATE,
        risk_level=RiskLevel.HIGH,
        required_permission="pods:delete",
        requires_confirmation=True,
        input_schema=DeletePodInput,
        handler=handle_delete_pod
    ),
    ToolDefinition(
        name="k8s.list_services",
        description="Lists registered Kubernetes network services and cluster IPs.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="services:view",
        requires_confirmation=False,
        input_schema=ListServicesInput,
        handler=handle_list_services
    ),
    ToolDefinition(
        name="k8s.get_service",
        description="Retrieves service ports, cluster IP, and selector details.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="services:view",
        requires_confirmation=False,
        input_schema=GetServiceInput,
        handler=handle_get_service
    ),
    ToolDefinition(
        name="k8s.list_nodes",
        description="Lists worker nodes, readiness conditions, and hardware capacity.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="nodes:view",
        requires_confirmation=False,
        input_schema=ListNodesInput,
        handler=handle_list_nodes
    ),
    ToolDefinition(
        name="k8s.get_node",
        description="Retrieves worker node conditions and capacity details.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="nodes:view",
        requires_confirmation=False,
        input_schema=GetNodeInput,
        handler=handle_get_node
    ),
    ToolDefinition(
        name="k8s.list_events",
        description="Lists Kubernetes cluster warning and lifecycle events.",
        category=ToolCategory.KUBERNETES,
        provider="kubernetes",
        operation_type=OperationType.READ,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="events:view",
        requires_confirmation=False,
        input_schema=ListEventsInput,
        handler=handle_list_events
    )
]
