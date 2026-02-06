import subprocess
import os
import json
from acontext_logger import log_activity

class GitManager:
    """
    ARKADY Git Collaborator v1.
    Handles branch management, conventional commits, and safety checks.
    """
    def __init__(self, repo_path: str = "D:\\DMarket-Telegram-Bot-main"):
        self.repo_path = repo_path

    def _run_git(self, args: list) -> str:
        result = subprocess.run(
            ["git", "-C", self.repo_path] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()

    def ensure_clean_state(self):
        status = self._run_git(["status", "--porcelain"])
        if status:
            log_activity("CODER", "GIT_CHECK", "Repository is dirty", "ERROR")
            raise Exception("Repository has uncommitted changes. Clean it first.")
        log_activity("CODER", "GIT_CHECK", "Repository is clean", "SUCCESS")
        return True

    def create_feature_branch(self, name: str):
        branch_name = f"arkady/feat-{name}"
        self._run_git(["checkout", "-b", branch_name])
        log_activity("ARCHITECT", "GIT_BRANCH", f"Created branch {branch_name}", "SUCCESS")
        return branch_name

    def commit_changes(self, message: str):
        # Safety check: secrets and syntax should be checked by pre-commit or here
        self._run_git(["add", "."])
        self._run_git(["commit", "-m", message])
        log_activity("CODER", "GIT_COMMIT", f"Committed: {message}", "SUCCESS")

    def push_branch(self):
        branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        self._run_git(["push", "origin", branch])
        log_activity("CODER", "GIT_PUSH", f"Pushed branch {branch}", "SUCCESS")
