"""Keep the committed reference plugins in customer-templates/ lint-clean."""
from __future__ import annotations

from pathlib import Path
import json
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_partner import PartnerKit


class CustomerTemplatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = PartnerKit()
        self.base = REPO_ROOT / "customer-templates"

    def test_reference_plugins_exist(self) -> None:
        """Both reference plugins are present."""
        self.assertTrue((self.base / "python-reference").is_dir())
        self.assertTrue((self.base / "node-reference").is_dir())

    def test_reference_plugins_lint_clean(self) -> None:
        """Every reference plugin lints clean (no secrets, env example, test, README safety)."""
        for child in sorted(self.base.iterdir()):
            if child.is_dir():
                result = self.kit.plugin_lint(child)
                self.assertTrue(result["ok"], msg=f"{child.name}: {result['findings']}")

    def test_reference_plugins_package(self) -> None:
        """Every reference plugin can be packaged (proves it is distributable)."""
        import tempfile

        for child in sorted(self.base.iterdir()):
            if child.is_dir():
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / f"{child.name}.zip"
                    result = self.kit.plugin_package(child, "zip", out)
                    self.assertEqual(result["status"], "ok", msg=str(result))
                    self.assertTrue(out.exists())

    def test_node_reference_has_locked_executable_contract(self) -> None:
        """The committed Node reference installs, compiles, tests, and starts deterministically."""
        node = self.base / "node-reference"
        self.assertTrue((node / "package-lock.json").is_file())
        package = json.loads((node / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((node / "package-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["packages"][""]["name"], package["name"])
        self.assertEqual(lock["packages"][""]["version"], package["version"])
        self.assertEqual(
            package["scripts"],
            {
                "build": "tsc -p tsconfig.json",
                "test": "npm run build --silent && node dist/test/smoke.test.js",
                "start": "node dist/src/index.js",
            },
        )
        tsconfig = json.loads((node / "tsconfig.json").read_text(encoding="utf-8"))
        self.assertEqual(tsconfig["compilerOptions"]["rootDir"], ".")
        self.assertEqual(tsconfig["compilerOptions"]["outDir"], "dist")
        self.assertEqual(tsconfig["include"], ["src/**/*.ts", "test/**/*.ts"])

    def test_node_reference_documents_and_runs_the_node_workflow(self) -> None:
        """The committed Node reference has Node-only setup docs and complete CI."""
        node = self.base / "node-reference"
        readme = (node / "README.md").read_text(encoding="utf-8")
        for command in ("npm ci", "npm run build", "npm test", "npm start"):
            self.assertIn(command, readme)
        self.assertNotIn("pip install", readme)
        self.assertNotIn("python main.py", readme)
        workflow = (node / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for command in ("npm ci", "npm run build", "npm test"):
            self.assertIn(f"run: {command}", workflow)

    def test_node_reference_does_not_log_password_material(self) -> None:
        """The committed entrypoint does not transform password material for logging."""
        ts = (self.base / "node-reference" / "src/index.ts").read_text(encoding="utf-8")
        self.assertNotIn("function redact", ts)
        self.assertNotIn("password=${", ts)
        self.assertNotRegex(ts, r"AXXON_PASSWORD[^\n]*\.(?:slice|substring|substr)\(")
        self.assertNotIn("throw lastErr", ts)


if __name__ == "__main__":
    unittest.main()
