"""Release documentation and root CI must describe one secure, reproducible contract."""
from __future__ import annotations

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
CORPUS_README = REPO_ROOT / "docs/api-audit/mcp-corpus/README.md"
WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"


class ReleaseDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = README.read_text(encoding="utf-8")
        cls.corpus_readme = CORPUS_README.read_text(encoding="utf-8")
        cls.normalized_readme = re.sub(r"\s+", " ", cls.readme.lower())
        cls.normalized_corpus_readme = re.sub(
            r"\s+", " ", cls.corpus_readme.lower()
        )

    def test_readme_describes_secure_startup_profiles(self) -> None:
        lower = self.normalized_readme
        self.assertIn("exactly seven knowledge tools", lower)
        self.assertIn("knowledge-only profile", lower)
        self.assertIn("no credentials", lower)
        self.assertIn("--enable-live", self.readme)
        self.assertIn("--read-only", self.readme)
        self.assertIn("--enable-all", self.readme)
        self.assertIn("registration only", lower)
        self.assertIn("does not authorize mutations", lower)
        self.assertIn("authoritative", lower)
        self.assertIn("mutation-disabled", lower)

    def test_readme_never_claims_broad_or_approved_defaults(self) -> None:
        lower = self.normalized_readme
        forbidden = (
            "all on by default",
            "no flags enables every group",
            "running with no flags enables everything",
            "running with no capability flags enables all groups",
            "mutation approvals are enabled by default",
        )
        for phrase in forbidden:
            self.assertNotIn(phrase, lower)

    def test_readme_documents_external_mutation_authorization(self) -> None:
        lower = self.normalized_readme
        self.assertIn("explicit capability group", lower)
        self.assertIn("axxON_<module>_approve=1".lower(), lower)
        self.assertIn("exact value `1`", lower)
        self.assertIn("per-call", lower)
        self.assertIn("plan", lower)
        self.assertIn("confirmation", lower)

    def test_readme_documents_operator_review_then_apply(self) -> None:
        lower = self.normalized_readme
        self.assertIn(
            "plan → caller review and approval → explicit apply → verify → optional rollback",
            lower,
        )
        self.assertIn("never supplies its own confirmation", lower)
        self.assertNotIn("assistant supplies the confirmation token", lower)
        self.assertNotIn("run in a single `execute` call", lower)

    def test_readme_uses_python_312_commands_matching_release_checks(self) -> None:
        commands = (
            "python3.12 -m pip install -r tools/requirements-mcp.txt",
            "python3.12 tools/axxon_mcp_server.py --transport stdio",
            "python3.12 -m unittest discover -s tools/tests -v",
            "python3.12 tools/verify_mcp_startup.py",
            "python3.12 tools/axxon_corpus_restamp.py --check",
            "python3.12 tools/generate_coverage.py --check",
            "python3.12 -m unittest discover -s customer-templates/python-reference -p 'test*.py' -v",
            "npm --prefix customer-templates/node-reference ci",
            "npm --prefix customer-templates/node-reference run build",
            "npm --prefix customer-templates/node-reference test",
        )
        for command in commands:
            self.assertIn(command, self.readme)

    def test_customer_configuration_is_secure_and_least_privileged(self) -> None:
        self.assertRegex(self.readme, r'"AXXON_HTTP_URL": "https://[^"<]+"')
        self.assertIn('"AXXON_USERNAME": "axxon-mcp-reader"', self.readme)
        self.assertNotIn('"AXXON_USERNAME": "root"', self.readme)
        self.assertIn("trusted lab", self.readme.lower())

    def test_architecture_matches_per_group_clients(self) -> None:
        lower = self.normalized_readme
        self.assertIn("reuse the same client implementation class", lower)
        self.assertIn("separate client instances", lower)
        self.assertNotIn("one shared client", lower)
        self.assertNotIn("uses one process-wide singleton", lower)

    def test_corpus_maintenance_uses_check_only_commands_and_secure_posture(self) -> None:
        self.assertIn(
            "python3.12 tools/axxon_corpus_restamp.py --check", self.corpus_readme
        )
        self.assertIn(
            "python3.12 tools/generate_coverage.py --check", self.corpus_readme
        )
        lower = self.normalized_corpus_readme
        self.assertIn("exactly seven knowledge tools", lower)
        self.assertIn("--enable-all", self.corpus_readme)
        self.assertIn("registration only", lower)
        self.assertNotIn("running with no capability flags enables all groups", lower)


class RootWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_runs_for_push_and_pull_request(self) -> None:
        self.assertRegex(self.workflow, r'(?m)^"on":\s*$')
        self.assertRegex(self.workflow, r"(?m)^\s{2}push:\s*$")
        self.assertRegex(self.workflow, r"(?m)^\s{2}pull_request:\s*$")

    def test_workflow_has_python_312_and_node_20_jobs(self) -> None:
        self.assertRegex(self.workflow, r"(?m)^\s{2}python:\s*$")
        self.assertRegex(self.workflow, r"python-version:\s*[\"']?3\.12")
        self.assertRegex(self.workflow, r"(?m)^\s{2}node-reference:\s*$")
        self.assertRegex(self.workflow, r"node-version:\s*[\"']?20")

    def test_python_job_runs_complete_customer_release_checks(self) -> None:
        commands = (
            "python3.12 -m pip install -r tools/requirements-mcp.txt",
            "python3.12 -m pip check",
            "python3.12 -m unittest discover -s tools/tests -v",
            "python3.12 tools/verify_mcp_startup.py",
            "python3.12 tools/axxon_corpus_restamp.py --check",
            "python3.12 tools/generate_coverage.py --check",
            "python3.12 -m unittest discover -s customer-templates/python-reference -p 'test*.py' -v",
        )
        for command in commands:
            self.assertIn(f"run: {command}", self.workflow)

    def test_node_job_uses_locked_reference_commands(self) -> None:
        self.assertIn("cache-dependency-path: customer-templates/node-reference/package-lock.json", self.workflow)
        for command in ("npm ci", "npm run build", "npm test"):
            pattern = rf"(?ms)working-directory: customer-templates/node-reference\s+run: {re.escape(command)}"
            self.assertRegex(self.workflow, pattern)

    def test_workflow_has_no_customer_secrets_or_live_dependencies(self) -> None:
        lower = self.workflow.lower()
        for forbidden in ("secrets.", "axxon_host", "axxon_password", "proto_dir"):
            self.assertNotIn(forbidden, lower)


if __name__ == "__main__":
    unittest.main()
