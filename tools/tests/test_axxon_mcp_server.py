from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeFastMCP:
    def __init__(self, name: str, **kwargs: object) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}

    def tool(self, name: str | None = None, **_kwargs: object):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator

    def resource(self, uri: str, **_kwargs: object):
        def decorator(func):
            self.resources[uri] = func
            return func

        return decorator


class StubDocs:
    def search_api_docs(self, query: str, *, limit: int = 10):
        return {"query": query, "limit": limit}

    def get_api_method(self, fqmn: str):
        return {"fqmn": fqmn}

    def get_http_endpoint(self, path_or_topic: str):
        return {"path_or_topic": path_or_topic}

    def get_verified_example(self, topic: str):
        return {"topic": topic}

    def explain_task_recipe(self, task: str):
        return {"task": task}

    def list_remaining_gaps(self):
        return {"gaps": []}


class StubLive:
    def connect_axxon_profile(self, profile: str = "env"):
        return {"profile": profile}

    def list_cameras(self, filter_text: str | None = None, limit: int = 100):
        return {"kind": "cameras", "filter_text": filter_text, "limit": limit}

    def list_archives(self, filter_text: str | None = None, limit: int = 100):
        return {"kind": "archives", "filter_text": filter_text, "limit": limit}

    def list_config_units(self, filter_text: str | None = None, limit: int = 100):
        return {"kind": "config_units", "filter_text": filter_text, "limit": limit}

    def list_detectors(self, camera_or_host: str | None = None, limit: int = 100):
        return {"kind": "detectors", "camera_or_host": camera_or_host, "limit": limit}

    def list_appdata_detectors(self, camera_or_host: str | None = None, limit: int = 100):
        return {"kind": "appdata_detectors", "camera_or_host": camera_or_host, "limit": limit}

    def find_event_suppliers(self, camera_or_detector: str | None = None, limit: int = 100):
        return {"kind": "event_suppliers", "camera_or_detector": camera_or_detector, "limit": limit}

    def find_metadata_endpoints(self, camera_or_detector: str | None = None, limit: int = 100):
        return {"kind": "metadata_endpoints", "camera_or_detector": camera_or_detector, "limit": limit}

    def preflight_task(self, task: str):
        return {"task": task}

    def get_archive_intervals(self, camera: str, hours: float = 1.0, max_count: int = 32, min_gap_ms: int = 1000):
        return {"camera": camera, "hours": hours, "max_count": max_count, "min_gap_ms": min_gap_ms}

    def subscribe_events_bounded(self, subjects=None, event_types=None, timeout: float = 5.0, limit: int = 25):
        return {"subjects": subjects or [], "event_types": event_types or [], "timeout": timeout, "limit": limit}


class StubOperator:
    def known_workflows(self):
        return ["temp_camera"]

    def plan(self, workflow, params):
        return {"plan_id": "plan-test", "workflow": workflow, "params": dict(params or {}), "status": "planned"}

    def apply(self, plan_id, confirmation):
        return {"status": "applied", "plan_id": plan_id, "confirmation": confirmation, "created_uids": []}

    def verify(self, plan_id):
        return {"status": "verified", "plan_id": plan_id, "still_present": []}

    def rollback(self, plan_id, confirmation):
        return {"status": "rolled_back", "plan_id": plan_id, "confirmation": confirmation}

    def audit_log(self):
        return [{"action": "plan", "plan_id": "plan-test"}]


