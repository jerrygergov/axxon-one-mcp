from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class SubscriptionSmokeTests(unittest.TestCase):
    def test_modes_are_declared(self) -> None:
        module = importlib.import_module("axxon_subscription_smoke")
        self.assertIn("websocket_camera_events", module.subscription_modes())
        self.assertIn("websocket_camera_track", module.subscription_modes())
        self.assertIn("grpc_event_subscription", module.subscription_modes())

    def test_builds_grpc_pull_event_filters(self) -> None:
        module = importlib.import_module("axxon_subscription_smoke")

        class FakeEventFilter:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeEventFilters:
            def __init__(self, include=None):
                self.include = include or []

        notify_pb2 = SimpleNamespace(EventFilter=FakeEventFilter, EventFilters=FakeEventFilters)
        events_pb2 = SimpleNamespace(ET_DetectorEvent=1)

        filters = module.build_pull_event_filters(
            notify_pb2,
            events_pb2,
            subjects=["hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"],
            event_types=["detector"],
            current_node_events_only=True,
        )

        self.assertEqual(len(filters.include), 1)
        self.assertEqual(filters.include[0].kwargs["event_type"], 1)
        self.assertEqual(filters.include[0].kwargs["subject"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertTrue(filters.include[0].kwargs["current_node_events_only"])

    def test_builds_pdf_style_websocket_url(self) -> None:
        module = importlib.import_module("axxon_subscription_smoke")

        url = module.build_websocket_url("http://example.test/root", "root", "p@ss word", schema="proto")

        self.assertEqual(url, "ws://root:p%40ss%20word@example.test/root/events?schema=proto")

    def test_camera_device_ap_strips_source_endpoint(self) -> None:
        module = importlib.import_module("axxon_subscription_smoke")

        self.assertEqual(
            module.camera_device_ap("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"),
            "hosts/Server/DeviceIpint.1",
        )
