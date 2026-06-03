"""Phase 6A increment 7 tests: plugin_scaffold template (Python + Node)."""
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


class PluginScaffoldTests(unittest.TestCase):
    """AC1-AC9."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _request(self, language: str = "python", **params):
        base = {"name": "acme-bridge"}
        base.update(params)
        return self.module.GenerationRequest(
            template="plugin_scaffold", params=base, language=language
        )

    def test_catalog_entry(self) -> None:
        """AC1: plugin_scaffold is in the catalog with python+node and name param."""
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("plugin_scaffold", entries)
        entry = entries["plugin_scaffold"]
        self.assertIn("python", entry["languages"])
        self.assertIn("node", entry["languages"])
        self.assertIn("name", entry["required_params"])
        self.assertIn("AXXON_HOST", entry["required_env"])

    def test_python_file_set(self) -> None:
        """AC2: python scaffold emits entrypoint, README, requirements, env example, test, CI, LICENSE."""
        result = self.gen.generate(self._request())
        self.assertIsInstance(result, self.module.GeneratedBundle)
        files = result.files
        self.assertIn("main.py", files)
        self.assertIn("README.md", files)
        self.assertIn("requirements.txt", files)
        self.assertIn(".env.example", files)
        self.assertTrue(any(n.startswith("test") and n.endswith(".py") for n in files), msg=str(list(files)))
        self.assertTrue(any(n.endswith((".yml", ".yaml")) for n in files), msg=str(list(files)))
        self.assertIn("LICENSE", files)

    def test_python_entrypoint(self) -> None:
        """AC3: entrypoint bakes NAME, reads os.environ, references ListCameras, has a retry helper."""
        body = self.gen.generate(self._request()).files["main.py"]
        self.assertIn("acme-bridge", body)
        self.assertIn("os.environ", body)
        self.assertNotIn("hunter2", body)
        self.assertIn("ListCameras", body)
        self.assertIn("retry", body.lower())

    def test_readme_and_env_example(self) -> None:
        """AC4: README has a Safety section; .env.example lists env names with no real values."""
        files = self.gen.generate(self._request()).files
        self.assertIn("Safety", files["README.md"])
        env_example = files[".env.example"]
        for name in ("AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"):
            self.assertIn(name, env_example)
        self.assertNotIn("root", env_example.lower())

    def test_verifier_passes_python(self) -> None:
        """AC5/AC7: generated python scaffold passes the static verifier."""
        bundle = self.gen.generate(self._request())
        result = self.module.Verifier().verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_node_file_set(self) -> None:
        """AC6: node scaffold emits TS entrypoint, package.json, README, env example, test, CI, LICENSE."""
        files = self.gen.generate(self._request(language="node")).files
        self.assertIn("src/index.ts", files)
        self.assertIn("package.json", files)
        self.assertIn("README.md", files)
        self.assertIn(".env.example", files)
        self.assertTrue(any(n.endswith(".test.ts") or (n.startswith("test") and n.endswith(".ts")) for n in files), msg=str(list(files)))
        self.assertTrue(any(n.endswith((".yml", ".yaml")) for n in files), msg=str(list(files)))
        self.assertIn("LICENSE", files)

    def test_node_entrypoint(self) -> None:
        """AC6: src/index.ts reads process.env, references ListCameras, has a retry helper."""
        ts = self.gen.generate(self._request(language="node")).files["src/index.ts"]
        self.assertIn("process.env", ts)
        self.assertIn("ListCameras", ts)
        self.assertIn("retry", ts.lower())

    def test_verifier_passes_node(self) -> None:
        """AC7: generated node scaffold passes the static verifier."""
        bundle = self.gen.generate(self._request(language="node"))
        result = self.module.Verifier().verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))


if __name__ == "__main__":
    unittest.main()
