from __future__ import annotations

import unittest
from pathlib import Path
import sys

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class _FakeClient(AxxonApiClient):
    def __init__(self) -> None:
        cfg = AxxonClientConfig(
            host="example.local", grpc_port=20109, http_port=80,
            http_url="http://example.local", username="root", password="secret",
            tls_cn="Server", ca=Path("/tmp/ca.crt"), proto_dir=Path("/tmp"),
            stubs_dir=Path("/tmp"), timeout=5.0,
        )
        super().__init__(cfg)
        self.calls: list[tuple[str, dict]] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append((fqmn, dict(data or {})))
        return {"status": 200, "body": {"result": True, "alert_id": "fake-id"}}


class LogicServiceWrappersTests(unittest.TestCase):
    def test_raise_alert_passes_camera_ap_through(self) -> None:
        c = _FakeClient()
        r = c.raise_alert("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(r["body"]["alert_id"], "fake-id")
        self.assertEqual(c.calls, [(
            "axxonsoft.bl.logic.LogicService.RaiseAlert",
            {"camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
        )])

    def test_begin_alert_review_passes_camera_ap_and_alert_id(self) -> None:
        c = _FakeClient()
        c.begin_alert_review("cam-ap", "alert-1")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.BeginAlertReview",
            {"camera_ap": "cam-ap", "alert_id": "alert-1"},
        ))

    def test_complete_alert_review_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.complete_alert_review("cam-ap", "alert-1", severity="confirmed_alarm", bookmark_message="ok")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.CompleteAlertReview",
            {
                "camera_ap": "cam-ap",
                "alert_id": "alert-1",
                "severity": "confirmed_alarm",
                "bookmark": {"message": "ok"},
            },
        ))

    def test_escalate_alert_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.escalate_alert("cam-ap", "alert-1", priority="AP_HIGH", user_roles=["role-a"], comment="esc")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.EscalateAlert",
            {
                "camera_ap": "cam-ap",
                "alert_id": "alert-1",
                "priority": "AP_HIGH",
                "user_roles": ["role-a"],
                "comment": "esc",
            },
        ))

    def test_batch_get_active_alerts_passes_nodes(self) -> None:
        c = _FakeClient()
        c.batch_get_active_alerts(["hosts/Server"])
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.BatchGetActiveAlerts",
            {"nodes": ["hosts/Server"]},
        ))

    def test_batch_filter_active_alerts_passes_nodes_and_filter(self) -> None:
        c = _FakeClient()
        c.batch_filter_active_alerts(["hosts/Server"], filter={"min_severity": 1})
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.BatchFilterActiveAlerts",
            {"nodes": ["hosts/Server"], "filter": {"min_severity": 1}},
        ))


if __name__ == "__main__":
    unittest.main()
