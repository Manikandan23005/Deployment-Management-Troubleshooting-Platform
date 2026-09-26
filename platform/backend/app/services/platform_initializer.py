# --- Zero-Touch Platform Self-Healing Initialization Engine ---
import base64
import time
from typing import Dict, Any, List
from app.core.logging import logger
from app.clients.kubernetes import k8s_client
from app.clients.argocd import argocd_client
from app.clients.prometheus import prometheus_client
from app.services.port_supervisor import port_supervisor

class PlatformInitializer:
    """Automates self-healing bootstrap, GitOps application reconciliation, microservice services creation, and telemetry NodePort configuration on platform boot."""

    def initialize_platform(self):
        logger.info("Initializing DevOps Nexus zero-touch platform bootstrap...")

        # 1. Register & Auto-Discover Local Cluster
        try:
            from app.services.cluster_registry import cluster_registry
            cluster_registry._auto_detect_local_clusters()
            logger.info("✅ Cluster Registry verified.")
        except Exception as e:
            logger.warning(f"Cluster registry auto-registration warning: {str(e)}")

        # 1.5. Ensure Persistent AWS Account & EKS Cluster Target Connection
        try:
            from app.aws.account_registry import aws_account_registry
            from app.aws.models import AWSAccountRegistrationRequest
            from app.core.settings import settings

            default_acc_id = getattr(settings, "DEFAULT_AWS_ACCOUNT_ID", "605294565283")
            default_role_arn = getattr(settings, "DEFAULT_AWS_ROLE_ARN", "arn:aws:iam::605294565283:role/DevOpsNexusAccessRole")
            default_region = getattr(settings, "DEFAULT_AWS_REGION", "ap-south-1")

            acc = aws_account_registry.get_account(default_acc_id)
            if not acc:
                req = AWSAccountRegistrationRequest(
                    name="Production AWS",
                    account_id=default_acc_id,
                    role_arn=default_role_arn,
                    default_region=default_region
                )
                acc = aws_account_registry.register_account(req)
                logger.info(f"✅ Registered persistent AWS account {default_acc_id} ({default_role_arn}).")

            # Register/link EKS cluster target
            try:
                aws_account_registry.register_eks_cluster_as_target(
                    acc.id if acc else default_acc_id,
                    "devops-nexus-prod",
                    region=default_region,
                    is_default=True
                )
                logger.info("✅ Linked persistent EKS cluster 'devops-nexus-prod' as active target.")
            except Exception as cluster_err:
                logger.debug(f"EKS target auto-link note: {str(cluster_err)}")
        except Exception as aws_err:
            logger.warning(f"Persistent AWS account initialization note: {str(aws_err)}")

        # 2. Ensure Prometheus NodePort 30090 Exposure
        self._ensure_prometheus_nodeport()

        # 3. Auto-Authenticate ArgoCD Client
        try:
            argocd_client._ensure_token()
            logger.info("✅ ArgoCD client auto-authenticated.")
        except Exception as e:
            logger.warning(f"ArgoCD client auto-auth warning: {str(e)}")

        # 4. Reconcile Core Microservice ArgoCD Applications
        self._reconcile_argocd_applications()

        # 5. Reconcile Microservice K8s Services
        self._reconcile_k8s_microservice_services()

        # 6. Ensure Telemetry Ports & Port-Forwards
        try:
            port_supervisor.ensure_telemetry_ports()
            logger.info("✅ Telemetry ports supervisor verified.")
        except Exception as e:
            logger.warning(f"Port supervisor warning: {str(e)}")

        logger.info("🚀 DevOps Nexus platform self-healing bootstrap complete 100%.")

    def _ensure_prometheus_nodeport(self):
        """Ensures kube-prometheus-stack-prometheus service is exposed on NodePort 30090."""
        try:
            clients = k8s_client.get_clients()
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]

            svc = v1.read_namespaced_service("kube-prometheus-stack-prometheus", "monitoring")
            if svc.spec.type != "NodePort":
                v1.patch_namespaced_service(
                    name="kube-prometheus-stack-prometheus",
                    namespace="monitoring",
                    body={
                        "spec": {
                            "type": "NodePort",
                            "ports": [{"name": "http-web", "port": 9090, "targetPort": 9090, "nodePort": 30090}]
                        }
                    }
                )
                logger.info("✅ Exposed Prometheus service on NodePort 30090.")
            else:
                logger.info("✅ Prometheus service NodePort 30090 verified.")
        except Exception as e:
            logger.warning(f"Prometheus NodePort auto-patch warning: {str(e)}")

    def _reconcile_argocd_applications(self):
        """Ensures all 9 core microservices have valid ArgoCD Application CRDs in namespace argocd."""
        core_services = [
            ("auth", "helm/auth"),
            ("frontend", "helm/frontend"),
            ("gateway", "helm/gateway"),
            ("notification", "helm/notification"),
            ("orders", "helm/orders"),
            ("payment", "helm/payment"),
            ("products", "helm/products"),
            ("traffic-generator", "kubernetes"),
            ("users", "helm/users")
        ]

        try:
            clients = k8s_client.get_clients()
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
            from kubernetes import client as k8s_sdk
            custom_api = k8s_sdk.CustomObjectsApi(v1.api_client)

            existing_crd_apps = custom_api.list_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace="argocd",
                plural="applications"
            ).get("items", [])

            existing_names = {item.get("metadata", {}).get("name") for item in existing_crd_apps}

            for prefix, repo_path in core_services:
                app_name = f"{prefix}-prod"
                if app_name not in existing_names:
                    app_manifest = {
                        "apiVersion": "argoproj.io/v1alpha1",
                        "kind": "Application",
                        "metadata": {
                            "name": app_name,
                            "namespace": "argocd",
                            "labels": {"env": "prod"}
                        },
                        "spec": {
                            "project": "default",
                            "source": {
                                "repoURL": "https://github.com/Manikandan23005/Microservice-Deployment-Monitoring-Platform.git",
                                "targetRevision": "main",
                                "path": repo_path
                            },
                            "destination": {
                                "server": "https://kubernetes.default.svc",
                                "namespace": "devops-nexus-prod"
                            },
                            "syncPolicy": {
                                "automated": {
                                    "selfHeal": True,
                                    "prune": False
                                }
                            },
                            "ignoreDifferences": [
                                {
                                    "group": "apps",
                                    "kind": "Deployment",
                                    "jsonPointers": ["/spec/replicas"]
                                }
                            ]
                        }
                    }
                    try:
                        custom_api.create_namespaced_custom_object(
                            group="argoproj.io",
                            version="v1alpha1",
                            namespace="argocd",
                            plural="applications",
                            body=app_manifest
                        )
                        logger.info(f"Auto-created missing ArgoCD Application CRD '{app_name}'.")
                    except Exception as crd_err:
                        logger.warning(f"CRD auto-creation for '{app_name}' error: {str(crd_err)}")
                else:
                    logger.info(f"ArgoCD Application CRD '{app_name}' verified.")

        except Exception as e:
            logger.warning(f"ArgoCD applications reconciliation warning: {str(e)}")

    def _reconcile_k8s_microservice_services(self):
        """Ensures Kubernetes Services exist for all microservices in devops-nexus-prod namespace."""
        services_def = [
            ("frontend-service", "frontend", "NodePort", 3000, 30080),
            ("gateway-service", "gateway", "NodePort", 8080, 30808),
            ("auth-service", "auth", "ClusterIP", 8000, None),
            ("orders-service", "orders", "ClusterIP", 8000, None),
            ("products-service", "products", "ClusterIP", 8000, None),
            ("payment-service", "payment", "ClusterIP", 8000, None),
            ("users-service", "users", "ClusterIP", 8000, None),
            ("notification-service", "notification", "ClusterIP", 8000, None),
        ]
        try:
            clients = k8s_client.get_clients()
            v1 = clients.get("v1") if isinstance(clients, dict) else clients[0]
            existing_svc_names = {s.metadata.name for s in v1.list_namespaced_service("devops-nexus-prod").items}

            for svc_name, app_label, svc_type, port, node_port in services_def:
                if svc_name not in existing_svc_names:
                    port_obj = {"name": "http", "port": port, "targetPort": port}
                    if node_port:
                        port_obj["nodePort"] = node_port
                    svc_manifest = {
                        "apiVersion": "v1",
                        "kind": "Service",
                        "metadata": {"name": svc_name, "namespace": "devops-nexus-prod", "labels": {"app": app_label}},
                        "spec": {
                            "type": svc_type,
                            "ports": [port_obj],
                            "selector": {"app": app_label}
                        }
                    }
                    try:
                        v1.create_namespaced_service("devops-nexus-prod", svc_manifest)
                        logger.info(f"Auto-created missing K8s Service '{svc_name}' in devops-nexus-prod.")
                    except Exception as s_err:
                        logger.warning(f"Service creation error for '{svc_name}': {str(s_err)}")
                else:
                    logger.info(f"K8s Service '{svc_name}' verified.")
        except Exception as e:
            logger.warning(f"Microservice K8s services reconciliation warning: {str(e)}")

platform_initializer = PlatformInitializer()
