"""Phase 6A increment 6 tests: dashboard_backend template (Python + Node)."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


def make_corpus(root: Path) -> Path:
    corpus = root / "mcp-corpus"
    corpus.mkdir()
    (corpus / "api_methods.json").write_text(json.dumps({"methods": []}), encoding="utf-8")
    (corpus / "http_endpoints.json").write_text(json.dumps({"endpoints": []}), encoding="utf-8")
    (corpus / "safety_policies.json").write_text(json.dumps({"classes": {}}), encoding="utf-8")
    (corpus / "known_behaviors.json").write_text(json.dumps({}), encoding="utf-8")
    (corpus / "fixtures.json").write_text(json.dumps({}), encoding="utf-8")
    (corpus / "task_recipes.json").write_text(json.dumps({"recipes": []}), encoding="utf-8")
    return corpus


def load_generator(corpus: Path):
    module = importlib.import_module("axxon_mcp_generator")
    importlib.reload(module)
    return module, module.Generator(corpus_dir=corpus)


SOURCES = ("ListCameras", "GetActiveAlerts", "ReadEvents")


class DashboardBackendTests(unittest.TestCase):
    """AC1-AC8."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _request(self, language: str = "python", **params):
        base = {"output_path": "/tmp/dashboard.json"}
        base.update(params)
        return self.module.GenerationRequest(
            template="dashboard_backend", params=base, language=language
        )

    def test_catalog_entry(self) -> None:
        """AC1: dashboard_backend is in the catalog with python+node and output_path param."""
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("dashboard_backend", entries)
        entry = entries["dashboard_backend"]
        self.assertIn("python", entry["languages"])
        self.assertIn("node", entry["languages"])
        self.assertIn("output_path", entry["required_params"])
        self.assertIn("AXXON_HOST", entry["required_env"])

    def test_python_returns_bundle(self) -> None:
        """AC2: python generation returns main.py, README, requirements with no mutation gate."""
        result = self.gen.generate(self._request())
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("main.py", result.files)
        self.assertIn("README.md", result.files)
        self.assertIn("requirements.txt", result.files)

    def test_python_bakes_constants(self) -> None:
        """AC3: main.py bakes OUTPUT_PATH and BYTE_CAP from params."""
        result = self.gen.generate(self._request())
        self.assertIsInstance(result, self.module.GeneratedBundle)
        body = result.files["main.py"]
        self.assertIn('OUTPUT_PATH = "/tmp/dashboard.json"', body)
        self.assertIn("BYTE_CAP = ", body)

    def test_python_env_output_sources(self) -> None:
        """AC4: main.py uses os.environ, writes OUTPUT_PATH, references all three sources."""
        body = self.gen.generate(self._request()).files["main.py"]
        self.assertIn("os.environ", body)
        self.assertNotIn("hunter2", body)
        self.assertIn("OUTPUT_PATH", body)
        for name in SOURCES:
            self.assertIn(name, body)

    def test_node_returns_bundle(self) -> None:
        """AC5: node generation returns src/index.ts, README, package.json."""
        result = self.gen.generate(self._request(language="node"))
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)
        self.assertIn("package.json", result.files)

    def test_node_bakes_env_sources(self) -> None:
        """AC5: src/index.ts bakes constants, reads process.env, references the three sources."""
        ts = self.gen.generate(self._request(language="node")).files["src/index.ts"]
        self.assertIn("BYTE_CAP = ", ts)
        self.assertIn("process.env", ts)
        self.assertIn("OUTPUT_PATH", ts)
        for name in SOURCES:
            self.assertIn(name, ts)

    def test_verifier_passes_python(self) -> None:
        """AC6: generated python bundle passes the static verifier."""
        bundle = self.gen.generate(self._request())
        result = self.module.Verifier().verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_verifier_passes_node(self) -> None:
        """AC6: generated node bundle passes the static verifier."""
        bundle = self.gen.generate(self._request(language="node"))
        result = self.module.Verifier().verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))


if __name__ == "__main__":
    unittest.main()
