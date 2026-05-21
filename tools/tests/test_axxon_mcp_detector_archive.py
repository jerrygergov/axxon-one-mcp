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


class FakeListTemplatesRequest:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeDomainPb:
    ListComponentsRequest = FakeListComponentsRequest


class FakeConfigPb:
    VIEW_MODE_FULL = "VIEW_MODE_FULL"
    ListUnitsRequest = FakeListUnitsRequest
    ListTemplatesRequest = FakeListTemplatesRequest


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
        self.list_templates_requests: list[FakeListTemplatesRequest] = []

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

    def ListTemplates(self, request: FakeListTemplatesRequest, timeout: float) -> dict[str, Any]:
        self.list_templates_requests.append(request)
        return {
            "items": [
                {
                    "body": {
                        "unit": {
                            "type": "AVDetector",
                            "properties": [
                                {
                                    "id": "input",
                                    "properties": [
                                        {
                                            "id": "detector",
                                            "enum_constraint": {
                                                "items": [
                                                    {"value_string": "Loitering"},
                                                ],
                                            },
                                        },
                                    ],
                                }
                            ],
                        }
                    }
                }
            ]
        }


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


class FakeDetectorSchemaClient(FakeClient):
    def list_units(self, unit_type: str) -> list[dict[str, Any]]:
        if unit_type != "AppDataDetector":
            return []
        return [
            {
                "uid": "hosts/Server/AppDataDetector.Schema",
                "type": "AppDataDetector",
                "source_type": "TargetList",
                "properties": [
                    {
                        "id": "input",
                        "type": "group",
                        "required": True,
                        "properties": [
                            {
                                "id": "detector",
                                "type": "string",
                                "readonly": False,
                                "internal": False,
                                "value_kind": "value_string",
                                "value_string": "MoveInZone",
                                "enum_constraint": {
                                    "items": [
                                        {"value_string": "MoveInZone", "name": "Move in zone"},
                                        {"value_string": "LongInZone", "name": "Long in zone"},
                                    ],
                                },
                            },
                            {
                                "id": "camera_ref",
                                "type": "link",
                                "properties": [
                                    {
                                        "id": "streaming_id",
                                        "type": "string",
                                        "value_kind": "value_string",
                                        "value_string": "vmda-source",
                                    },
                                ],
                            },
                        ],
                    },
                    {
                        "id": "advanced",
                        "type": "group",
                        "properties": [
                            {
                                "id": "sensitivity",
                                "type": "int",
                                "value_kind": "value_int32",
                                "value_int32": 42,
                                "range_constraint": {"min_int": 0, "max_int": 100},
                            },
                            {
                                "id": "apiToken",
                                "type": "string",
                                "value_kind": "value_string",
                                "value_string": "SCHEMA_SECRET_SHOULD_NOT_LEAK",
                                "enum_constraint": {
                                    "items": [
                                        {"value_string": "ENUM_SECRET_SHOULD_NOT_LEAK", "name": "Leaked token"},
                                    ],
                                },
                            },
                        ],
                    },
                ],
                "child_units": [
                    {
                        "uid": "hosts/Server/AppDataDetector.Schema/VisualElement.1",
                        "type": "VisualElement",
                        "name": "VisualElement",
                        "properties": [
                            {
                                "id": "polyline",
                                "type": "shape",
                                "readonly": False,
                                "value_simple_polygon": {
                                    "points": [
                                        {"x": 0.1, "y": 0.1},
                                        {"x": 0.9, "y": 0.1},
                                    ],
                                },
                            },
                            {
                                "id": "secretOverlayToken",
                                "type": "string",
                                "value_string": "VISUAL_SECRET_SHOULD_NOT_LEAK",
                            },
                        ],
                    }
                ],
            }
        ]

    def detector_archive_templates(self) -> list[dict[str, Any]]:
        return []

    def batch_get_factories(self, factory_ids: list[dict[str, Any]]) -> dict[str, Any]:
        return {"body": {"items": []}}


