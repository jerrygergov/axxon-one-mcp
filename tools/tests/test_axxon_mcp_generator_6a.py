"""Phase 6A tests: Node/TypeScript renderer seam and extended Verifier."""
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
    (corpus / "api_methods.json").write_text(
        json.dumps(
            {
                "methods": [
                    {
                        "fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits",
                        "package": "axxonsoft.bl.config",
                        "service": "ConfigurationService",
                        "method": "ListUnits",
                        "request": "ListUnitsRequest",
                        "response": "ListUnitsResponse",
                        "streaming": "none",
                        "safety_class": "safe-read",
                        "live_status": "tested-pass",
                        "proto": "axxonsoft/bl/config/ConfigurationService.proto",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (corpus / "http_endpoints.json").write_text(
        json.dumps({"endpoints": []}), encoding="utf-8"
    )
    (corpus / "safety_policies.json").write_text(json.dumps({"classes": {}}), encoding="utf-8")
    (corpus / "known_behaviors.json").write_text(json.dumps({}), encoding="utf-8")
    (corpus / "fixtures.json").write_text(json.dumps({}), encoding="utf-8")
    (corpus / "task_recipes.json").write_text(json.dumps({"recipes": []}), encoding="utf-8")
    return corpus


def load_generator(corpus: Path):
    module = importlib.import_module("axxon_mcp_generator")
    importlib.reload(module)
    return module, module.Generator(corpus_dir=corpus)


class NodeRendererTests(unittest.TestCase):
    """AC1-AC4, AC8, AC10."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_generation_request_defaults_language_python(self) -> None:
        """AC1: language defaults to 'python'."""
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
        )
        self.assertEqual(req.language, "python")

    def test_event_consumer_node_returns_bundle(self) -> None:
        """AC2: node language returns GeneratedBundle with src/index.ts, README.md, package.json."""
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)
        self.assertIn("README.md", result.files)
        self.assertIn("package.json", result.files)

    def test_event_consumer_node_bakes_in_caps(self) -> None:
        """AC3: src/index.ts contains DURATION_SECONDS and COUNT_CAP baked from params."""
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier", "duration": "20", "count": "200"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("DURATION_SECONDS = 20", ts)
        self.assertIn("COUNT_CAP = 200", ts)

    def test_event_consumer_node_uses_process_env(self) -> None:
        """AC4: src/index.ts reads credentials from process.env, not literals."""
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("process.env", ts)
        # No password literal
        self.assertNotIn("hunter2", ts)
        self.assertNotIn("password = '", ts)

    def test_unsupported_language_returns_refusal(self) -> None:
        """AC8: unsupported language for a template returns GenerationRefusal."""
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="rust",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "unsupported_language")

    def test_list_templates_includes_languages_for_event_consumer(self) -> None:
        """AC10: list_templates returns languages field for event_consumer."""
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("event_consumer", entries)
        ec = entries["event_consumer"]
        self.assertIn("languages", ec)
        self.assertIn("python", ec["languages"])
        self.assertIn("node", ec["languages"])

    def test_list_templates_python_only_templates_have_languages(self) -> None:
        """Templates without TS support still have a languages field listing python only."""
        entries = {t["name"]: t for t in self.gen.list_templates()}
        for name, entry in entries.items():
            self.assertIn("languages", entry, f"template {name!r} missing languages field")
            self.assertIn("python", entry["languages"], f"template {name!r} missing python in languages")

    def test_event_consumer_python_unchanged(self) -> None:
        """Existing Python path is not broken by the language field."""
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="python",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("main.py", result.files)
        self.assertNotIn("src/index.ts", result.files)


class TypeScriptVerifierTests(unittest.TestCase):
    """AC5-AC7."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, _ = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _clean_ts_bundle(self) -> dict[str, str]:
        return {
            "src/index.ts": (
                "import * as grpc from '@grpc/grpc-js';\n"
                "const DURATION_SECONDS = 30;\n"
                "const COUNT_CAP = 500;\n"
                "const host = process.env.AXXON_HOST!;\n"
                "const password = process.env.AXXON_PASSWORD!;\n"
            ),
            "README.md": "# Test\n",
            "package.json": '{"name": "test", "version": "1.0.0"}\n',
        }

    def test_verifier_accepts_clean_ts_bundle(self) -> None:
        """AC5: clean TS bundle passes verification."""
        verifier = self.module.Verifier()
        result = verifier.verify_bundle(self._clean_ts_bundle())
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_verifier_rejects_ts_embedded_secret(self) -> None:
        """AC6: TS bundle with embedded password literal is rejected."""
        verifier = self.module.Verifier()
        bundle = self._clean_ts_bundle()
        bundle["src/index.ts"] = "const password = 'hunter2';\n"
        result = verifier.verify_bundle(bundle)
        self.assertFalse(result.ok)
        self.assertTrue(any("secret_match" in e for e in result.errors))

    def test_verifier_rejects_ts_child_process(self) -> None:
        """AC7: TS bundle importing child_process is rejected."""
        verifier = self.module.Verifier()
        bundle = self._clean_ts_bundle()
        bundle["src/index.ts"] = "import { exec } from 'child_process';\nconst x = 1;\n"
        result = verifier.verify_bundle(bundle)
        self.assertFalse(result.ok)
        self.assertTrue(any("disallowed_import" in e for e in result.errors))

    def test_verifier_rejects_ts_eval(self) -> None:
        """TS bundle calling eval() is rejected."""
        verifier = self.module.Verifier()
        bundle = self._clean_ts_bundle()
        bundle["src/index.ts"] = "eval('dangerous code');\n"
        result = verifier.verify_bundle(bundle)
        self.assertFalse(result.ok)
        self.assertTrue(any("disallowed_import" in e for e in result.errors))

    def test_verifier_ts_requires_package_json(self) -> None:
        """TS bundle missing package.json fails required-files check."""
        verifier = self.module.Verifier()
        bundle = self._clean_ts_bundle()
        del bundle["package.json"]
        result = verifier.verify_bundle(bundle)
        self.assertFalse(result.ok)
        self.assertTrue(any("missing_file" in e for e in result.errors))

    def test_verifier_ts_requires_index_ts(self) -> None:
        """TS bundle missing src/index.ts fails required-files check."""
        verifier = self.module.Verifier()
        bundle = self._clean_ts_bundle()
        del bundle["src/index.ts"]
        result = verifier.verify_bundle(bundle)
        self.assertFalse(result.ok)
        self.assertTrue(any("missing_file" in e for e in result.errors))

    def test_verifier_generated_ts_bundle_is_clean(self) -> None:
        """Full round-trip: generate node bundle then verify it passes."""
        _, gen = load_generator(self.corpus)
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        bundle = gen.generate(req)
        self.assertIsInstance(bundle, self.module.GeneratedBundle)
        verifier = self.module.Verifier()
        result = verifier.verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))


if __name__ == "__main__":
    unittest.main()
