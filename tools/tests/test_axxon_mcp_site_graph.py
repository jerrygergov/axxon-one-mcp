from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

module = importlib.import_module("axxon_mcp_site_graph")

CAM_AP = "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"
CAM_SOURCE_AP = "hosts/Server/DeviceIpint.1/Sources/src.0"
ARCHIVE_AP = "hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage"
ARCHIVE_SOURCE_AP = "hosts/Server/MultimediaStorage.AliceBlue/Sources/src.archive0"
DETECTOR_UID = "hosts/Server/AVDetector.5"
APPDATA_UID = "hosts/Server/AppDataDetector.7"
EVENT_SUPPLIER_AP = f"{APPDATA_UID}/EventSupplier"
METADATA_AP = f"{DETECTOR_UID}/SourceEndpoint.vmda"

SECRET_PASSWORD = "SITE_GRAPH_PASSWORD_SHOULD_NOT_LEAK"
SECRET_TOKEN = "SITE_GRAPH_TOKEN_SHOULD_NOT_LEAK"
SECRET_CA = "SITE_GRAPH_CA_SHOULD_NOT_LEAK"
SECRET_LICENSE = "SITE_GRAPH_LICENSE_SHOULD_NOT_LEAK"
SECRET_SERIAL = "SITE_GRAPH_SERIAL_SHOULD_NOT_LEAK"
SECRET_MEDIA = "SITE_GRAPH_MEDIA_SHOULD_NOT_LEAK"


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = SECRET_PASSWORD
    tls_cn = "Server"
    ca = Path(f"/tmp/{SECRET_CA}.crt")
    timeout = 7.0


class FakeSiteGraphClient:
    config = FakeConfig()

    def __init__(self) -> None:
        self.load_count = 0
        self.inventory = {
            "nodes": [{"node_name": "Server", "display_name": "Main Server"}],
            "cameras": [
                {
                    "access_point": CAM_AP,
                    "display_name": "Lobby",
                    "enabled": True,
                    "source_access_point": CAM_SOURCE_AP,
                    "archive_access_point": ARCHIVE_AP,
                    "serial_number": SECRET_SERIAL,
                    "password": SECRET_PASSWORD,
                }
            ],
            "archives": [
                {
                    "access_point": ARCHIVE_AP,
                    "display_name": "Main archive",
                    "enabled": True,
                    "source_access_point": ARCHIVE_SOURCE_AP,
                }
            ],
            "components": [
                {"access_point": CAM_SOURCE_AP},
                {"access_point": ARCHIVE_SOURCE_AP},
                {"access_point": EVENT_SUPPLIER_AP},
                {"access_point": EVENT_SUPPLIER_AP},
                {"access_point": METADATA_AP},
            ],
            "host_unit": {
                "units": [
                    {
                        "uid": DETECTOR_UID,
                        "type": "AVDetector",
                        "display_name": "Motion detector",
                        "camera_access_point": CAM_AP,
                        "event_supplier": EVENT_SUPPLIER_AP,
                        "metadata_endpoint": METADATA_AP,
                    },
                    {
                        "uid": APPDATA_UID,
                        "type": "AppDataDetector",
                        "display_name": "Line crossing",
                        "camera_access_point": CAM_AP,
                        "event_supplier": EVENT_SUPPLIER_AP,
                    },
                ]
            },
            "raw_media_bytes": SECRET_MEDIA.encode("ascii"),
            "authorization": f"Bearer {SECRET_TOKEN}",
        }

    def load_inventory(self) -> dict:
        self.load_count += 1
        return self.inventory

    def sanitize(self, value):
        return value

    def list_layouts(self, view: str = "VIEW_MODE_ONLY_META") -> dict:
        return {
            "status": 200,
            "body": {
                "items": [
                    {
                        "meta": {"layout_id": "layout-main", "etag": "layout-etag"},
                        "body": {
                            "id": "layout-main",
                            "display_name": "Operator layout",
                            "map_id": "map-main",
                            "cells": {
                                "1": {"access_point": CAM_AP},
                                "2": {"access_point": DETECTOR_UID},
                            },
                        },
                    }
                ]
            },
        }

    def list_maps(self) -> dict:
        return {
            "status": 200,
            "body": {
                "items": [
                    {
                        "meta": {
                            "id": "map-main",
                            "name": "Floor plan",
                            "type": "MAP_TYPE_RASTER",
                            "etag": "map-etag",
                            "image_etag": "image-etag",
                        },
                        "image": {"data": SECRET_MEDIA},
                    }
                ]
            },
        }

    def get_markers(self, map_id: str) -> dict:
        self.last_marker_map = map_id
        return {
            "status": 200,
            "body": {
                "markers": [
                    {
                        "id": "marker-camera",
                        "access_point": CAM_AP,
                        "position": {"x": 0.5, "y": 0.25},
                        "marker_type": "MARKER_TYPE_CAMERA",
                    },
                    {
                        "id": "marker-camera",
                        "access_point": CAM_AP,
                        "position": {"x": 0.5, "y": 0.25},
                        "marker_type": "MARKER_TYPE_CAMERA",
                    },
                ]
            },
        }

    def security_inventory(self) -> dict:
        return {
            "status": "ok",
            "roles": {"count": 1, "items": [{"role_id": "role-admin", "name": "Administrators"}]},
            "users": {
                "count": 1,
                "items": [
                    {
                        "user_id": "user-root",
                        "login": "root",
                        "enabled": True,
                        "role_ids": ["role-admin"],
                        "token": SECRET_TOKEN,
                    }
                ],
            },
        }

    def role_permissions(self, role_id: str, page_size: int = 50) -> dict:
        return {
            "status": "ok",
            "role_id": role_id,
            "objects": {"count": 1, "items": [{"id": CAM_AP, "display_name": "Lobby camera"}]},
        }

    def system_health(self) -> dict:
        return {
            "status": "ok",
            "security": {"status": "ok", "roles_count": 1, "users_count": 1},
            "license": {"domain": {"key": SECRET_LICENSE}, "host_info": {"serialNumber": SECRET_SERIAL}},
            "session": {"connected": True, "authorization": f"Bearer {SECRET_TOKEN}"},
        }