class FakeDetectorConfigClient(FakeClient):
    detector_uid = "hosts/Server/AppDataDetector.Config"

    def __init__(self, config: FakeConfig) -> None:
        super().__init__(config)
        self.list_units_calls: list[str] = []

    def list_units(self, unit_type: str) -> list[dict[str, Any]]:
        self.list_units_calls.append(unit_type)
        if unit_type != "AppDataDetector":
            return []
        return [
            {
                "uid": self.detector_uid,
                "type": "AppDataDetector",
                "source_type": "TargetList",
                "display_name": "Zone watcher",
                "properties": [
                    {
                        "id": "input",
                        "type": "group",
                        "properties": [
                            {
                                "id": "detector",
                                "type": "string",
                                "readonly": False,
                                "value_kind": "value_string",
                                "value_string": "MoveInZone",
                            },
                        ],
                    },
                    {
                        "id": "advanced",
                        "type": "group",
                        "properties": [
                            {
                                "id": "sensitivity",
                                "type": "int",
                                "readonly": False,
                                "value_kind": "value_int32",
                                "value_int32": 55,
                            },
                            {
                                "id": "apiToken",
                                "type": "string",
                                "readonly": False,
                                "value_kind": "value_string",
                                "value_string": "CONFIG_SECRET_SHOULD_NOT_LEAK",
                                "enum_constraint": {
                                    "items": [
                                        {
                                            "id": "CONFIG_ENUM_ID_SECRET_SHOULD_NOT_LEAK",
                                            "value_string": "CONFIG_ENUM_SECRET_SHOULD_NOT_LEAK",
                                            "name": "Option A",
                                        },
                                    ],
                                },
                                "default_value": {
                                    "value_string": "CONFIG_DEFAULT_SECRET_SHOULD_NOT_LEAK",
                                },
                            },
                            {
                                "id": "generated",
                                "type": "string",
                                "readonly": True,
                                "value_kind": "value_string",
                                "value_string": "server-owned",
                            },
                        ],
                    },
                ],
                "child_units": [
                    {
                        "uid": "hosts/Server/AppDataDetector.Config/VisualElement.1",
                        "type": "VisualElement",
                        "name": "Zone polygon",
                        "properties": [
                            {
                                "id": "zone",
                                "type": "shape",
                                "readonly": False,
                                "value_simple_polygon": {
                                    "points": [
                                        {"x": 0.1, "y": 0.2},
                                        {"x": 0.8, "y": 0.2},
                                        {"x": 0.8, "y": 0.7},
                                    ],
                                },
                            },
                            {
                                "id": "overlayToken",
                                "type": "string",
                                "readonly": False,
                                "value_string": "VISUAL_CONFIG_SECRET_SHOULD_NOT_LEAK",
                            },
                        ],
                    },
                ],
            }
        ]


class FakeDirectConfigStub:
    def __init__(self) -> None:
        self.list_units_requests: list[FakeListUnitsRequest] = []

    def ListUnits(self, request: FakeListUnitsRequest, timeout: float) -> dict[str, Any]:
        self.list_units_requests.append(request)
        if request.kwargs["unit_uids"] != ["hosts/Server/AVDetector.Direct"]:
            return {"units": []}
        return {
            "units": [
                {
                    "uid": "hosts/Server/AVDetector.Direct",
                    "type": "AVDetector",
                    "properties": [
                        {
                            "id": "input",
                            "properties": [
                                {
                                    "id": "detector",
                                    "value_string": "MotionDetection",
                                },
                            ],
                        }
                    ],
                }
            ]
        }


