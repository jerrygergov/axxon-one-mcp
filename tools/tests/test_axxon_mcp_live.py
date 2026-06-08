from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "secret"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeClient:
    config = FakeConfig()

    def __init__(self) -> None:
        self.load_count = 0
        self.inventory = {
            "version": {"major": 3, "minor": 0},
            "nodes": [{"node_name": "Server"}],
            "cameras": [
                {
                    "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                    "display_name": "Camera 1",
                    "enabled": True,
                    "model": "Virtual",
                    "serial_number": "SHOULD_NOT_LEAK",
                }
            ],
            "archives": [
                {
                    "access_point": "hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage",
                    "display_name": "Main archive",
                    "enabled": True,
                }
            ],
            "components": [
                {"access_point": "hosts/Server/AVDetector.1/SourceEndpoint.vmda"},
                {"access_point": "hosts/Server/AppDataDetector.27/EventSupplier"},
                {"access_point": "hosts/Server/AppDataDetector.27"},
                {"access_point": "hosts/Server/DeviceIpint.1/Sources/src.0"},
                {"access_point": "hosts/Server/MultimediaStorage.AliceBlue/Sources/src.archive0"},
            ],
            "host_unit": {
                "units": [
                    {"uid": "hosts/Server/AVDetector.1", "type": "AVDetector", "display_name": "Tracker"},
                    {
                        "uid": "hosts/Server/AppDataDetector.27",
                        "type": "AppDataDetector",
                        "display_name": "Line crossing",
                    },
                ]
            },
        }

    def load_inventory(self):
        self.load_count += 1
        return self.inventory

    def sanitize(self, value):
        if isinstance(value, dict):
            return {key: ("<redacted>" if key == "serial_number" else self.sanitize(item)) for key, item in value.items()}
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        return value


