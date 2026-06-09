"""Phase D: ptz_controller template (Python + Node)."""
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


TELEMETRY_AP = "hosts/Server/DeviceIpint.54/TelemetryControl.0"


class PtzControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _request(self, language="python", allow_mutation=True, **params):
        base = {"telemetry_ap": TELEMETRY_AP}
        base.update(params)
        return self.module.GenerationRequest(
            template="ptz_controller", params=base, language=language, allow_mutation=allow_mutation
        )

    def test_catalog_entry(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("ptz_controller", entries)
        entry = entries["ptz_controller"]
        self.assertIn("python", entry["languages"])
        self.assertIn("node", entry["languages"])
        self.assertIn("telemetry_ap", entry["required_params"])
        self.assertIn("AXXON_HOST", entry["required_env"])

    def test_refuses_without_allow_mutation(self) -> None:
        result = self.gen.generate(self._request(allow_mutation=False))
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "refused_mutation")

    def test_python_returns_bundle(self) -> None:
        result = self.gen.generate(self._request())
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("main.py", result.files)
        self.assertIn("README.md", result.files)
        self.assertIn("requirements.txt", result.files)

    def test_node_returns_bundle(self) -> None:
        result = self.gen.generate(self._request(language="node"))
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)
        self.assertIn("package.json", result.files)

    def test_python_bakes_ap_and_caps(self) -> None:
        result = self.gen.generate(self._request(pan="0.1", tilt="0.0", hold_ms="500"))
        body = result.files["main.py"]
        self.assertIn(f'TELEMETRY_AP = "{TELEMETRY_AP}"', body)
        self.assertIn("PAN = 0.1", body)
        self.assertIn("HOLD_MS = 500", body)

    def test_python_cap_exceeded(self) -> None:
        result = self.gen.generate(self._request(pan="5.0"))  # beyond [-1,1] bound
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "cap_exceeded")

    def test_template_does_position_rollback(self) -> None:
        body = self.gen.generate(self._request()).files["main.py"]
        # the generated controller must read start position, move, then restore it
        self.assertIn("GetPositionInformation", body)
        self.assertIn("AbsoluteMove", body)
        self.assertIn("ReleaseSessionId", body)

    def test_no_embedded_secret(self) -> None:
        body = self.gen.generate(self._request()).files["main.py"]
        self.assertIn("os.environ", body)
        self.assertNotIn("hunter2", body)


if __name__ == "__main__":
    unittest.main()
