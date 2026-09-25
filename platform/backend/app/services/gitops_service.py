# --- GitOps GitHub Management Service ---
from typing import List, Dict, Any
from app.clients.github import github_client
from shared.exceptions import DevOpsNexusException
from app.core.logging import logger

class GitOpsService:
    def get_workflows_status(self, owner: str = "Manikandan23005", repo: str = "Microservice-Deployment-Monitoring-Platform") -> List[Dict[str, Any]]:
        """Retrieves CI/CD workflow status logs from GitHub."""
        try:
            runs = github_client.get_workflow_runs(owner, repo)
            result = []
            for run in runs[:5]:
                result.append({
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "branch": run.get("head_branch"),
                    "event": run.get("event"),
                    "url": run.get("html_url")
                })
            return result
        except DevOpsNexusException:
            return []

    def get_repository_details(self, owner: str = "Manikandan23005", repo: str = "Microservice-Deployment-Monitoring-Platform") -> Dict[str, Any]:
        """Gathers latest commits list and branches catalog."""
        try:
            commits = github_client.get_commits(owner, repo)
            branches = github_client.get_branches(owner, repo)
            
            parsed_commits = []
            for c in commits[:5]:
                parsed_commits.append({
                    "sha": c.get("sha")[:7] if c.get("sha") else "unknown",
                    "author": c.get("commit", {}).get("author", {}).get("name", "unknown"),
                    "message": c.get("commit", {}).get("message", "").split("\n")[0]
                })
                
            return {
                "owner": owner,
                "repository": repo,
                "branches": [b.get("name") for b in branches] if branches else [],
                "latest_commits": parsed_commits
            }
        except DevOpsNexusException:
            return {
                "owner": owner,
                "repository": repo,
                "branches": [],
                "latest_commits": []
            }

gitops_service = GitOpsService()
