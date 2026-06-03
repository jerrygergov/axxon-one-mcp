"""Phase 6A increment 5 tests: ml_detector_bridge template (Python + Node)."""
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


class MlDetectorBridgeTests(unittest.TestCase):
    """AC1-AC9."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _request(self, language: str = "python", allow_mutation: bool = True, **params):
        base = {
            "access_point": "hosts/Server/AppDataDetector.1/EventSupplier",
            "results_path": "/tmp/ml_results.json",
        }
        base.update(params)
        return self.module.GenerationRequest(
            template="ml_detector_bridge",
            params=base,
            language=language,
            allow_mutation=allow_mutation,
        )

    def test_catalog_entry(self) -> None:
        """AC1: ml_detector_bridge is in the catalog with python+node and required params."""
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("ml_detector_bridge", entries)
        entry = entries["ml_detector_bridge"]
        self.assertIn("python", entry["languages"])
        self.assertIn("node", entry["languages"])
        self.assertIn("access_point", entry["required_params"])
        self.assertIn("results_path", entry["required_params"])
        self.assertIn("AXXON_HOST", entry["required_env"])

    def test_python_returns_bundle(self) -> None:
        """AC2: python generation returns main.py, README, requirements."""
        result = self.gen.generate(self._request())
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("main.py", result.files)
        self.assertIn("README.md", result.files)
        self.assertIn("requirements.txt", result.files)

    def test_refuses_without_allow_mutation(self) -> None:
        """AC3: raising events is mutating, so generation refuses without allow_mutation."""
        result = self.gen.generate(self._request(allow_mutation=False))
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "refused_mutation")

    def test_python_bakes_constants(self) -> None:
        """AC4: main.py bakes ACCESS_POINT, RESULTS_PATH, COUNT_CAP, DURATION_SECONDS."""
        result = self.gen.generate(self._request(count="50", duration="20"))
        self.assertIsInstance(result, self.module.GeneratedBundle)
        body = result.files["main.py"]
        self.assertIn("ACCESS_POINT = ", body)
        self.assertIn('RESULTS_PATH = "/tmp/ml_results.json"', body)
        self.assertIn("COUNT_CAP = 50", body)
        self.assertIn("DURATION_SECONDS = 20", body)

    def test_python_cap_exceeded(self) -> None:
        """AC4: count over the module cap refuses with cap_exceeded."""
        result = self.gen.generate(self._request(count="100000"))
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "cap_exceeded")

    def test_python_env_results_method(self) -> None:
        """AC5: main.py uses os.environ, reads RESULTS_PATH, references RaiseOccasionalEvent."""
        body = self.gen.generate(self._request()).files["main.py"]
        self.assertIn("os.environ", body)
        self.assertNotIn("hunter2", body)
        self.assertIn("RESULTS_PATH", body)
        self.assertIn("RaiseOccasionalEvent", body)

    def test_node_returns_bundle(self) -> None:
        """AC6: node generation returns src/index.ts, README, package.json."""
        result = self.gen.generate(self._request(language="node"))
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)
        self.assertIn("package.json", result.files)

    def test_node_bakes_env_results_method(self) -> None:
        """AC6: src/index.ts bakes constants, reads process.env + RESULTS_PATH, references the method."""
        ts = self.gen.generate(self._request(language="node", count="50", duration="20")).files["src/index.ts"]
        self.assertIn("COUNT_CAP = 50", ts)
        self.assertIn("DURATION_SECONDS = 20", ts)
        self.assertIn("process.env", ts)
        self.assertIn("RESULTS_PATH", ts)
        self.assertIn("RaiseOccasionalEvent", ts)

    def test_verifier_passes_python(self) -> None:
        """AC7: generated python bundle passes the static verifier."""
        bundle = self.gen.generate(self._request())
        result = self.module.Verifier().verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_verifier_passes_node(self) -> None:
        """AC7: generated node bundle passes the static verifier."""
        bundle = self.gen.generate(self._request(language="node"))
        result = self.module.Verifier().verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))


if __name__ == "__main__":
    unittest.main()
