from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class McpCorpusGeneratorTests(unittest.TestCase):
    def test_generate_corpus_writes_phase_zero_files(self) -> None:
        module = importlib.import_module("generate_mcp_corpus")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audit = root / "docs" / "api-audit"
            audit.mkdir(parents=True)
            (audit / "grpc-api-catalog.csv").write_text(
                "\n".join(
                    [
                        "package,service,method,fqmn,request,response,streaming,safety,live_status,http,proto",
                        "axxonsoft.bl.domain,DomainService,ListCameras,axxonsoft.bl.domain.DomainService.ListCameras,ListCamerasRequest,ListCamerasResponse,server,read,tested-pass,GET /v1/domain/cameras,axxonsoft/bl/domain/Domain.proto",
                        "axxonsoft.bl.config,ConfigurationService,ChangeConfig,axxonsoft.bl.config.ConfigurationService.ChangeConfig,ChangeConfigRequest,ChangeConfigResponse,none,mutating,tested-pass-safe-record,POST /v1/configurator:change,axxonsoft/bl/config/ConfigurationService.proto",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (audit / "http-endpoints-catalog.md").write_text(
                textwrap.dedent(
                    """\
                    # HTTP
                    | Verb | Path | gRPC Method | Safety | Live | Proto |
                    | --- | --- | --- | --- | --- | --- |
                    | `GET` | `/v1/domain/cameras` | `axxonsoft.bl.domain.DomainService.ListCameras` | `read` | `tested-pass` | `axxonsoft/bl/domain/Domain.proto` |
                    """
                ),
                encoding="utf-8",
            )
            (audit.parent / "Axxon_One_Integration_APIs.postman_collection.json").write_text(
                json.dumps(
                    {
                        "item": [
                            {
                                "name": "Legacy web",
                                "item": [
                                    {
                                        "name": "Get hosts",
                                        "request": {
                                            "method": "GET",
                                            "url": {
                                                "raw": "{{baseUrl}}/hosts/",
                                                "path": ["hosts", ""],
                                            },
                                        },
                                    }
                                ],
                            },
                            {
                                "name": "Client HTTP API",
                                "item": [
                                    {
                                        "name": "SwitchLayout",
                                        "request": {
                                            "method": "POST",
                                            "url": {
                                                "raw": "http://127.0.0.1:8888/SwitchLayout?layout=Main",
                                                "path": ["SwitchLayout"],
                                            },
                                        },
                                    }
                                ],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (audit / "pdf-gap-coverage-matrix.json").write_text(
                json.dumps(
                    [
                        {
                            "pdf_area": "Inventory",
                            "pages": "1-2",
                            "status": "verified",
                            "risk": "safe-read",
                            "tooling": "tool.py",
                            "report": "api-audit/report.md",
                            "next_step": "covered",
                        },
                        {
                            "pdf_area": "PTZ",
                            "pages": "3-4",
                            "status": "fixture-needed",
                            "risk": "mutation",
                            "tooling": "ptz.py",
                            "report": "api-audit/ptz.md",
                            "next_step": "needs telemetry/PTZ access point",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            (audit / "integration-playbooks.md").write_text(
                "## Inventory And Discovery\n\nUse `ListCameras`.\n\n## Events And Search\n\nUse bounded subscriptions.\n",
                encoding="utf-8",
            )
            playbook_dir = audit / "mutation-playbooks"
            playbook_dir.mkdir()
            (playbook_dir / "ptz-control.md").write_text("# PTZ\n\n- Risk level: high\n", encoding="utf-8")

            output_dir = root / "docs" / "api-audit" / "mcp-corpus"
            written = module.generate_corpus(audit_dir=audit, output_dir=output_dir)

            self.assertEqual(
                set(written),
                {
                    "api_methods.json",
                    "http_endpoints.json",
                    "legacy_http_endpoints.json",
                    "task_recipes.json",
                    "fixtures.json",
                    "safety_policies.json",
                    "known_behaviors.json",
                },
            )
            api_methods = json.loads((output_dir / "api_methods.json").read_text(encoding="utf-8"))
            self.assertEqual(api_methods["method_count"], 4)
            self.assertEqual(api_methods["methods"][0]["fqmn"], "axxonsoft.bl.domain.DomainService.ListCameras")
            self.assertEqual(api_methods["methods"][1]["safety_class"], "mutating")
            self.assertIn("grpc.health.v1.Health.Check", {method["fqmn"] for method in api_methods["methods"]})

            fixtures = json.loads((output_dir / "fixtures.json").read_text(encoding="utf-8"))
            self.assertEqual(fixtures["coverage_counts"]["verified"], 1)
            self.assertEqual(fixtures["coverage_counts"]["fixture-needed"], 1)
            self.assertEqual(fixtures["fixture_needed"][0]["missing_fixture"], "needs telemetry/PTZ access point")

            endpoints = json.loads((output_dir / "http_endpoints.json").read_text(encoding="utf-8"))
            self.assertEqual(endpoints["endpoints"][0]["path"], "/v1/domain/cameras")

            legacy = json.loads((output_dir / "legacy_http_endpoints.json").read_text(encoding="utf-8"))
            self.assertEqual(legacy["endpoint_count"], 2)
            self.assertEqual(legacy["endpoints"][0]["path"], "/hosts/")
            self.assertEqual(legacy["endpoints"][0]["surface"], "legacy_web_http")
            self.assertEqual(legacy["endpoints"][1]["surface"], "client_http_api")


if __name__ == "__main__":
    unittest.main()
