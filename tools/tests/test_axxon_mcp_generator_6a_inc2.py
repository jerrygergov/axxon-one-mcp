"""Phase 6A increment 2 tests: Node/TS variants for remaining 7 templates."""
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


class GrpcConsumerNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_grpc_consumer_node_returns_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)
        self.assertIn("README.md", result.files)
        self.assertIn("package.json", result.files)

    def test_grpc_consumer_node_bakes_in_caps(self) -> None:
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("DURATION_SECONDS", ts)

    def test_grpc_consumer_node_uses_process_env(self) -> None:
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("process.env", ts)

    def test_grpc_consumer_node_verifier_passes(self) -> None:
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        result = verifier.verify_bundle(bundle.files)
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_grpc_consumer_node_languages_field(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("node", entries["grpc_consumer"]["languages"])

    def test_grpc_consumer_node_refuses_mutation(self) -> None:
        """Node language still respects mutation guard."""
        req = self.module.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        # safe-read so it should pass
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)


class HttpGrpcConsumerNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_http_grpc_consumer_node_returns_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="http_grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)
        self.assertIn("package.json", result.files)

    def test_http_grpc_consumer_node_bakes_caps(self) -> None:
        req = self.module.GenerationRequest(
            template="http_grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("DURATION_SECONDS", ts)
        self.assertIn("BYTE_CAP", ts)

    def test_http_grpc_consumer_node_uses_process_env(self) -> None:
        req = self.module.GenerationRequest(
            template="http_grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("process.env", result.files["src/index.ts"])

    def test_http_grpc_consumer_node_verifier_passes(self) -> None:
        req = self.module.GenerationRequest(
            template="http_grpc_consumer",
            params={"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
            language="node",
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        self.assertTrue(verifier.verify_bundle(bundle.files).ok)

    def test_http_grpc_consumer_node_languages_field(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("node", entries["http_grpc_consumer"]["languages"])


class LegacyHttpConsumerNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_legacy_http_consumer_node_returns_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="legacy_http_consumer",
            params={"path": "/product/version"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)

    def test_legacy_http_consumer_node_bakes_caps(self) -> None:
        req = self.module.GenerationRequest(
            template="legacy_http_consumer",
            params={"path": "/product/version"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("DURATION_SECONDS", ts)
        self.assertIn("BYTE_CAP", ts)

    def test_legacy_http_consumer_node_uses_process_env(self) -> None:
        req = self.module.GenerationRequest(
            template="legacy_http_consumer",
            params={"path": "/product/version"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIn("process.env", result.files["src/index.ts"])

    def test_legacy_http_consumer_node_verifier_passes(self) -> None:
        req = self.module.GenerationRequest(
            template="legacy_http_consumer",
            params={"path": "/product/version"},
            language="node",
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        self.assertTrue(verifier.verify_bundle(bundle.files).ok)

    def test_legacy_http_consumer_node_languages_field(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("node", entries["legacy_http_consumer"]["languages"])


class ExternalEventProducerNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_external_event_producer_node_returns_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="external_event_producer",
            params={"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)

    def test_external_event_producer_node_bakes_access_point(self) -> None:
        req = self.module.GenerationRequest(
            template="external_event_producer",
            params={"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("DetectorEx.1", ts)
        self.assertIn("Event1", ts)

    def test_external_event_producer_node_uses_process_env(self) -> None:
        req = self.module.GenerationRequest(
            template="external_event_producer",
            params={"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIn("process.env", result.files["src/index.ts"])

    def test_external_event_producer_node_verifier_passes(self) -> None:
        req = self.module.GenerationRequest(
            template="external_event_producer",
            params={"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1"},
            language="node",
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        self.assertTrue(verifier.verify_bundle(bundle.files).ok)

    def test_external_event_producer_node_languages_field(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("node", entries["external_event_producer"]["languages"])


class WebhookBridgeNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_webhook_bridge_node_returns_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="webhook_bridge",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)

    def test_webhook_bridge_node_bakes_caps(self) -> None:
        req = self.module.GenerationRequest(
            template="webhook_bridge",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("DURATION_SECONDS", ts)
        self.assertIn("COUNT_CAP", ts)

    def test_webhook_bridge_node_uses_process_env(self) -> None:
        req = self.module.GenerationRequest(
            template="webhook_bridge",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        result = self.gen.generate(req)
        ts = result.files["src/index.ts"]
        self.assertIn("process.env", ts)
        self.assertIn("WEBHOOK_URL", ts)

    def test_webhook_bridge_node_no_raw_webhook_url_in_log(self) -> None:
        """WEBHOOK_URL value must not be logged directly."""
        req = self.module.GenerationRequest(
            template="webhook_bridge",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        result = self.gen.generate(req)
        ts = result.files["src/index.ts"]
        for line in ts.splitlines():
            if "console." in line and "WEBHOOK_URL" in line and "split" not in line and "replace" not in line:
                self.fail(f"raw WEBHOOK_URL logged: {line!r}")

    def test_webhook_bridge_node_verifier_passes(self) -> None:
        req = self.module.GenerationRequest(
            template="webhook_bridge",
            params={"subject": "hosts/Server/AppDataDetector.1/EventSupplier"},
            language="node",
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        self.assertTrue(verifier.verify_bundle(bundle.files).ok)

    def test_webhook_bridge_node_languages_field(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("node", entries["webhook_bridge"]["languages"])


class ExportJobNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_export_job_node_returns_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="export_job",
            params={
                "camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                "begin": "2026-05-15T10:00:00Z",
                "end": "2026-05-15T10:05:00Z",
            },
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)

    def test_export_job_node_bakes_caps(self) -> None:
        req = self.module.GenerationRequest(
            template="export_job",
            params={
                "camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                "begin": "2026-05-15T10:00:00Z",
                "end": "2026-05-15T10:05:00Z",
            },
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("BYTE_CAP", ts)

    def test_export_job_node_uses_process_env(self) -> None:
        req = self.module.GenerationRequest(
            template="export_job",
            params={
                "camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                "begin": "2026-05-15T10:00:00Z",
                "end": "2026-05-15T10:05:00Z",
            },
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIn("process.env", result.files["src/index.ts"])

    def test_export_job_node_verifier_passes(self) -> None:
        req = self.module.GenerationRequest(
            template="export_job",
            params={
                "camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                "begin": "2026-05-15T10:00:00Z",
                "end": "2026-05-15T10:05:00Z",
            },
            language="node",
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        self.assertTrue(verifier.verify_bundle(bundle.files).ok)

    def test_export_job_node_languages_field(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("node", entries["export_job"]["languages"])


class InventorySyncNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.module, self.gen = load_generator(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_inventory_sync_node_returns_bundle(self) -> None:
        req = self.module.GenerationRequest(
            template="inventory_sync",
            params={"output_path": "~/axxon-inventory.json"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        self.assertIn("src/index.ts", result.files)

    def test_inventory_sync_node_bakes_output_path(self) -> None:
        req = self.module.GenerationRequest(
            template="inventory_sync",
            params={"output_path": "~/axxon-inventory.json"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIsInstance(result, self.module.GeneratedBundle)
        ts = result.files["src/index.ts"]
        self.assertIn("axxon-inventory.json", ts)
        self.assertIn("BYTE_CAP", ts)

    def test_inventory_sync_node_uses_process_env(self) -> None:
        req = self.module.GenerationRequest(
            template="inventory_sync",
            params={"output_path": "~/axxon-inventory.json"},
            language="node",
        )
        result = self.gen.generate(req)
        self.assertIn("process.env", result.files["src/index.ts"])

    def test_inventory_sync_node_verifier_passes(self) -> None:
        req = self.module.GenerationRequest(
            template="inventory_sync",
            params={"output_path": "~/axxon-inventory.json"},
            language="node",
        )
        bundle = self.gen.generate(req)
        verifier = self.module.Verifier()
        self.assertTrue(verifier.verify_bundle(bundle.files).ok)

    def test_inventory_sync_node_languages_field(self) -> None:
        entries = {t["name"]: t for t in self.gen.list_templates()}
        self.assertIn("node", entries["inventory_sync"]["languages"])

    def test_inventory_sync_node_has_list_cameras_and_units(self) -> None:
        req = self.module.GenerationRequest(
            template="inventory_sync",
            params={"output_path": "~/axxon-inventory.json"},
            language="node",
        )
        result = self.gen.generate(req)
        ts = result.files["src/index.ts"]
        self.assertIn("ListCameras", ts)
        self.assertIn("ListUnits", ts)


if __name__ == "__main__":
    unittest.main()