class FakeRealShapedDetectorConfigClient(FakeClient):
    def __init__(self, config: FakeConfig) -> None:
        super().__init__(config)
        self.authenticate_calls = 0
        self.config_stub = FakeDirectConfigStub()

    def authenticate_grpc(self) -> None:
        self.authenticate_calls += 1

    def import_module(self, module_name: str) -> Any:
        if module_name == "axxonsoft.bl.config.ConfigurationService_pb2":
            return FakeConfigPb
        raise AssertionError(module_name)

    def common_stubs(self) -> dict[str, Any]:
        return {"config": self.config_stub}

    def message_to_dict(self, message: Any) -> dict[str, Any]:
        return message if isinstance(message, dict) else {}


class FakeEndpointRef:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakePullMetadataRequest:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeMetadataPb:
    PullMetadataRequest = FakePullMetadataRequest


class FakeMediaPb:
    EndpointRef = FakeEndpointRef


class FakeMetadataStub:
    def __init__(self, responses: list[dict[str, Any]], error: Exception | None = None) -> None:
        self.responses = responses
        self.error = error
        self.requests: list[FakePullMetadataRequest] = []
        self.timeouts: list[float] = []

    def PullMetadata(self, requests: Any, timeout: float) -> Any:
        self.requests.extend(list(requests))
        self.timeouts.append(timeout)

        def iterator() -> Any:
            for response in self.responses:
                yield response
            if self.error is not None:
                raise self.error

        return iterator()


