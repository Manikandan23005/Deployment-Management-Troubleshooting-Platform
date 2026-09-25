# --- Environment-Aware Kubernetes Client Factory ---
import os
import tempfile
import base64
import datetime
import threading
from typing import Dict, Any, Optional
import boto3
from botocore.signers import RequestSigner
from kubernetes import client, config
from app.services.cluster_registry import cluster_registry, ClusterProvider
from app.aws.credential_provider import aws_credential_provider
from app.aws.models import AWSAccount
from app.core.logging import logger

class KubernetesClientFactory:
    """Instantiates environment-aware Kubernetes API client instances.
    Dynamically routes between local/on-premise kubeconfig authentication and 
    Amazon EKS IAM bearer token authentication without static kubeconfig files."""

    def __init__(self):
        self._lock = threading.Lock()
        self._eks_client_cache: Dict[str, Dict[str, Any]] = {}
        self._ca_temp_files: Dict[str, str] = {}

    def generate_eks_token(
        self,
        cluster_name: str,
        account: AWSAccount,
        region: Optional[str] = None
    ) -> str:
        """Generates a standard Amazon EKS v1beta1 STS pre-signed bearer authentication token."""
        creds = aws_credential_provider.get_temporary_credentials(account)
        target_region = region or account.default_region or "ap-south-1"

        session = boto3.Session(
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
            aws_session_token=creds["aws_session_token"],
            region_name=target_region
        )
        sts_client = session.client("sts", region_name=target_region)
        
        service_id = sts_client.meta.service_model.service_id
        signer = RequestSigner(
            service_id,
            target_region,
            "sts",
            "v4",
            session.get_credentials(),
            session.events
        )

        params = {
            "method": "GET",
            "url": f"https://sts.{target_region}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
            "body": {},
            "headers": {"x-k8s-aws-id": cluster_name},
            "context": {}
        }

        presigned_url = signer.generate_presigned_url(
            params,
            region_name=target_region,
            expires_in=60,
            operation_name=""
        )

        # Base64 URL-safe encode without padding
        encoded_url = base64.urlsafe_b64encode(presigned_url.encode("utf-8")).decode("utf-8").rstrip("=")
        return f"k8s-aws-v1.{encoded_url}"

    def _write_ca_cert_file(self, cluster_id: str, ca_base64: str) -> str:
        """Writes base64 CA data to a secured temp file for Kubernetes client SSL verification."""
        if cluster_id in self._ca_temp_files and os.path.exists(self._ca_temp_files[cluster_id]):
            return self._ca_temp_files[cluster_id]

        ca_bytes = base64.b64decode(ca_base64)
        fd, path = tempfile.mkstemp(prefix=f"eks-ca-{cluster_id[:8]}-", suffix=".crt")
        with os.fdopen(fd, "wb") as f:
            f.write(ca_bytes)

        self._ca_temp_files[cluster_id] = path
        return path

    def get_clients(
        self,
        cluster_id: Optional[str] = None,
        scope: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Resolves and instantiates Kubernetes API clients (CoreV1, AppsV1, NetworkingV1)."""
        
        # 1. Resolve target cluster definition
        target_cid = cluster_id or (getattr(scope, "cluster_id", None) if scope else None)
        target_env = getattr(scope, "environment", None) if scope else None

        cluster = None
        if target_cid:
            cluster = cluster_registry.get_cluster(target_cid)
        if not cluster:
            from shared.exceptions import KubernetesClientException
            raise KubernetesClientException("No Kubernetes cluster configured.")

        cid = cluster.get("id", "default")
        provider = cluster.get("provider", ClusterProvider.MINIKUBE.value)
        auth_type = cluster.get("authentication_type", "Kubeconfig")

        is_eks = (provider == ClusterProvider.EKS.value or 
                  auth_type == "AWS_IAM_EKS" or 
                  target_env in ["AWS_EKS", "Amazon EKS"] or 
                  "eks" in cid.lower())

        if not is_eks:
            # On-Premise / Minikube: delegate to cluster_registry
            return cluster_registry.get_k8s_clients(cid)

        # 2. Amazon EKS Dynamic Authentication
        with self._lock:
            now = datetime.datetime.now(datetime.timezone.utc)
            if cid in self._eks_client_cache:
                cached_entry = self._eks_client_cache[cid]
                if cached_entry["expires_at"] > now + datetime.timedelta(minutes=2):
                    return cached_entry["clients"]

        # Resolve AWS Account
        from app.aws.account_registry import aws_account_registry
        aws_acc_id = cluster.get("aws_account_id")
        account = None
        if aws_acc_id:
            account = aws_account_registry.get_account(aws_acc_id)
        if not account:
            # Try finding by first registered account or fallback
            accounts = aws_account_registry.list_accounts()
            if accounts:
                account = accounts[0]

        if not account:
            logger.warning(f"No AWS Account registered for EKS cluster '{cid}'. Falling back to local cluster registry.")
            return cluster_registry.get_k8s_clients(cid)

        eks_cluster_name = cluster.get("eks_cluster_name") or cluster.get("name", "").replace("eks-", "")
        region = cluster.get("aws_region") or account.default_region or "ap-south-1"

        try:
            bearer_token = self.generate_eks_token(eks_cluster_name, account, region=region)
            
            k8s_conf = client.Configuration()
            k8s_conf.host = cluster.get("api_server", f"https://{eks_cluster_name}.{region}.eks.amazonaws.com")
            k8s_conf.api_key = {"authorization": f"Bearer {bearer_token}"}

            ca_data = cluster.get("ca_data")
            if ca_data:
                ca_path = self._write_ca_cert_file(cid, ca_data)
                k8s_conf.ssl_ca_cert = ca_path
                k8s_conf.verify_ssl = True
            else:
                k8s_conf.verify_ssl = False

            api_client = client.ApiClient(k8s_conf)
            clients = {
                "v1": client.CoreV1Api(api_client),
                "apps_v1": client.AppsV1Api(api_client),
                "networking_v1": client.NetworkingV1Api(api_client),
                "cluster": cluster,
                "environment": "AWS_EKS"
            }

            with self._lock:
                self._eks_client_cache[cid] = {
                    "clients": clients,
                    "expires_at": now + datetime.timedelta(minutes=10)
                }

            return clients

        except Exception as e:
            logger.error(f"Failed to generate dynamic EKS Kubernetes client for cluster '{cid}': {str(e)}")
            return cluster_registry.get_k8s_clients(cid)

k8s_client_factory = KubernetesClientFactory()
