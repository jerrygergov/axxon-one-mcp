"""Keep the committed reference plugins in customer-templates/ lint-clean."""
from __future__ import annotations

from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
