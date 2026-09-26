# --- Phase 7 Test Suite: ECR, Helm, ArgoCD, and GitOps Control Plane ---
import os
import yaml
import pytest
from unittest.mock import MagicMock, patch

from app.agent.verification_engine import VerificationEngine
from app.agent.gitops.ownership import GitOpsOwnershipResolver
from app.agent.gitops.change_engine import GitChangeEngine
from app.agent.target_resolver import TargetResolver
from app.clients.argocd import ArgoCDClient

SERVICES = ["auth", "users", "products", "orders", "payment", "notification", "gateway", "frontend"]
REPO_URL = "https://github.com/Manikandan23005/Deployment-Management-Troubleshooting-Platform.git"

class TestPhase7ECRArchitecture:
    """Validates ECR repository strategy, naming standards, and image references."""

    def test_ecr_naming_and_repo_configuration(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        tf_ecr_path = os.path.join(repo_root, "terraform/modules/ecr/main.tf")
        tf_var_path = os.path.join(repo_root, "terraform/modules/ecr/variables.tf")
        assert os.path.exists(tf_ecr_path), f"ECR Terraform module main.tf must exist at {tf_ecr_path}"
        assert os.path.exists(tf_var_path), f"ECR Terraform module variables.tf must exist at {tf_var_path}"
        with open(tf_ecr_path, "r") as f:
            content = f.read()
        assert "aws_ecr_repository" in content
        assert "scan_on_push" in content
        assert "image_tag_mutability" in content
        with open(tf_var_path, "r") as f:
            var_content = f.read()
        assert "image_tag_mutability" in var_content

    def test_helm_values_contain_immutable_ecr_tags(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        for svc in SERVICES:
            val_path = os.path.join(repo_root, f"helm/{svc}/values-prod.yaml")
            assert os.path.exists(val_path), f"values-prod.yaml for {svc} must exist"
            with open(val_path, "r") as f:
                values = yaml.safe_load(f)
            
            img = values.get("image", {})
            repo = img.get("repository", "")
            tag = img.get("tag", "")
            
            assert "605294565283.dkr.ecr.ap-south-1.amazonaws.com/devops-nexus/" in repo
            assert tag == "1.0.0", f"Service {svc} should use immutable release tag '1.0.0'"
            assert img.get("pullPolicy") in ["IfNotPresent", "Always"]


class TestPhase7HelmArchitecture:
    """Validates Helm charts structure, resource sizing, and probes."""

    def test_helm_resource_requests_and_limits_bounded(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        for svc in SERVICES:
            val_path = os.path.join(repo_root, f"helm/{svc}/values-prod.yaml")
            with open(val_path, "r") as f:
                values = yaml.safe_load(f)
            
            resources = values.get("resources", {})
            reqs = resources.get("requests", {})
            limits = resources.get("limits", {})
            
            assert reqs.get("cpu"), f"{svc} must define CPU requests"
            assert reqs.get("memory"), f"{svc} must define memory requests"
            assert limits.get("cpu"), f"{svc} must define CPU limits"
            assert limits.get("memory"), f"{svc} must define memory limits"

    def test_helm_chart_metadata_and_templates_exist(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        for svc in SERVICES:
            chart_path = os.path.join(repo_root, f"helm/{svc}/Chart.yaml")
            assert os.path.exists(chart_path)
            with open(chart_path, "r") as f:
                chart = yaml.safe_load(f)
            assert chart.get("name") == svc
            assert chart.get("apiVersion") in ["v1", "v2"]


class TestPhase7ArgoCDConfiguration:
    """Validates ArgoCD GitOps Application manifests and sync policies."""

    def test_argocd_prod_application_manifests(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        for svc in SERVICES:
            app_manifest = os.path.join(repo_root, f"gitops/argocd/prod/{svc}-app.yaml")
            assert os.path.exists(app_manifest), f"ArgoCD manifest {svc}-app.yaml must exist"
            with open(app_manifest, "r") as f:
                app_def = yaml.safe_load(f)
            
            assert app_def.get("apiVersion") == "argoproj.io/v1alpha1"
            assert app_def.get("kind") == "Application"
            spec = app_def.get("spec", {})
            assert spec.get("source", {}).get("repoURL") == REPO_URL
            assert spec.get("source", {}).get("path") == f"helm/{svc}"
            assert spec.get("destination", {}).get("namespace") == "devops-nexus-prod"
            sync_policy = spec.get("syncPolicy", {})
            assert sync_policy.get("automated", {}).get("selfHeal") is True

    def test_argocd_client_fail_safe_discovery(self):
        client = ArgoCDClient()
        assert client.default_server is not None
        assert hasattr(client, "list_applications")
        assert hasattr(client, "sync_application")
        assert hasattr(client, "refresh_application")


class TestPhase7GitOpsOwnershipAndControlPlane:
    """Validates that Git remains single source of truth and mutations are governed."""

    def test_gitops_ownership_resolution(self):
        resolver = GitOpsOwnershipResolver()
        for svc in SERVICES:
            ownership = resolver.resolve_ownership("devops-nexus-prod", f"{svc}-service")
            assert ownership.is_gitops is True, f"{svc}-service must be GitOps-owned"
            assert ownership.argocd_app_name == f"{svc}-prod"
            assert ownership.target_values_file is not None

    def test_agent_target_resolver_routes_gitops_workload_to_git(self):
        resolver = TargetResolver()
        target = resolver.resolve_target("scale auth-service in devops-nexus-prod to 3 replicas")
        assert target["application"] == "auth-service"
        assert target["namespace"] == "devops-nexus-prod"


class TestPhase7VerificationEngineAndFailureHandling:
    """Validates deterministic state verification, drift detection, and failure reporting."""

    def test_verification_engine_success_when_all_layers_match(self):
        engine = VerificationEngine()
        before_snap = {
            "git_desired_replicas": 1,
            "argocd_sync": "Synced",
            "argocd_health": "Healthy",
            "ready_pods": 1,
            "running_pods": 1
        }
        
        with patch.object(engine, "capture_state_snapshot") as mock_snap:
            mock_snap.return_value = {
                "git_desired_replicas": 3,
                "argocd_sync": "Synced",
                "argocd_health": "Healthy",
                "ready_pods": 3,
                "running_pods": 3,
                "deployment_ready_replicas": 3,
                "total_pods": 3
            }
            
            res = engine.verify_action_execution(
                target_resource="auth-service",
                action_type="scale_deployment",
                before_snapshot=before_snap,
                namespace="devops-nexus-prod",
                expected_params={"replicas": 3}
            )
            
            assert res["verified"] is True
            assert res["git_verified"] is True
            assert res["k8s_verified"] is True
            assert res["argocd_verified"] is True
            assert "VERIFIED_SUCCESS" in res["verification_summary"]

    def test_verification_engine_fails_on_state_mismatch_or_degraded(self):
        engine = VerificationEngine()
        before_snap = {
            "git_desired_replicas": 1,
            "argocd_sync": "Synced",
            "argocd_health": "Healthy",
            "ready_pods": 1,
            "running_pods": 1
        }
        
        # Test case: ArgoCD is OutOfSync / Degraded (e.g. invalid image tag failure)
        with patch.object(engine, "capture_state_snapshot") as mock_snap:
            mock_snap.return_value = {
                "git_desired_replicas": 1,
                "argocd_sync": "OutOfSync",
                "argocd_health": "Degraded",
                "ready_pods": 0,
                "running_pods": 0,
                "deployment_ready_replicas": 0,
                "total_pods": 1
            }
            
            res = engine.verify_action_execution(
                target_resource="auth-service",
                action_type="scale_deployment",
                before_snapshot=before_snap,
                namespace="devops-nexus-prod",
                expected_params={"replicas": 2}
            )
            
            assert res["verified"] is False
            assert "VERIFICATION_FAILED" in res["verification_summary"]

    def test_verification_engine_no_false_positive_on_image_pull_failure(self):
        engine = VerificationEngine()
        before_snap = {"running_pods": 1, "ready_pods": 1}
        
        with patch.object(engine, "capture_state_snapshot") as mock_snap:
            mock_snap.return_value = {
                "git_desired_replicas": 1,
                "argocd_sync": "Synced",
                "argocd_health": "Degraded",
                "ready_pods": 0,
                "running_pods": 0,
                "deployment_ready_replicas": 0,
                "total_pods": 1
            }
            
            res = engine.verify_action_execution(
                target_resource="payment-service",
                action_type="restart_deployment",
                before_snapshot=before_snap,
                namespace="devops-nexus-prod"
            )
            
            assert res["verified"] is False
            assert "VERIFICATION_FAILED" in res["verification_summary"]
