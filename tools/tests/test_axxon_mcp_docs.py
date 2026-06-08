from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class AxxonMcpDocsTests(unittest.TestCase):
    def make_corpus(self, root: Path) -> Path:
        corpus = root / "mcp-corpus"
        corpus.mkdir()
        (corpus / "api_methods.json").write_text(
            json.dumps(
                {
                    "source": "docs/api-audit/grpc-api-catalog.csv",
                    "method_count": 2,
                    "methods": [
                        {
                            "fqmn": "axxonsoft.bl.domain.DomainService.ListCameras",
                            "package": "axxonsoft.bl.domain",
                            "service": "DomainService",
                            "method": "ListCameras",
                            "request": "ListCamerasRequest",
                            "response": "ListCamerasResponse",
                            "streaming": "server",
                            "safety_class": "read",
                            "live_status": "tested-pass",
                            "http_annotation": "GET /v1/domain/cameras",
                            "proto": "axxonsoft/bl/domain/Domain.proto",
                        },
                        {
                            "fqmn": "axxonsoft.bl.config.ConfigurationService.ChangeConfig",
                            "package": "axxonsoft.bl.config",
                            "service": "ConfigurationService",
                            "method": "ChangeConfig",
                            "request": "ChangeConfigRequest",
                            "response": "ChangeConfigResponse",
                            "streaming": "none",
                            "safety_class": "mutating",
                            "live_status": "tested-pass-safe-record",
                            "http_annotation": "",
                            "proto": "axxonsoft/bl/config/ConfigurationService.proto",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (corpus / "http_endpoints.json").write_text(
            json.dumps(
                {
                    "source": "docs/api-audit/http-endpoints-catalog.md",
                    "endpoint_count": 1,
                    "endpoints": [
                        {
                            "verb": "GET",
                            "path": "/v1/domain/cameras",
                            "grpc_method": "axxonsoft.bl.domain.DomainService.ListCameras",
                            "safety_class": "read",
                            "live_status": "tested-pass",
                            "proto": "axxonsoft/bl/domain/Domain.proto",
                            "source": "docs/api-audit/http-endpoints-catalog.md",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (corpus / "task_recipes.json").write_text(
            json.dumps(
                {
                    "source": "docs/api-audit/integration-playbooks.md",
                    "recipes": [
                        {
                            "task": "Inventory And Discovery",
                            "summary": "Use DomainService.ListCameras for VMS inventory sync and camera selection.",
                            "source": "docs/api-audit/integration-playbooks.md",
                        },
                        {
                            "task": "Configuration And Device Catalog",
                            "summary": "Use ConfigurationService.ChangeConfig only with fixtures and rollback.",
                            "source": "docs/api-audit/integration-playbooks.md",
                        },
                    ],
                    "mutation_playbooks": [
                        {
                            "name": "detector-parameters",
                            "title": "Mutation Playbook: Detector Parameters",
                            "source": "docs/api-audit/mutation-playbooks/detector-parameters.md",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (corpus / "fixtures.json").write_text(
            json.dumps(
                {
                    "source": "docs/api-audit/pdf-gap-coverage-matrix.json",
                    "coverage_counts": {"verified": 18, "fixture-needed": 1},
                    "fixture_needed": [
                        {
                            "pdf_area": "Legacy HTTP PTZ camera control",
                            "pages": "80-87",
                            "risk": "mutation",
                            "tooling": "axxon_ptz_preflight.py",
                            "report": "api-audit/ptz-preflight-latest.md",
                            "missing_fixture": "Add a non-production PTZ fixture.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (corpus / "safety_policies.json").write_text(
            json.dumps({"default_mode": "read-only", "classes": {"mutation": {"requires_approval": True}}}),
            encoding="utf-8",
        )
        (corpus / "known_behaviors.json").write_text(
            json.dumps(
                {
                    "behaviors": [
                        {
                            "topic": "websocket_events",
                            "behavior": "Demo Web server upgrades /events then closes during receive.",
                            "source": "docs/api-audit/subscription-smoke-latest.md",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return corpus

    def test_docs_index_supports_phase_one_tool_queries(self) -> None:
        module = importlib.import_module("axxon_mcp_docs")
        with tempfile.TemporaryDirectory() as temp:
            docs = module.AxxonMcpDocs.from_corpus_dir(self.make_corpus(Path(temp)))

            method = docs.get_api_method("DomainService.ListCameras")
            self.assertTrue(method["found"])
            self.assertEqual(method["method"]["fqmn"], "axxonsoft.bl.domain.DomainService.ListCameras")
            self.assertIn("docs/api-audit/grpc-api-catalog.csv", method["sources"])

            endpoint = docs.get_http_endpoint("/v1/domain/cameras")
            self.assertTrue(endpoint["found"])
            self.assertEqual(endpoint["endpoint"]["grpc_method"], "axxonsoft.bl.domain.DomainService.ListCameras")

            recipe = docs.explain_task_recipe("camera inventory")
            self.assertTrue(recipe["found"])
            self.assertEqual(recipe["recipe"]["task"], "Inventory And Discovery")

            results = docs.search_api_docs("change camera configuration")
            self.assertGreaterEqual(len(results["results"]), 2)
            self.assertEqual(results["results"][0]["kind"], "method")

            example = docs.get_verified_example("websocket events")
            self.assertTrue(example["found"])
            self.assertEqual(example["example"]["topic"], "websocket_events")

            gaps = docs.list_remaining_gaps()
            self.assertEqual(gaps["coverage_counts"]["fixture-needed"], 1)
            self.assertEqual(gaps["gaps"][0]["pdf_area"], "Legacy HTTP PTZ camera control")

    def test_unknown_queries_are_reported_as_gaps_not_invented(self) -> None:
        module = importlib.import_module("axxon_mcp_docs")
        with tempfile.TemporaryDirectory() as temp:
            docs = module.AxxonMcpDocs.from_corpus_dir(self.make_corpus(Path(temp)))

            method = docs.get_api_method("NoSuchService.NoSuchMethod")
            self.assertFalse(method["found"])
            self.assertEqual(method["status"], "gap")
            self.assertIn("NoSuchService.NoSuchMethod", method["query"])

            endpoint = docs.get_http_endpoint("/v1/not/real")
            self.assertFalse(endpoint["found"])
            self.assertEqual(endpoint["status"], "gap")


if __name__ == "__main__":
    unittest.main()
