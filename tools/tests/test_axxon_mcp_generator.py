from __future__ import annotations

import ast
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
                    {
                        "fqmn": "axxonsoft.bl.config.ConfigurationService.ChangeConfig",
                        "package": "axxonsoft.bl.config",
                        "service": "ConfigurationService",
                        "method": "ChangeConfig",
                        "request": "ChangeConfigRequest",
                        "response": "ChangeConfigResponse",
                        "streaming": "none",
                        "safety_class": "mutation",
                        "live_status": "tested-pass",
                        "proto": "axxonsoft/bl/config/ConfigurationService.proto",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (corpus / "http_endpoints.json").write_text(
        json.dumps(
            {
                "endpoints": [
                    {
                        "verb": "GET",
                        "path": "/product/version",
                        "auth_mode": "bearer",
                        "safety_class": "safe-read",
                        "live_status": "tested-pass",
                    },
                    {
                        "verb": "GET",
                        "path": "/never/tested",
                        "auth_mode": "bearer",
                        "safety_class": "safe-read",
                        "live_status": "not-verified",
                    },
                ]
            }
        ),
        encoding="utf-8",
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


class GeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_generator_lists_templates(self) -> None:
        names = [t["name"] for t in self.gen.list_templates()]
        self.assertEqual(
            sorted(names),
            sorted(
                [
                    "grpc_consumer",
                    "http_grpc_consumer",
                    "legacy_http_consumer",
                    "event_consumer",
                    "external_event_producer",
                    "export_job",
                ]
            ),
        )
        for entry in self.gen.list_templates():
            self.assertIn("summary", entry)
            self.assertIn("required_env", entry)

    def test_plan_grpc_consumer_safe_read(self) -> None:
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
        )
        result = self.gen.plan(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("main.py", result.files)

    def test_plan_grpc_consumer_refuses_mutation(self) -> None:
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ChangeConfig"},
        )
        result = self.gen.plan(req)
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "refused_mutation")
        self.assertIn("mutation", result.detail)

    def test_plan_legacy_http_refuses_unverified(self) -> None:
        req = self.module.GenerationRequest(template="legacy_http_consumer", params={"path": "/never/tested"})
        result = self.gen.plan(req)
        self.assertIsInstance(result, self.module.GenerationRefusal)
        self.assertEqual(result.reason, "unverified_endpoint")

    def test_generate_event_consumer_emits_caps(self) -> None:
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AppDataDetector.27/EventSupplier"},
        )
        bundle = self.gen.generate(req)
        self.assertIsInstance(bundle, self.module.GeneratedBundle)
        body = bundle.files["main.py"]
        self.assertIn("DURATION_SECONDS = 30", body)
        self.assertIn("COUNT_CAP = 500", body)

    def test_generate_event_consumer_prefers_appdata(self) -> None:
        req = self.module.GenerationRequest(
            template="event_consumer",
            params={"subject": "hosts/Server/AVDetector.1/EventSupplier"},
        )
        bundle = self.gen.generate(req)
        self.assertIsInstance(bundle, self.module.GeneratedBundle)
        self.assertTrue(any("AppDataDetector" in n for n in bundle.notes))
        self.assertIn("AppDataDetector", bundle.files["main.py"])

    def test_generate_external_event_producer_requires_detectorex(self) -> None:
        req = self.module.GenerationRequest(
            template="external_event_producer",
            params={"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1"},
        )
        bundle = self.gen.generate(req)
        self.assertIsInstance(bundle, self.module.GeneratedBundle)
        body = bundle.files["main.py"]
        self.assertIn("ExternalDetector", body)
        self.assertIn("ConfigurationService.ListUnits", body)

    def test_generate_export_job_cleanup_in_finally(self) -> None:
        req = self.module.GenerationRequest(
            template="export_job",
            params={
                "camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                "begin": "2026-05-15T10:00:00Z",
                "end": "2026-05-15T10:05:00Z",
                "format": "jpeg",
            },
        )
        bundle = self.gen.generate(req)
        self.assertIsInstance(bundle, self.module.GeneratedBundle)
        tree = ast.parse(bundle.files["main.py"])
        cleanup_in_finally = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) and node.finalbody:
                cleanup_in_finally = True
        self.assertTrue(cleanup_in_finally, "export_job must perform cleanup in a finally block")

    def test_verifier_rejects_embedded_secrets(self) -> None:
        verifier = self.module.Verifier()
        result = verifier.verify_bundle(
            {
                "main.py": "AXXON_PASSWORD = 'hunter2'\nimport os\n",
                "README.md": "x",
                "requirements.txt": "x",
            }
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("secret_match" in e for e in result.errors))

    def test_verifier_rejects_disallowed_import(self) -> None:
        verifier = self.module.Verifier()
        result = verifier.verify_bundle(
            {
                "main.py": "import subprocess\nimport os\n",
                "README.md": "x",
                "requirements.txt": "x",
            }
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("disallowed_import" in e for e in result.errors))

    def test_verifier_accepts_clean_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        result = verifier.verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_generate_refuses_in_repo_without_flag(self) -> None:
        # tool-layer concern: the generator itself does not write files.
        # The MCP server's `generate_integration` enforces the in-repo refusal.
        # Here we verify the helper used by the server.
        helper = self.module
        repo_root = helper.REPO_ROOT
        target = repo_root / "tools" / "_generated_test"
        self.assertTrue(str(target).startswith(str(repo_root)))
        self.assertFalse(helper.allow_in_repo_write(target, allow=False))
        self.assertTrue(helper.allow_in_repo_write(target, allow=True))
        outside = Path(tempfile.gettempdir()) / "axxon_gen_outside"
        self.assertTrue(helper.allow_in_repo_write(outside, allow=False))

    def test_mcp_server_exposes_generator_only_when_enabled(self) -> None:
        import axxon_mcp_server as srv_mod

        class FakeFastMCP:
            def __init__(self, *args, **kwargs):
                self.tools: dict[str, object] = {}
                self.resources: dict[str, object] = {}

            def tool(self, name=None):
                def deco(func):
                    self.tools[name or func.__name__] = func
                    return func
                return deco

            def resource(self, uri):
                def deco(func):
                    self.resources[uri] = func
                    return func
                return deco

        class StubDocs:
            corpus_dir = self.corpus

            def list_remaining_gaps(self):
                return {"gaps": []}

        srv_off = srv_mod.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        srv_on = srv_mod.create_server(
            docs=StubDocs(),
            generator=self.gen,
            fastmcp_factory=FakeFastMCP,
        )
        self.assertNotIn("list_integration_templates", srv_off.tools)
        self.assertIn("list_integration_templates", srv_on.tools)
        self.assertIn("plan_integration", srv_on.tools)
        self.assertIn("generate_integration", srv_on.tools)
        self.assertIn("verify_integration", srv_on.tools)


if __name__ == "__main__":
    unittest.main()