class AxxonMcpLiveTests(unittest.TestCase):
    def test_live_inspector_summarizes_inventory_without_secrets(self) -> None:
        module = importlib.import_module("axxon_mcp_live")
        fake_client = FakeClient()
        live = module.AxxonMcpLive(client_factory=lambda _config: fake_client, config_factory=lambda: FakeConfig())

        profile = live.connect_axxon_profile("env")
        self.assertTrue(profile["connected"])
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))

        cameras = live.list_cameras()
        self.assertEqual(cameras["count"], 1)
        self.assertEqual(cameras["items"][0]["display_name"], "Camera 1")
        self.assertNotIn("SHOULD_NOT_LEAK", str(cameras))

        archives = live.list_archives()
        self.assertEqual(archives["items"][0]["access_point"], "hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage")

        detectors = live.list_detectors()
        self.assertEqual(detectors["count"], 1)
        self.assertIn("AVDetector.1", detectors["items"][0]["access_point"])

        appdata = live.list_appdata_detectors()
        self.assertEqual(appdata["count"], 2)

        event_suppliers = live.find_event_suppliers("AppDataDetector.27")
        self.assertEqual(event_suppliers["items"][0], "hosts/Server/AppDataDetector.27/EventSupplier")

        metadata = live.find_metadata_endpoints("AVDetector.1")
        self.assertEqual(metadata["items"][0], "hosts/Server/AVDetector.1/SourceEndpoint.vmda")

    def test_preflight_task_reports_fixture_availability(self) -> None:
        module = importlib.import_module("axxon_mcp_live")
        live = module.AxxonMcpLive(client_factory=lambda _config: FakeClient(), config_factory=lambda: FakeConfig())

        detector_preflight = live.preflight_task("subscribe detector events")
        self.assertEqual(detector_preflight["status"], "ready")
        self.assertIn("event_supplier", detector_preflight["available"])

        ptz_preflight = live.preflight_task("move ptz camera")
        self.assertEqual(ptz_preflight["status"], "blocked")
        self.assertIn("ptz", ptz_preflight["missing"])

    def test_get_archive_intervals_returns_bounded_summary(self) -> None:
        module = importlib.import_module("axxon_mcp_live")
        fake = FakeClient()

        intervals_payload = [
            {"begin_time": 1, "end_time": 100, "type": "TT_RECORDING"},
            {"begin_time": 200, "end_time": 300, "type": "TT_RECORDING"},
        ]

        def fake_get_history(*, access_point, begin_time, end_time, max_count, min_gap_ms):
            fake.last_history_call = {
                "access_point": access_point,
                "begin_time": begin_time,
                "end_time": end_time,
                "max_count": max_count,
                "min_gap_ms": min_gap_ms,
            }
            return {"intervals": intervals_payload}

        fake.get_archive_history = fake_get_history  # type: ignore[attr-defined]
        live = module.AxxonMcpLive(client_factory=lambda _config: fake, config_factory=lambda: FakeConfig())
        live.connect_axxon_profile("env")

        result = live.get_archive_intervals(
            camera="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            hours=2.0,
            max_count=8,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["intervals"], intervals_payload)
        self.assertEqual(result["source_access_point"], "hosts/Server/MultimediaStorage.AliceBlue/Sources/src.archive0")
        call = fake.last_history_call
        self.assertEqual(call["access_point"], "hosts/Server/MultimediaStorage.AliceBlue/Sources/src.archive0")
        self.assertEqual(call["max_count"], 8)
        self.assertGreater(call["end_time"], call["begin_time"])

    def test_get_archive_intervals_unknown_camera_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_live")
        live = module.AxxonMcpLive(client_factory=lambda _config: FakeClient(), config_factory=lambda: FakeConfig())
        result = live.get_archive_intervals(camera="hosts/Server/NoSuch/Camera", hours=1.0)
        self.assertEqual(result["status"], "gap")
        self.assertIn("camera", result["message"].lower())

    def test_search_events_registers_export_event_body_type(self) -> None:
        """search_events imports the ExportEvent body module so Any decode never crashes."""
        module = importlib.import_module("axxon_mcp_live")

        class FakeStub:
            def ReadEvents(self, request, timeout):
                self.last_request = request
                yield object()

        import types

        class RecordingClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.imported: list[str] = []

            def ensure_client(self):
                return self

            def authenticate_grpc(self):
                pass

            def import_module(self, name):
                self.imported.append(name)
                stub_mod = types.SimpleNamespace()
                stub_mod.EEventType = types.SimpleNamespace(DESCRIPTOR=types.SimpleNamespace(values_by_name={}))
                stub_mod.SearchFilter = lambda **kw: types.SimpleNamespace(subjects=[], **kw)
                stub_mod.SearchFilterArray = lambda **kw: types.SimpleNamespace(**kw)
                stub_mod.TimeRange = lambda **kw: types.SimpleNamespace(**kw)
                stub_mod.ReadEventsRequest = lambda **kw: types.SimpleNamespace(**kw)
                return stub_mod

            def stub_from_proto(self, proto, service):
                self.last_stub = FakeStub()
                return self.last_stub

            def message_to_dict(self, message):
                return {"items": [{"event_name": "axxonsoft.bl.mmexport.ExportEvent", "subjects": ["x"]}]}

        fake = RecordingClient()
        live = module.AxxonMcpLive(client_factory=lambda _config: fake, config_factory=lambda: FakeConfig())
        live.connect_axxon_profile("env")

        result = live.search_events(hours=24.0, limit=5)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertTrue(any("ExportEvent" in name for name in fake.imported))
        # AC5: TimeRange must use the millisecond string format YYYYMMDDThhmmss.mmm, not numeric epoch-1900 ms.
        rng = fake.last_stub.last_request.range
        self.assertRegex(rng.begin_time, r"^\d{8}T\d{6}\.\d{3}$")
        self.assertRegex(rng.end_time, r"^\d{8}T\d{6}\.\d{3}$")

    def test_subscribe_events_bounded_respects_caps(self) -> None:
        module = importlib.import_module("axxon_mcp_live")
        fake = FakeClient()
        events = [
            {"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "type": "ET_DETECTOR", "id": "evt1"},
            {"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "type": "ET_DETECTOR", "id": "evt2"},
            {"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "type": "ET_DETECTOR", "id": "evt3"},
        ]

        def fake_pull_events(*, subjects, event_types, timeout, max_events):
            fake.last_subscribe_call = {
                "subjects": list(subjects),
                "event_types": list(event_types),
                "timeout": timeout,
                "max_events": max_events,
            }
            return events[:max_events]

        fake.pull_events_bounded = fake_pull_events  # type: ignore[attr-defined]
        live = module.AxxonMcpLive(client_factory=lambda _config: fake, config_factory=lambda: FakeConfig())
        live.connect_axxon_profile("env")

        result = live.subscribe_events_bounded(
            subjects=["hosts/Server/AppDataDetector.27/EventSupplier"],
            event_types=["ET_DETECTOR"],
            timeout=3.0,
            limit=2,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(fake.last_subscribe_call["timeout"], 3.0)
        self.assertEqual(fake.last_subscribe_call["max_events"], 2)

    def test_subscribe_events_bounded_caps_inputs(self) -> None:
        module = importlib.import_module("axxon_mcp_live")
        fake = FakeClient()
        fake.pull_events_bounded = lambda **_: []  # type: ignore[attr-defined]
        live = module.AxxonMcpLive(client_factory=lambda _config: fake, config_factory=lambda: FakeConfig())
        live.connect_axxon_profile("env")

        # Reject unbounded request: huge timeout or huge limit must be capped.
        result = live.subscribe_events_bounded(subjects=[], event_types=[], timeout=999.0, limit=10000)
        self.assertLessEqual(result["timeout"], 30.0)
        self.assertLessEqual(result["limit"], 500)


if __name__ == "__main__":
    unittest.main()
