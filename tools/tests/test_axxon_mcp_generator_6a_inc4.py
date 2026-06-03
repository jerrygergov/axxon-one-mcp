"""Phase 6A increment 4 tests: scheduled_exporter template (Python + Node)."""
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


class ScheduledExporterTests(unittest.TestCase):
    """AC1-AC9."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _request(self, language: str = "python", **params):
        base = {"camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"}
        base.update(params)
        return self.module.GenerationRequest(
            template="scheduled_exporter", params=base, language=language
        )

    def test_catalog_entry(self) -> None:
        """AC1: scheduled_exporter is in the catalog with python+node and camera_ap param."""
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("scheduled_exporter", entries)
        entry = entries["scheduled_exporter"]
        self.assertIn("python", entry["languages"])
        self.assertIn("node", entry["languages"])
        self.assertIn("camera_ap", entry["required_params"])
        self.assertIn("AXXON_HOST", entry["required_env"])

    def test_python_returns_bundle(self) -> None:
        """AC2: python generation returns main.py, README, requirements with no mutation gate."""
        result = self.gen.generate(self._request())
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("main.py", result.files)
        self.assertIn("README.md", result.files)
        self.assertIn("requirements.txt", result.files)

    def test_python_bakes_constants(self) -> None:
        """AC3: main.py bakes INTERVAL_SECONDS, MAX_RUNS, BYTE_CAP, CAMERA_AP from params."""
        result = self.gen.generate(self._request(interval="120", max_runs="5"))
        self.assertIsInstance(result, self.module.GeneratedBundle)
        body = result.files["main.py"]
        self.assertIn("INTERVAL_SECONDS = 120", body)
        self.assertIn("MAX_RUNS = 5", body)
        self.assertIn("BYTE_CAP =", body)
        self.assertIn("CAMERA_AP = ", body)

    def test_refuses_interval_too_small(self) -> None:
        """AC4: interval below the floor refuses with cap_exceeded."""
        result = self.gen.generate(self._request(interval="1"))
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "cap_exceeded")

    def test_refuses_max_runs_too_large(self) -> None:
        """AC4: max_runs over the cap refuses with cap_exceeded."""
        result = self.gen.generate(self._request(max_runs="100000"))
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "cap_exceeded")

    def test_python_env_and_method(self) -> None:
        """AC5: main.py uses os.environ and references ListSessions."""
        body = self.gen.generate(self._request()).files["main.py"]
        self.assertIn("os.environ", body)
        self.assertNotIn("hunter2", body)
        self.assertIn("ListSessions", body)

    def test_node_returns_bundle(self) -> None:
        """AC6: node generation returns src/index.ts, README, package.json."""
        result = self.gen.generate(self._request(language="node"))
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)
        self.assertIn("package.json", result.files)

    def test_node_bakes_env_method(self) -> None:
        """AC6: src/index.ts bakes constants, reads process.env, references ListSessions."""
        ts = self.gen.generate(self._request(language="node", interval="120", max_runs="5")).files["src/index.ts"]
        self.assertIn("INTERVAL_SECONDS = 120", ts)
        self.assertIn("MAX_RUNS = 5", ts)
        self.assertIn("process.env", ts)
        self.assertIn("ListSessions", ts)

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