class FailingOptionalClient(FakeSiteGraphClient):
    def list_maps(self) -> dict:
        raise RuntimeError(f"map fixture unavailable token={SECRET_TOKEN}")


class AxxonMcpSiteGraphTests(unittest.TestCase):
    def test_connect_env_profile_is_lazy_and_redacted(self) -> None:
        constructed: list[str] = []

        def factory(_config):
            constructed.append("client")
            return FakeSiteGraphClient()

        graph = module.AxxonMcpSiteGraph(client_factory=factory, config_factory=lambda: FakeConfig())
        self.assertIsNone(graph.client)

        gap = graph.site_graph_connect_axxon_profile("named-profile")
        self.assertEqual(gap["status"], "gap")
        self.assertEqual(constructed, [])

        connected = graph.site_graph_connect_axxon_profile("env")
        self.assertTrue(connected["connected"])
        self.assertEqual(connected["mode"], "read-only")
        self.assertEqual(constructed, ["client"])
        self.assertTrue(connected["profile"]["password_present"])
        self.assertNotIn(SECRET_PASSWORD, str(connected))
        self.assertNotIn(SECRET_CA, str(connected))

    def test_build_graph_joins_inventory_layouts_maps_security_and_health(self) -> None:
        client = FakeSiteGraphClient()
        out = module.build_site_graph(client)

        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "build_site_graph")
        self.assertEqual(out["summary"]["cameras"], 1)
        self.assertEqual(out["summary"]["archives"], 1)
        self.assertEqual(out["summary"]["detectors"], 1)
        self.assertEqual(out["summary"]["appdata_detectors"], 1)
        self.assertEqual(out["summary"]["layouts"], 1)
        self.assertEqual(out["summary"]["maps"], 1)
        self.assertEqual(out["summary"]["markers"], 1)
        self.assertEqual(out["summary"]["event_suppliers"], 1)
        self.assertEqual(out["summary"]["metadata_endpoints"], 1)
        self.assertEqual(out["summary"]["permissions_roles"], 1)
        self.assertEqual(out["summary"]["health_sections"], 3)
        self.assertEqual(out["summary"]["node_count"], len(out["nodes"]))
        self.assertEqual(out["summary"]["edge_count"], len(out["edges"]))

        node_ids = {node["id"] for node in out["nodes"]}
        for expected in (CAM_AP, ARCHIVE_AP, DETECTOR_UID, APPDATA_UID, "layout-main", "map-main", "role-admin"):
            self.assertIn(expected, node_ids)

        edge_types = {edge["type"] for edge in out["edges"]}
        for expected in (
            "host_contains",
            "camera_uses_source",
            "camera_records_to_archive",
            "camera_has_detector",
            "detector_emits_event",
            "detector_has_metadata",
            "layout_uses_map",
            "layout_references",
            "map_contains_marker",
            "marker_points_to",
            "user_has_role",
            "role_grants_object",
            "health_reports",
        ):
            self.assertIn(expected, edge_types)

        for edge in out["edges"]:
            self.assertIn("source", edge)
            self.assertIn("target", edge)
            self.assertIn("type", edge)

    def test_deduplicates_access_points_event_suppliers_and_markers(self) -> None:
        out = module.build_site_graph(FakeSiteGraphClient())

        self.assertEqual(out["collections"]["event_suppliers"], [EVENT_SUPPLIER_AP])
        self.assertEqual(out["summary"]["event_suppliers"], 1)
        self.assertEqual(out["collections"]["access_points"].count(EVENT_SUPPLIER_AP), 1)
        self.assertEqual([marker["marker_id"] for marker in out["collections"]["markers"]], ["marker-camera"])

    def test_partial_section_failure_warns_without_dropping_inventory(self) -> None:
        out = module.build_site_graph(FailingOptionalClient())

        self.assertEqual(out["status"], "warn")
        self.assertEqual(out["summary"]["cameras"], 1)
        self.assertEqual(out["collections"]["cameras"][0]["access_point"], CAM_AP)
        self.assertIn("maps", out["source_sections"])
        self.assertEqual(out["source_sections"]["maps"]["status"], "fixture-needed")
        self.assertTrue(any(gap["section"] == "maps" for gap in out["gaps"]))
        self.assertNotIn(SECRET_TOKEN, str(out))

    def test_redacts_secret_like_fields_and_raw_bytes(self) -> None:
        graph = module.AxxonMcpSiteGraph(
            client_factory=lambda _config: FakeSiteGraphClient(),
            config_factory=lambda: FakeConfig(),
        )
        out = graph.build_site_graph()
        text = str(out)

        for secret in (
            SECRET_PASSWORD,
            SECRET_TOKEN,
            SECRET_CA,
            SECRET_LICENSE,
            SECRET_SERIAL,
            SECRET_MEDIA,
        ):
            self.assertNotIn(secret, text)
        self.assertIn("raw_media_bytes", text)
        self.assertIn("byte_count", text)

    def test_tool_names_exported(self) -> None:
        self.assertEqual(
            module.SITE_GRAPH_TOOL_NAMES,
            ("site_graph_connect_axxon_profile", "build_site_graph"),
        )


if __name__ == "__main__":
    unittest.main()
