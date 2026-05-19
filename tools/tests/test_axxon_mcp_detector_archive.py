from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_VALUE_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeClient:
    config = FakeConfig()

    def __init__(self, config: FakeConfig) -> None:
        self.config = config


class FakeDetectorCatalogClient(FakeClient):
    def __init__(self, config: FakeConfig) -> None:
        super().__init__(config)
        self.list_units_calls: list[str] = []
        self.factories_requested: list[dict[str, Any]] = []

    def list_units(self, unit_type: str) -> list[dict[str, Any]]:
        self.list_units_calls.append(unit_type)
        if unit_type == "AVDetector":
            return [
                {
                    "uid": "hosts/Server/AVDetector.1",
                    "type": "AVDetector",
                    "properties": [
                        {
                            "id": "input",
                            "properties": [
                                {
                                    "id": "detector",
                                    "enum_constraint": {
                                        "items": [
                                            {"value_string": "CrowdDensity"},
                                        ],
                                    },
                                },
                            ],
                        },
                    ],
                },
            ]
        if unit_type == "AppDataDetector":
            return [
                {
                    "uid": "hosts/Server/AppDataDetector.1",
                    "type": "AppDataDetector",
                    "properties": [
                        {
                            "id": "input",
                            "properties": [
                                {
                                    "id": "detector",
                                    "value_string": "FaceListMatch",
                                },
                            ],
                        },
                    ],
                },
            ]
        return []

    def detector_archive_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "AVDetector",
                "properties": [
                    {
                        "id": "input",
                        "properties": [
                            {
                                "id": "detector",
                                "enum_constraint": {
                                    "items": [
                                        {"value": "HelmetDetection"},
                                    ],
                                },
                            },
                        ],
                    },
                ],
            },
        ]

    def batch_get_factories(self, factory_ids: list[dict[str, Any]]) -> dict[str, Any]:
        self.factories_requested.extend(factory_ids)
        return {
            "body": {
                "items": [
                    {
                        "factory": {
                            "type": "AppDataDetector",
                            "properties": [
                                {
                                    "id": "input",
                                    "properties": [
                                        {
                                            "id": "detector",
                                            "enum_constraint": {
                                                "items": [
                                                    {"value_string": "QueueLength"},
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                        },
                    },
                ],
            },
        }


class FakeListComponentsRequest:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeListUnitsRequest:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeDomainPb:
    ListComponentsRequest = FakeListComponentsRequest


class FakeConfigPb:
    ListUnitsRequest = FakeListUnitsRequest


class FakeDomainStub:
    def __init__(self) -> None:
        self.requests: list[FakeListComponentsRequest] = []

    def ListComponents(self, request: FakeListComponentsRequest, timeout: float) -> list[dict[str, Any]]:
        self.requests.append(request)
        return [
            {
                "items": [
                    {
                        "access_point": "hosts/Server/AVDetector.2/EventSupplier.Detector",
                    },
                    {
                        "access_point": "hosts/Server/AppDataDetector.3/SourceEndpoint.Target",
                    },
                ],
            }
        ]


class FakeConfigStub:
    def __init__(self) -> None:
        self.list_units_requests: list[FakeListUnitsRequest] = []

    def ListUnits(self, request: FakeListUnitsRequest, timeout: float) -> dict[str, Any]:
        self.list_units_requests.append(request)
        uid = request.kwargs["unit_uids"][0]
        if uid == "hosts/Server/AVDetector.2":
            return {
                "units": [
                    {
                        "uid": uid,
                        "type": "AVDetector",
                        "properties": [
                            {
                                "id": "input",
                                "properties": [
                                    {
                                        "id": "detector",
                                        "enum_constraint": {
                                            "items": [
                                                {"value_string": "PeopleCounting"},
                                            ],
                                        },
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        if uid == "hosts/Server/AppDataDetector.3":
            return {
                "units": [
                    {
                        "uid": uid,
                        "type": "AppDataDetector",
                        "properties": [
                            {
                                "id": "input",
                                "properties": [
                                    {
                                        "id": "detector",
                                        "value_string": "VehicleListMatch",
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        return {"units": []}


class FakeRealShapedDetectorCatalogClient(FakeClient):
    def __init__(self, config: FakeConfig) -> None:
        super().__init__(config)
        self.authenticate_calls = 0
        self.domain = FakeDomainStub()
        self.config_stub = FakeConfigStub()
        self.factories_requested: list[dict[str, Any]] = []

    def authenticate_grpc(self) -> None:
        self.authenticate_calls += 1

    def import_module(self, module_name: str) -> Any:
        if module_name == "axxonsoft.bl.domain.Domain_pb2":
            return FakeDomainPb
        if module_name == "axxonsoft.bl.config.ConfigurationService_pb2":
            return FakeConfigPb
        raise AssertionError(module_name)

    def common_stubs(self) -> dict[str, Any]:
        return {"domain": self.domain, "config": self.config_stub}

    def message_to_dict(self, message: Any) -> dict[str, Any]:
        return message if isinstance(message, dict) else {}

    def batch_get_factories(self, factory_ids: list[dict[str, Any]]) -> dict[str, Any]:
        self.factories_requested.extend(factory_ids)
        return {"body": {"items": []}}


class AxxonMcpDetectorArchiveTests(unittest.TestCase):
    def test_module_loads_with_phase_5e_constants(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        self.assertEqual(module.DETECTOR_LIST_LIMIT_CAP, 200)
        self.assertEqual(module.METADATA_SAMPLE_TIMEOUT_DEFAULT, 5.0)
        self.assertEqual(module.METADATA_SAMPLE_TIMEOUT_CAP, 30.0)
        self.assertEqual(module.METADATA_SAMPLE_LIMIT_DEFAULT, 20)
        self.assertEqual(module.METADATA_SAMPLE_LIMIT_CAP, 200)
        self.assertIn("AVDetector", module.DETECTOR_UNIT_TYPES)
        self.assertIn("AppDataDetector", module.DETECTOR_UNIT_TYPES)
        self.assertIn("MotionDetection", module.KNOWN_DETECTOR_KINDS["AVDetector"])
        self.assertIn("MoveInZone", module.KNOWN_DETECTOR_KINDS["AppDataDetector"])

    def test_detector_archive_connect_axxon_profile_reports_redacted_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeClient(config),
            config_factory=lambda: FakeConfig(),
        )

        profile = archive.detector_archive_connect_axxon_profile("env")

        self.assertTrue(profile["connected"])
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], "read-only")
        self.assertEqual(profile["profile"]["host"], "example.local")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertIsInstance(archive.client, FakeClient)
        self.assertEqual(archive.profile_name, "env")
        self.assertNotIn("CONFIG_VALUE_SHOULD_NOT_LEAK", str(profile))

        rejected = archive.detector_archive_connect_axxon_profile("other")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(rejected["profile_name"], "other")

    def test_ensure_client_connects_env_profile_once(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        calls: list[str] = []

        def client_factory(config: FakeConfig) -> FakeClient:
            calls.append(config.host)
            return FakeClient(config)

        archive = module.AxxonMcpDetectorArchive(
            client_factory=client_factory,
            config_factory=lambda: FakeConfig(),
        )

        first = archive.ensure_client()
        second = archive.ensure_client()

        self.assertIs(first, second)
        self.assertEqual(calls, ["example.local"])

    def test_sensitive_property_redaction_normalizes_nested_values(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        raw: dict[str, Any] = {
            "display_name": "Detector",
            "properties": {
                "password": "PROPERTY_VALUE_SHOULD_NOT_LEAK",
                "apiToken": "TOKEN_VALUE_SHOULD_NOT_LEAK",
                "camera": {
                    "serialNumber": "SERIAL_VALUE_SHOULD_NOT_LEAK",
                    "enabled": True,
                },
                "zones": [
                    {"license": "LICENSE_VALUE_SHOULD_NOT_LEAK"},
                    {"name": "safe"},
                ],
            },
        }

        redacted = module.redact_sensitive_properties(raw)

        self.assertEqual(redacted["display_name"], "Detector")
        self.assertEqual(redacted["properties"]["password"], "<redacted>")
        self.assertEqual(redacted["properties"]["apiToken"], "<redacted>")
        self.assertEqual(redacted["properties"]["camera"]["serialNumber"], "<redacted>")
        self.assertTrue(redacted["properties"]["camera"]["enabled"])
        self.assertEqual(redacted["properties"]["zones"][0]["license"], "<redacted>")
        self.assertEqual(redacted["properties"]["zones"][1]["name"], "safe")
        self.assertNotIn("PROPERTY_VALUE_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("TOKEN_VALUE_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("SERIAL_VALUE_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("LICENSE_VALUE_SHOULD_NOT_LEAK", str(redacted))

    def test_sensitive_property_redaction_handles_axxon_property_nodes(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        raw: dict[str, Any] = {
            "properties": [
                {
                    "id": "password",
                    "name": "Password",
                    "type": "string",
                    "readonly": False,
                    "value_kind": "value_string",
                    "value": "SECRET_SHOULD_NOT_LEAK",
                    "value_string": "PROPERTY_VALUE_SHOULD_NOT_LEAK",
                },
                {
                    "id": "display_name",
                    "name": "Display name",
                    "type": "string",
                    "readonly": False,
                    "value_string": "Detector 1",
                },
                {
                    "id": "connection",
                    "name": "Connection",
                    "type": "group",
                    "readonly": True,
                    "properties": [
                        {
                            "id": "apiToken",
                            "name": "API token",
                            "type": "string",
                            "readonly": False,
                            "value_string": "TOKEN_VALUE_SHOULD_NOT_LEAK",
                        },
                        {
                            "id": "endpoint",
                            "name": "Endpoint",
                            "type": "string",
                            "readonly": False,
                            "value_string": "metadata-stream",
                        },
                    ],
                },
            ],
        }

        redacted = module.redact_sensitive_properties(raw)

        password = redacted["properties"][0]
        self.assertEqual(password["id"], "password")
        self.assertEqual(password["name"], "Password")
        self.assertEqual(password["type"], "string")
        self.assertFalse(password["readonly"])
        self.assertEqual(password["value_kind"], "value_string")
        self.assertEqual(password["value"], "<redacted>")
        self.assertEqual(password["value_string"], "<redacted>")

        display_name = redacted["properties"][1]
        self.assertEqual(display_name["id"], "display_name")
        self.assertEqual(display_name["value_string"], "Detector 1")

        connection = redacted["properties"][2]
        self.assertEqual(connection["id"], "connection")
        self.assertTrue(connection["readonly"])
        token = connection["properties"][0]
        self.assertEqual(token["id"], "apiToken")
        self.assertEqual(token["value_string"], "<redacted>")
        endpoint = connection["properties"][1]
        self.assertEqual(endpoint["id"], "endpoint")
        self.assertEqual(endpoint["value_string"], "metadata-stream")
        self.assertNotIn("SECRET_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("PROPERTY_VALUE_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("TOKEN_VALUE_SHOULD_NOT_LEAK", str(redacted))

    def test_detector_kind_catalog_returns_known_fallback_without_live_lookup(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorCatalogClient(config),
            config_factory=lambda: FakeConfig(),
        )

        catalog = archive.detector_kind_catalog(include_live=False)

        self.assertEqual(catalog["status"], "ok")
        self.assertEqual(catalog["tool"], "detector_kind_catalog")
        self.assertFalse(catalog["include_live"])
        self.assertEqual(catalog["count"], sum(len(items) for items in catalog["by_unit_type"].values()))
        self.assertIsNone(archive.client)

        av_by_kind = {entry["detector_kind"]: entry for entry in catalog["by_unit_type"]["AVDetector"]}
        motion = av_by_kind["MotionDetection"]
        self.assertEqual(motion["unit_type"], "AVDetector")
        self.assertEqual(motion["source_type"], "Video")
        self.assertEqual(motion["provenance"], ["known-catalog"])
        self.assertEqual(motion["fixtures"]["required"], ["video_source_ap"])
        self.assertEqual(motion["fixtures"]["missing"], ["video_source_ap"])

        app_by_kind = {entry["detector_kind"]: entry for entry in catalog["by_unit_type"]["AppDataDetector"]}
        move_in_zone = app_by_kind["MoveInZone"]
        self.assertEqual(move_in_zone["source_type"], "TargetList")
        self.assertEqual(move_in_zone["provenance"], ["known-catalog"])
        self.assertEqual(move_in_zone["fixtures"]["required"], ["video_source_ap", "vmda_source_ap"])
        self.assertEqual(move_in_zone["fixtures"]["missing"], ["video_source_ap", "vmda_source_ap"])

    def test_detector_kind_catalog_merges_live_template_and_factory_sources(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        fake = FakeDetectorCatalogClient(FakeConfig())
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        catalog = archive.detector_kind_catalog(include_live=True)

        self.assertEqual(catalog["status"], "ok")
        self.assertTrue(catalog["include_live"])
        self.assertEqual(fake.list_units_calls, ["AVDetector", "AppDataDetector"])
        self.assertEqual(
            fake.factories_requested,
            [
                {"unit_type": "AVDetector", "parent_uid": "hosts/Server", "ignore_possible_limits": True},
                {"unit_type": "AppDataDetector", "parent_uid": "hosts/Server", "ignore_possible_limits": True},
            ],
        )

        av_by_kind = {entry["detector_kind"]: entry for entry in catalog["by_unit_type"]["AVDetector"]}
        self.assertIn("CrowdDensity", av_by_kind)
        self.assertEqual(av_by_kind["CrowdDensity"]["provenance"], ["live-unit"])
        self.assertEqual(av_by_kind["CrowdDensity"]["source_type"], "Video")

        self.assertIn("HelmetDetection", av_by_kind)
        self.assertEqual(av_by_kind["HelmetDetection"]["provenance"], ["template"])

        app_by_kind = {entry["detector_kind"]: entry for entry in catalog["by_unit_type"]["AppDataDetector"]}
        self.assertIn("FaceListMatch", app_by_kind)
        self.assertEqual(app_by_kind["FaceListMatch"]["provenance"], ["live-unit"])
        self.assertEqual(app_by_kind["FaceListMatch"]["source_type"], "TargetList")

        self.assertIn("QueueLength", app_by_kind)
        self.assertEqual(app_by_kind["QueueLength"]["provenance"], ["factory"])
        self.assertEqual(app_by_kind["QueueLength"]["fixtures"]["required"], ["video_source_ap", "vmda_source_ap"])

    def test_detector_kind_catalog_reads_real_client_live_units_without_list_units_wrapper(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        fake = FakeRealShapedDetectorCatalogClient(FakeConfig())
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        catalog = archive.detector_kind_catalog(include_live=True)

        self.assertEqual(fake.authenticate_calls, 1)
        self.assertEqual(fake.domain.requests[0].kwargs, {"page_size": 500})
        self.assertEqual(
            [request.kwargs for request in fake.config_stub.list_units_requests],
            [
                {"unit_uids": ["hosts/Server/AVDetector.2"]},
                {"unit_uids": ["hosts/Server/AppDataDetector.3"]},
            ],
        )
        av_by_kind = {entry["detector_kind"]: entry for entry in catalog["by_unit_type"]["AVDetector"]}
        self.assertEqual(av_by_kind["PeopleCounting"]["provenance"], ["live-unit"])
        app_by_kind = {entry["detector_kind"]: entry for entry in catalog["by_unit_type"]["AppDataDetector"]}
        self.assertEqual(app_by_kind["VehicleListMatch"]["provenance"], ["live-unit"])

    def test_detector_kind_catalog_requests_factories_with_host_parent_uid(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        fake = FakeRealShapedDetectorCatalogClient(FakeConfig())
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        archive.detector_kind_catalog(include_live=True)

        self.assertEqual(
            fake.factories_requested,
            [
                {"unit_type": "AVDetector", "parent_uid": "hosts/Server", "ignore_possible_limits": True},
                {"unit_type": "AppDataDetector", "parent_uid": "hosts/Server", "ignore_possible_limits": True},
            ],
        )


if __name__ == "__main__":
    unittest.main()
