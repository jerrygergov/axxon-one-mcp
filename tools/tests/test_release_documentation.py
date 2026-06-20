#!/usr/bin/env python3
"""Release documentation and CI contract tests."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))


class ReleaseDocumentationTests(unittest.TestCase):
    def test_readme_describes_secure_startup_profiles(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        for phrase in (
            "seven-tool knowledge-only",
            "--enable-live",
            "--read-only",
            "authoritatively disables mutation execution",
            "--enable-all",
            "does not authorize mutations",
            "exact value",
            "AXXON_*_APPROVE=1",
            "caller review",
            "apply_operator_plan",
            "verify_operator_plan",
            "rollback_operator_plan",
        ):
            self.assertIn(phrase, text)

        forbidden = (
            "all on by default",
            "running with no flags enables every group",
            "assistant supplies the confirmation token",
            "process-wide shared client",
            '"AXXON_USERNAME": "root"',
            '"AXXON_HTTP_URL": "http://',
        )
        for phrase in forbidden:
            self.assertNotIn(phrase, text)

    def test_readme_documents_runtime_connection_profile(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Do not put the Axxon host/IP", text)
        self.assertIn("Claude Desktop config or environment variables", text)
        self.assertIn("configure_axxon_connection", text)
        self.assertIn("host`, `grpc_port`, `http_port`, `username`, and `password", text)
        self.assertIn("process memory", text)
        self.assertIn("clear_axxon_connection", text)
        self.assertIn("password_present: true", text)
        self.assertIn("least-privilege", text)
        self.assertIn("HTTPS", text)
        self.assertIn("tls_cn", text)
        self.assertNotRegex(text, r'"AXXON_(HOST|HTTP_URL|HTTP_PORT|GRPC_PORT|USERNAME|PASSWORD|TLS_CN)"')

    def test_readme_describes_connect_helper_scope_truthfully(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        lower_text = text.lower()

        self.assertIn("server-backed groups expose connection helper tools", lower_text)
        self.assertIn("offline authoring exceptions", lower_text)
        for offline_group in ("generator", "partner", "translator"):
            self.assertIn(offline_group, text)
        self.assertIn("Operator planning is also transport-free", text)
        self.assertIn("requires the runtime connection profile", text)
        self.assertNotIn("Every group exposes a `*_connect_axxon_profile` tool", text)
        self.assertNotIn("the rest connect to the live server", text)

    def test_readme_contains_interpreter_qualified_release_commands(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for command in (
            "python3.12 -m pip install -r tools/requirements-mcp.txt",
            "python3.12 -m pip check",
            "python3.12 -m unittest discover -s tools/tests -v",
            "python3.12 tools/verify_mcp_startup.py",
            "python3.12 tools/axxon_corpus_restamp.py --check",
            "python3.12 tools/generate_coverage.py --check",
            "npm ci",
            "npm run build",
            "npm test",
        ):
            self.assertIn(command, text)

    def test_root_ci_contains_release_commands(self) -> None:
        workflow = REPO_ROOT / ".github/workflows/ci.yml"
        text = workflow.read_text(encoding="utf-8")

        self.assertIn('"on":', text)
        self.assertIn("push", text)
        self.assertIn("pull_request", text)
        self.assertIn('python-version: "3.12"', text)
        self.assertIn('node-version: "20"', text)
        for command in (
            "python3.12 -m pip install -r tools/requirements-mcp.txt",
            "python3.12 -m pip check",
            "python3.12 -m unittest discover -s tools/tests -v",
            "python3.12 tools/verify_mcp_startup.py",
            "python3.12 tools/axxon_corpus_restamp.py --check",
            "python3.12 tools/generate_coverage.py --check",
            'python3.12 -m unittest discover -s customer-templates/python-reference -p "test*.py" -v',
            "npm ci",
            "npm run build",
            "npm test",
        ):
            self.assertIn(command, text)

        self.assertNotRegex(text, re.compile(r"AXXON_(PASSWORD|HOST|USERNAME|CA|PROTO_DIR)"))

    def test_corpus_readme_documents_ci_checks_and_secure_posture(self) -> None:
        text = (REPO_ROOT / "docs/api-audit/mcp-corpus/README.md").read_text(encoding="utf-8")

        self.assertIn("python3.12 tools/axxon_corpus_restamp.py --check", text)
        self.assertIn("python3.12 tools/generate_coverage.py --check", text)
        self.assertIn("knowledge-only", text)
        self.assertIn("Tool registration never grants mutation approval", text)
        self.assertNotIn("Running with no capability flags enables all groups", text)


if __name__ == "__main__":
    unittest.main()