class FakeMetadataClient(FakeClient):
    def __init__(
        self,
        config: FakeConfig,
        responses: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(config)
        self.authenticate_calls = 0
        self.stub = FakeMetadataStub(responses or [], error)

    def authenticate_grpc(self) -> None:
        self.authenticate_calls += 1

    def import_module(self, module_name: str) -> Any:
        if module_name == "axxonsoft.bl.metadata.MetadataService_pb2":
            return FakeMetadataPb
        if module_name == "axxonsoft.bl.media.Media_pb2":
            return FakeMediaPb
        raise AssertionError(module_name)

    def stub_from_proto(self, proto_path: str, service_name: str) -> FakeMetadataStub:
        self.proto_path = proto_path
        self.service_name = service_name
        return self.stub

    def message_to_dict(self, message: Any) -> dict[str, Any]:
        return message if isinstance(message, dict) else {}

    def sanitize(self, value: Any) -> Any:
        redacted = importlib.import_module("axxon_mcp_detector_archive").redact_sensitive_properties(value)
        if isinstance(redacted, dict):
            return {"sanitized": True, **redacted}
        return redacted


class FakeMetadataCatalogClient(FakeClient):
    def metadata_endpoints(self) -> list[str]:
        return [
            "hosts/Server/AVDetector.Live/SourceEndpoint.metadata",
            "hosts/Server/AVDetector.Live/SourceEndpoint.metadata",
        ]


class FakeInventoryMetadataCatalogClient(FakeClient):
    def load_inventory(self) -> dict[str, Any]:
        return {
            "items": [
                {"access_point": "hosts/Server/AVDetector.Inventory/SourceEndpoint.vmda"},
                {"access_point": "hosts/Server/AVDetector.Inventory/SourceEndpoint.Video"},
            ],
        }


class FakeFailingInventoryMetadataCatalogClient(FakeClient):
    def load_inventory(self) -> dict[str, Any]:
        raise RuntimeError("inventory offline")


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

    def test_sensitive_property_redaction_carries_context_into_nested_descriptor_values(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        raw: dict[str, Any] = {
            "properties": [
                {
                    "id": "apiToken",
                    "name": "API token",
                    "type": "string",
                    "value_kind": "value_string",
                    "value_string": "DIRECT_SECRET_SHOULD_NOT_LEAK",
                    "enum_constraint": {
                        "items": [
                            {
                                "id": "ENUM_ID_SECRET_SHOULD_NOT_LEAK",
                                "value_string": "ENUM_SECRET_SHOULD_NOT_LEAK",
                                "name": "Option A",
                            },
                        ],
                    },
                    "default_value": {
                        "value_string": "DEFAULT_SECRET_SHOULD_NOT_LEAK",
                    },
                    "history": [
                        {
                            "id": "HISTORY_ID_SECRET_SHOULD_NOT_LEAK",
                            "value_bytes": "HISTORY_SECRET_SHOULD_NOT_LEAK",
                        },
                    ],
                },
                {
                    "id": "display_mode",
                    "name": "Display mode",
                    "type": "string",
                    "value_kind": "value_string",
                    "value_string": "visible",
                    "enum_constraint": {
                        "items": [
                            {
                                "id": "visible-id",
                                "value_string": "visible",
                                "name": "Visible",
                            },
                        ],
                    },
                },
            ],
        }

        redacted = module.redact_sensitive_properties(raw)

        token = redacted["properties"][0]
        self.assertEqual(token["id"], "apiToken")
        self.assertEqual(token["name"], "API token")
        self.assertEqual(token["type"], "string")
        self.assertEqual(token["value_kind"], "value_string")
        self.assertEqual(token["value_string"], "<redacted>")
        self.assertEqual(token["enum_constraint"]["items"][0]["id"], "<redacted>")
        self.assertEqual(token["enum_constraint"]["items"][0]["value_string"], "<redacted>")
        self.assertEqual(token["enum_constraint"]["items"][0]["name"], "Option A")
        self.assertEqual(token["default_value"]["value_string"], "<redacted>")
        self.assertEqual(token["history"][0]["id"], "<redacted>")
        self.assertEqual(token["history"][0]["value_bytes"], "<redacted>")

        display = redacted["properties"][1]
        self.assertEqual(display["value_kind"], "value_string")
        self.assertEqual(display["value_string"], "visible")
        self.assertEqual(display["enum_constraint"]["items"][0]["id"], "visible-id")
        self.assertEqual(display["enum_constraint"]["items"][0]["value_string"], "visible")
        self.assertNotIn("DIRECT_SECRET_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("ENUM_ID_SECRET_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("ENUM_SECRET_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("DEFAULT_SECRET_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("HISTORY_ID_SECRET_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("HISTORY_SECRET_SHOULD_NOT_LEAK", str(redacted))

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

    def test_detector_kind_catalog_reads_real_client_template_units_without_helper_methods(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        fake = FakeRealShapedDetectorCatalogClient(FakeConfig())
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        catalog = archive.detector_kind_catalog(include_live=True)

        self.assertEqual(len(fake.config_stub.list_templates_requests), 1)
        self.assertEqual(fake.config_stub.list_templates_requests[0].kwargs, {"view": "VIEW_MODE_FULL"})
        av_by_kind = {entry["detector_kind"]: entry for entry in catalog["by_unit_type"]["AVDetector"]}
        self.assertEqual(av_by_kind["Loitering"]["provenance"], ["template"])

    def test_detector_parameter_schema_flattens_nested_descriptors_and_constraints(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorSchemaClient(config),
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_parameter_schema("AppDataDetector", "MoveInZone")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "detector_parameter_schema")
        self.assertEqual(result["unit_type"], "AppDataDetector")
        self.assertEqual(result["detector_kind"], "MoveInZone")
        self.assertEqual(result["source_type"], "TargetList")
        self.assertEqual(result["provenance"], ["live-unit"])
        self.assertEqual(result["fixtures"]["required"], ["video_source_ap", "vmda_source_ap"])
        properties = result["schema"]["properties"]
        self.assertIn("input.detector", properties)
        self.assertIn("input.camera_ref.streaming_id", properties)
        self.assertIn("advanced.sensitivity", properties)

        detector = properties["input.detector"]
        self.assertEqual(detector["id"], "detector")
        self.assertEqual(detector["path"], "input.detector")
        self.assertEqual(detector["value_kind"], "value_string")
        self.assertFalse(detector["readonly"])
        self.assertFalse(detector["internal"])
        self.assertEqual(detector["enum"], ["MoveInZone", "LongInZone"])
        self.assertEqual(detector["enum_choices"][0]["name"], "Move in zone")

        sensitivity = properties["advanced.sensitivity"]
        self.assertEqual(sensitivity["value_kind"], "value_int32")
        self.assertEqual(sensitivity["range"]["min_int"], 0)
        self.assertEqual(sensitivity["range"]["max_int"], 100)

    def test_detector_parameter_schema_matches_selected_kind_not_advertised_enum_choices(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorSchemaClient(config),
            config_factory=lambda: FakeConfig(),
        )

        selected = archive.detector_parameter_schema("AppDataDetector", "MoveInZone")
        advertised = archive.detector_parameter_schema("AppDataDetector", "LongInZone")

        self.assertEqual(selected["status"], "ok")
        self.assertEqual(advertised["status"], "fixture-needed")
        self.assertIn("LongInZone", advertised["message"])

    def test_detector_parameter_schema_reports_visual_elements_without_sensitive_values(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorSchemaClient(config),
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_parameter_schema("AppDataDetector", "MoveInZone")

        self.assertEqual(len(result["visual_elements"]), 1)
        visual = result["visual_elements"][0]
        self.assertEqual(visual["uid"], "hosts/Server/AppDataDetector.Schema/VisualElement.1")
        self.assertEqual(visual["type"], "VisualElement")
        self.assertEqual(visual["shape_fields"], ["value_simple_polygon"])
        self.assertEqual(visual["properties"][0]["id"], "polyline")
        self.assertEqual(visual["properties"][0]["value_kind"], "value_simple_polygon")
        self.assertNotIn("VISUAL_SECRET_SHOULD_NOT_LEAK", str(result))

    def test_detector_parameter_schema_redacts_sensitive_property_values(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorSchemaClient(config),
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_parameter_schema("AppDataDetector", "MoveInZone")

        token = result["schema"]["properties"]["advanced.apiToken"]
        self.assertEqual(token["id"], "apiToken")
        self.assertEqual(token["value_kind"], "value_string")
        self.assertNotIn("enum", token)
        self.assertNotIn("enum_choices", token)
        self.assertNotIn("SCHEMA_SECRET_SHOULD_NOT_LEAK", str(result))
        self.assertNotIn("ENUM_SECRET_SHOULD_NOT_LEAK", str(result))

    def test_detector_config_get_returns_sanitized_config_snapshot_and_writable_summaries(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        fake = FakeDetectorConfigClient(FakeConfig())
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_config_get(FakeDetectorConfigClient.detector_uid)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "detector_config_get")
        self.assertEqual(result["detector_uid"], FakeDetectorConfigClient.detector_uid)
        self.assertEqual(result["unit_type"], "AppDataDetector")
        self.assertEqual(result["detector_kind"], "MoveInZone")
        self.assertEqual(result["source_type"], "TargetList")
        self.assertEqual(fake.list_units_calls, ["AppDataDetector"])

        self.assertEqual(result["config"]["display_name"], "Zone watcher")
        self.assertNotIn("CONFIG_SECRET_SHOULD_NOT_LEAK", str(result))
        self.assertNotIn("VISUAL_CONFIG_SECRET_SHOULD_NOT_LEAK", str(result))

        writable = {item["path"]: item for item in result["writable_parameters"]}
        self.assertEqual(writable["input.detector"]["value"], "MoveInZone")
        self.assertEqual(writable["advanced.sensitivity"]["value"], 55)
        self.assertEqual(writable["advanced.apiToken"]["value"], "<redacted>")
        self.assertNotIn("advanced.generated", writable)

        token_config = result["config"]["properties"][1]["properties"][1]
        self.assertEqual(token_config["id"], "apiToken")
        self.assertEqual(token_config["value_string"], "<redacted>")
        self.assertEqual(token_config["enum_constraint"]["items"][0]["id"], "<redacted>")
        self.assertEqual(token_config["enum_constraint"]["items"][0]["value_string"], "<redacted>")
        self.assertEqual(token_config["enum_constraint"]["items"][0]["name"], "Option A")
        self.assertEqual(token_config["default_value"]["value_string"], "<redacted>")
        self.assertEqual(token_config["value_kind"], "value_string")
        self.assertNotIn("CONFIG_ENUM_ID_SECRET_SHOULD_NOT_LEAK", str(result))
        self.assertNotIn("CONFIG_ENUM_SECRET_SHOULD_NOT_LEAK", str(result))
        self.assertNotIn("CONFIG_DEFAULT_SECRET_SHOULD_NOT_LEAK", str(result))

        self.assertEqual(len(result["visual_elements"]), 1)
        visual = result["visual_elements"][0]
        self.assertEqual(visual["uid"], "hosts/Server/AppDataDetector.Config/VisualElement.1")
        self.assertEqual(visual["path"], "VisualElement.1")
        self.assertEqual(visual["type"], "VisualElement")
        self.assertEqual(visual["shape_fields"], ["value_simple_polygon"])

        snapshot = result["snapshot_metadata"]
        self.assertEqual(snapshot["detector_uid"], FakeDetectorConfigClient.detector_uid)
        self.assertEqual(snapshot["unit_type"], "AppDataDetector")
        self.assertEqual(snapshot["detector_kind"], "MoveInZone")
        self.assertEqual(snapshot["config_source"], "list_units")
        self.assertEqual(snapshot["rollback_key"], f"detector_config:{FakeDetectorConfigClient.detector_uid}")

    def test_detector_visual_elements_lists_editable_visual_children(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorConfigClient(config),
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_visual_elements(FakeDetectorConfigClient.detector_uid)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "detector_visual_elements")
        self.assertEqual(result["detector_uid"], FakeDetectorConfigClient.detector_uid)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["visual_elements"][0]["path"], "VisualElement.1")
        self.assertEqual(result["visual_elements"][0]["shape_fields"], ["value_simple_polygon"])
        self.assertEqual(result["visual_elements"][0]["properties"][0]["path"], "zone")
        self.assertNotIn("VISUAL_CONFIG_SECRET_SHOULD_NOT_LEAK", str(result))

    def test_detector_config_get_reads_real_client_unit_by_uid_with_configuration_service(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        fake = FakeRealShapedDetectorConfigClient(FakeConfig())
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_config_get("hosts/Server/AVDetector.Direct")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["detector_uid"], "hosts/Server/AVDetector.Direct")
        self.assertEqual(result["unit_type"], "AVDetector")
        self.assertEqual(result["detector_kind"], "MotionDetection")
        self.assertEqual(fake.authenticate_calls, 1)
        self.assertEqual(
            [request.kwargs for request in fake.config_stub.list_units_requests],
            [{"unit_uids": ["hosts/Server/AVDetector.Direct"]}],
        )
        self.assertEqual(result["snapshot_metadata"]["config_source"], "configuration_service.ListUnits")

    def test_detector_config_get_returns_fixture_needed_for_missing_detector_uid(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorConfigClient(config),
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_config_get("hosts/Server/AppDataDetector.Missing")

        self.assertEqual(result["status"], "fixture-needed")
        self.assertEqual(result["tool"], "detector_config_get")
        self.assertEqual(result["detector_uid"], "hosts/Server/AppDataDetector.Missing")
        self.assertIn("AppDataDetector.Missing", result["message"])

        visual_result = archive.detector_visual_elements("hosts/Server/AppDataDetector.Missing")
        self.assertEqual(visual_result["status"], "fixture-needed")
        self.assertEqual(visual_result["tool"], "detector_visual_elements")
        self.assertEqual(visual_result["detector_uid"], "hosts/Server/AppDataDetector.Missing")

    def test_detector_parameter_schema_returns_fixture_needed_for_unresolved_kind(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeDetectorSchemaClient(config),
            config_factory=lambda: FakeConfig(),
        )

        result = archive.detector_parameter_schema("AppDataDetector", "NotInFixtures")

        self.assertEqual(result["status"], "fixture-needed")
        self.assertEqual(result["tool"], "detector_parameter_schema")
        self.assertEqual(result["unit_type"], "AppDataDetector")
        self.assertEqual(result["detector_kind"], "NotInFixtures")
        self.assertEqual(result["fixtures"]["required"], ["video_source_ap", "vmda_source_ap"])
        self.assertEqual(result["fixtures"]["missing"], ["video_source_ap", "vmda_source_ap"])
        self.assertIn("NotInFixtures", result["message"])

    def test_metadata_schema_catalog_returns_proto_schema_and_endpoint_examples(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeMetadataCatalogClient(config),
            config_factory=lambda: FakeConfig(),
        )

        catalog = archive.metadata_schema_catalog()

        self.assertEqual(catalog["status"], "ok")
        self.assertEqual(catalog["tool"], "metadata_schema_catalog")
        self.assertIn("fallback", catalog["schema_source"])
        schemas = catalog["schemas"]
        for name in ("PullMetadataResponse", "MetadataSample", "Tracklets", "GlobalTracklets", "Tracklet"):
            self.assertIn(name, schemas)

        response_fields = {field["name"]: field for field in schemas["PullMetadataResponse"]["fields"]}
        self.assertEqual(response_fields["sample"]["type"], "MetadataSample")
        self.assertEqual(response_fields["sample"]["oneof"], "data")
        self.assertEqual(response_fields["config_update"]["type"], "StreamConfig")

        sample_fields = {field["name"]: field for field in schemas["MetadataSample"]["fields"]}
        self.assertEqual(sample_fields["tracklets"]["type"], "Tracklets")
        self.assertEqual(sample_fields["tracklets"]["oneof"], "data")
        self.assertEqual(sample_fields["global_tracklets"]["type"], "GlobalTracklets")

        tracklets_fields = {field["name"]: field for field in schemas["Tracklets"]["fields"]}
        self.assertTrue(tracklets_fields["tracklets"]["repeated"])
        self.assertEqual(tracklets_fields["tracklets"]["type"], "Tracklet")

        endpoints = [item["access_point"] for item in catalog["endpoint_examples"]]
        self.assertIn("hosts/Server/AVDetector.Live/SourceEndpoint.metadata", endpoints)
        self.assertIn("hosts/Server/AVDetector.1/SourceEndpoint.vmda", endpoints)
        self.assertEqual(len(endpoints), len(set(endpoints)))
        self.assertNotIn("CONFIG_VALUE_SHOULD_NOT_LEAK", str(catalog))

        inventory_archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeInventoryMetadataCatalogClient(config),
            config_factory=lambda: FakeConfig(),
        )
        inventory_catalog = inventory_archive.metadata_schema_catalog()
        inventory_endpoints = [item["access_point"] for item in inventory_catalog["endpoint_examples"]]
        self.assertIn("hosts/Server/AVDetector.Inventory/SourceEndpoint.vmda", inventory_endpoints)

    def test_metadata_schema_catalog_returns_fallback_without_env_credentials(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        client_factory_calls: list[Any] = []

        def missing_credentials_config_factory() -> FakeConfig:
            raise ValueError("password is required")

        def client_factory(config: FakeConfig) -> FakeClient:
            client_factory_calls.append(config)
            return FakeClient(config)

        archive = module.AxxonMcpDetectorArchive(
            client_factory=client_factory,
            config_factory=missing_credentials_config_factory,
        )

        catalog = archive.metadata_schema_catalog()

        self.assertEqual(catalog["status"], "ok")
        self.assertIn("fallback", catalog["schema_source"])
        self.assertIn("PullMetadataResponse", catalog["schemas"])
        self.assertIn("MetadataSample", catalog["schemas"])
        self.assertIn("Tracklets", catalog["schemas"])
        endpoints = [item["access_point"] for item in catalog["endpoint_examples"]]
        self.assertEqual(endpoints, ["hosts/Server/AVDetector.1/SourceEndpoint.vmda"])
        self.assertEqual(client_factory_calls, [])
        self.assertIsNone(archive.client)

    def test_metadata_schema_catalog_ignores_live_inventory_errors(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeFailingInventoryMetadataCatalogClient(config),
            config_factory=lambda: FakeConfig(),
        )

        catalog = archive.metadata_schema_catalog()

        self.assertEqual(catalog["status"], "ok")
        self.assertIn("fallback", catalog["schema_source"])
        endpoints = [item["access_point"] for item in catalog["endpoint_examples"]]
        self.assertEqual(endpoints, ["hosts/Server/AVDetector.1/SourceEndpoint.vmda"])
        self.assertNotIn("inventory offline", str(catalog))

    def test_metadata_sample_bounded_clamps_requested_caps_and_stops_at_limit(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        responses = [
            {"sample": {"timestamp": f"t-{index}", "tracklets": {"tracklets": []}}}
            for index in range(module.METADATA_SAMPLE_LIMIT_CAP + 5)
        ]
        fake = FakeMetadataClient(FakeConfig(), responses=responses)
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = archive.metadata_sample_bounded(
            "hosts/Server/AVDetector.1/SourceEndpoint.vmda",
            timeout_s=999.0,
            limit=999,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "metadata_sample_bounded")
        self.assertEqual(result["requested"], {"timeout_s": 999.0, "limit": 999})
        self.assertEqual(result["applied"]["timeout_s"], module.METADATA_SAMPLE_TIMEOUT_CAP)
        self.assertEqual(result["applied"]["limit"], module.METADATA_SAMPLE_LIMIT_CAP)
        self.assertEqual(result["count"], module.METADATA_SAMPLE_LIMIT_CAP)
        self.assertEqual(len(result["frames"]), module.METADATA_SAMPLE_LIMIT_CAP)
        self.assertTrue(all(frame["sanitized"] for frame in result["frames"]))
        self.assertEqual(fake.authenticate_calls, 1)
        self.assertEqual(fake.proto_path, "axxonsoft/bl/metadata/MetadataService.proto")
        self.assertEqual(fake.service_name, "MetadataService")
        self.assertEqual(fake.stub.timeouts, [module.METADATA_SAMPLE_TIMEOUT_CAP])
        request = fake.stub.requests[0]
        self.assertEqual(request.kwargs["count"], module.METADATA_SAMPLE_LIMIT_CAP)
        self.assertEqual(request.kwargs["endpoint"].kwargs["access_point"], "hosts/Server/AVDetector.1/SourceEndpoint.vmda")

    def test_metadata_sample_bounded_reports_transport_errors_with_partial_frames(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        fake = FakeMetadataClient(
            FakeConfig(),
            responses=[{"sample": {"timestamp": "t-1"}, "apiToken": "TOKEN_VALUE_SHOULD_NOT_LEAK"}],
            error=RuntimeError("metadata stream failed " + ("x" * 500)),
        )
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = archive.metadata_sample_bounded(
            "hosts/Server/AVDetector.1/SourceEndpoint.vmda",
            timeout_s=0,
            limit=2,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["tool"], "metadata_sample_bounded")
        self.assertEqual(result["requested"], {"timeout_s": 0, "limit": 2})
        self.assertEqual(result["applied"], {"timeout_s": 1.0, "limit": 2})
        self.assertLessEqual(len(result["message"]), 240)
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["frames"]), 1)
        self.assertEqual(result["frames"][0]["apiToken"], "<redacted>")
        self.assertNotIn("TOKEN_VALUE_SHOULD_NOT_LEAK", str(result))


if __name__ == "__main__":
    unittest.main()
