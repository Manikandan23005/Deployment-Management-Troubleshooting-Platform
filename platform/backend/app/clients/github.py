# --- GitHub REST API Client ---
import httpx
from typing import List, Dict, Any, Optional
from app.core.logging import logger
from shared.exceptions import DevOpsNexusException

class GitHubClient:
    """Manages queries to the GitHub REST API with in-memory caching."""
    def __init__(self, token: Optional[str] = None):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if token:
            self.headers["Authorization"] = f"token {token}"
        self._cache: Dict[str, Any] = {}
        self._cache_exp: Dict[str, float] = {}

    def _get_from_cache(self, key: str) -> Optional[Any]:
        import time
        if key in self._cache and time.time() < self._cache_exp.get(key, 0):
            return self._cache[key]
        return None

    def _set_cache(self, key: str, val: Any, ttl: float = 60.0):
        import time
        self._cache[key] = val
        self._cache_exp[key] = time.time() + ttl

    def get_branches(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        cache_key = f"branches:{owner}:{repo}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        url = f"{self.base_url}/repos/{owner}/{repo}/branches"
        try:
            with httpx.Client(headers=self.headers, timeout=0.8) as client:
                response = client.get(url)
                if response.status_code != 200:
                    raise DevOpsNexusException(f"GitHub returned error {response.status_code}: {response.text}")
                data = response.json()
                self._set_cache(cache_key, data, 120.0)
                return data
        except Exception as e:
            logger.error(f"Failed to fetch GitHub branches: {str(e)}")
            raise DevOpsNexusException(f"GitHub connection failed: {str(e)}")

    def get_commits(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        cache_key = f"commits:{owner}:{repo}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        try:
            with httpx.Client(headers=self.headers, timeout=0.8) as client:
                response = client.get(url)
                if response.status_code != 200:
                    raise DevOpsNexusException(f"GitHub returned error {response.status_code}: {response.text}")
                data = response.json()
                self._set_cache(cache_key, data, 120.0)
                return data
        except Exception as e:
            logger.error(f"Failed to fetch GitHub commits: {str(e)}")
            raise DevOpsNexusException(f"GitHub connection failed: {str(e)}")

    def get_workflow_runs(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        cache_key = f"workflows:{owner}:{repo}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs"
        try:
            with httpx.Client(headers=self.headers, timeout=0.8) as client:
                response = client.get(url)
                if response.status_code != 200:
                    raise DevOpsNexusException(f"GitHub returned error {response.status_code}: {response.text}")
                data = response.json().get("workflow_runs", [])
                self._set_cache(cache_key, data, 120.0)
                return data
        except Exception as e:
            logger.error(f"Failed to fetch GitHub workflow runs: {str(e)}")
            raise DevOpsNexusException(f"GitHub connection failed: {str(e)}")

github_client = GitHubClient()