class AxxonMcpServerTests(unittest.TestCase):
    def test_create_server_registers_phase_one_tools_and_resources(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        server = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)

        self.assertEqual(server.name, "Axxon One API Docs")
        self.assertEqual(
            set(server.tools),
            {
                "search_api_docs",
                "get_api_method",
                "get_http_endpoint",
                "get_verified_example",
                "explain_task_recipe",
                "list_remaining_gaps",
            },
        )
        self.assertIn("axxon://mcp-corpus/{name}", server.resources)
        self.assertIn("axxon://coverage/gaps", server.resources)

        self.assertEqual(server.tools["search_api_docs"]("camera", 3), {"query": "camera", "limit": 3})
        self.assertEqual(server.tools["get_api_method"]("DomainService.ListCameras"), {"fqmn": "DomainService.ListCameras"})
        self.assertEqual(server.resources["axxon://coverage/gaps"](), {"gaps": []})

    def test_create_server_registers_live_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        self.assertNotIn("connect_axxon_profile", docs_only.tools)

        server = module.create_server(docs=StubDocs(), live=StubLive(), fastmcp_factory=FakeFastMCP)
        for name in (
            "connect_axxon_profile",
            "list_cameras",
            "list_archives",
            "list_config_units",
            "list_detectors",
            "list_appdata_detectors",
            "find_event_suppliers",
            "find_metadata_endpoints",
            "preflight_task",
            "get_archive_intervals",
            "subscribe_events_bounded",
        ):
            self.assertIn(name, server.tools)

        self.assertEqual(server.tools["connect_axxon_profile"]("env"), {"profile": "env"})
        self.assertEqual(server.tools["list_cameras"]("Camera", 5)["limit"], 5)
        intervals = server.tools["get_archive_intervals"]("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", 2.0)
        self.assertEqual(intervals["camera"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(intervals["hours"], 2.0)
        bounded = server.tools["subscribe_events_bounded"](["hosts/Server/AppDataDetector.27/EventSupplier"], ["ET_DETECTOR"], 3.0, 10)
        self.assertEqual(bounded["limit"], 10)

    def test_create_server_registers_operator_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("plan_operator_workflow", "apply_operator_plan", "verify_operator_plan", "rollback_operator_plan"):
            self.assertNotIn(name, docs_only.tools)

        server = module.create_server(docs=StubDocs(), operator=StubOperator(), fastmcp_factory=FakeFastMCP)
        for name in (
            "list_operator_workflows",
            "plan_operator_workflow",
            "apply_operator_plan",
            "verify_operator_plan",
            "rollback_operator_plan",
        ):
            self.assertIn(name, server.tools)
        self.assertIn("axxon://operator/audit-log", server.resources)

        plan = server.tools["plan_operator_workflow"]("temp_camera", {"display_name_hint": "ok"})
        self.assertEqual(plan["workflow"], "temp_camera")
        applied = server.tools["apply_operator_plan"]("plan-test", "CONFIRM-temp_camera")
        self.assertEqual(applied["status"], "applied")
        verified = server.tools["verify_operator_plan"]("plan-test")
        self.assertEqual(verified["status"], "verified")
        rolled = server.tools["rollback_operator_plan"]("plan-test", "CONFIRM-temp_camera-rollback")
        self.assertEqual(rolled["status"], "rolled_back")
        audit = server.resources["axxon://operator/audit-log"]()
        self.assertEqual(audit["entries"][0]["action"], "plan")

    def test_create_server_registers_view_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("live_view", "snapshot_batch", "archive_scrub", "archive_frame", "archive_mjpeg_bounded", "stream_health"):
            self.assertNotIn(name, docs_only.tools)

        class StubView:
            def connect_axxon_profile(self, profile: str = "env"):
                return {"connected": True, "profile_name": profile}

            def live_view(self, camera_access_point, **kwargs):
                return {"status": "ok", "tool": "live_view", "camera": camera_access_point, **kwargs}

            def snapshot_batch(self, camera_access_points, **kwargs):
                return {"status": "ok", "tool": "snapshot_batch", "n": len(camera_access_points), **kwargs}

            def archive_scrub(self, camera_access_point, **kwargs):
                return {"status": "ok", "tool": "archive_scrub", "camera": camera_access_point, **kwargs}

            def archive_frame(self, camera_access_point, ts, **kwargs):
                return {"status": "ok", "tool": "archive_frame", "camera": camera_access_point, "ts": ts, **kwargs}

            def archive_mjpeg_bounded(self, camera_access_point, begin_ts, **kwargs):
                return {"status": "ok", "tool": "archive_mjpeg_bounded", "camera": camera_access_point, "begin_ts": begin_ts, **kwargs}

            def stream_health(self, camera_access_point):
                return {"status": "ok", "tool": "stream_health", "camera": camera_access_point}

        server = module.create_server(docs=StubDocs(), view=StubView(), fastmcp_factory=FakeFastMCP)
        for name in (
            "view_connect_axxon_profile",
            "live_view",
            "snapshot_batch",
            "archive_scrub",
            "archive_frame",
            "archive_mjpeg_bounded",
            "stream_health",
        ):
            self.assertIn(name, server.tools)

        self.assertEqual(server.tools["view_connect_axxon_profile"]("env"), {"connected": True, "profile_name": "env"})
        live = server.tools["live_view"]("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(live["status"], "ok")
        self.assertEqual(live["camera"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        batch = server.tools["snapshot_batch"](["a", "b"])
        self.assertEqual(batch["n"], 2)
        scrub = server.tools["archive_scrub"]("cam", 3)
        self.assertEqual(scrub["hours"], 3)
        frame = server.tools["archive_frame"]("cam", "2026-05-16T10:00:00Z")
        self.assertEqual(frame["ts"], "2026-05-16T10:00:00Z")
        mjpeg = server.tools["archive_mjpeg_bounded"]("cam", "2026-05-16T10:00:00Z", 2, 4, 320)
        self.assertEqual(mjpeg["speed"], 2)
        self.assertEqual(mjpeg["fps"], 4)
        health = server.tools["stream_health"]("cam")
        self.assertEqual(health["camera"], "cam")


if __name__ == "__main__":
    unittest.main()
