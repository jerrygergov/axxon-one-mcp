from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_logic_alerts as module


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_PASSWORD_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class _Alert:
    def __init__(self, id="a1", node="Server"):
        self.id = id
        self.guid = id
        self.source_endpoint = "cam"
        self.initiator = "cam"
        self.node = node


class _GetResp:
    def __init__(self, alerts=None, unreachable_nodes=None):
        self.alerts = alerts or []
        self.unreachable_nodes = unreachable_nodes or []


class _ReviewResp:
    def __init__(self, success=None, failure=None, unreachable_nodes=None):
        self.success = success or []
        self.failure = failure or []
        self.unreachable_nodes = unreachable_nodes or []


class _Parent:
    def __init__(self, access_point=""):
        self.access_point = access_point


class _Filter:
    def __init__(self, groups=None):
        self.groups = list(groups or [])
        self.parents = []


class _Req:
    def __init__(self, nodes=None, filter=None, **kw):
        self.nodes = list(nodes or [])
        self.filter = filter
        self.extra = kw


class _Pb2:
    AlertFilter = _Filter
    AlertParent = _Parent
    BatchGetActiveAlertsRequest = _Req
    BatchFilterActiveAlertsRequest = _Req
    BatchBeginAlertsReviewRequest = _Req
    BatchContinueAlertsRewiewRequest = _Req
    BatchCancelAlertsReviewRequest = _Req
    BatchCompleteAlertsReviewRequest = _Req
    BatchEscalateAlertsRequest = _Req


class _Stub:
    def __init__(self, rec, with_alert=False):
        self._rec = rec
        self._with = with_alert

    def BatchGetActiveAlerts(self, request, timeout=None):
        self._rec.append(("BatchGetActiveAlerts", list(request.nodes)))
        return iter([_GetResp(alerts=[_Alert()] if self._with else [])])

    def BatchFilterActiveAlerts(self, request, timeout=None):
        self._rec.append(("BatchFilterActiveAlerts", list(request.nodes)))
        return iter([_GetResp(alerts=[])])

    def _review(self, name, request):
        self._rec.append((name, list(request.nodes)))
        return iter([_ReviewResp(success=[], failure=[], unreachable_nodes=[])])

    def BatchBeginAlertsReview(self, request, timeout=None):
        return self._review("BatchBeginAlertsReview", request)

    def BatchContinueAlertsRewiew(self, request, timeout=None):
        return self._review("BatchContinueAlertsRewiew", request)

    def BatchCancelAlertsReview(self, request, timeout=None):
        return self._review("BatchCancelAlertsReview", request)

    def BatchCompleteAlertsReview(self, request, timeout=None):
        return self._review("BatchCompleteAlertsReview", request)

    def BatchEscalateAlerts(self, request, timeout=None):
        return self._review("BatchEscalateAlerts", request)


class FakeClient:
    def __init__(self, config, with_alert=False):
        self.config = config
        self.calls: list = []
        self._with = with_alert

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._with)

    def import_module(self, name):
        return _Pb2()


def _inst(with_alert=False, **overrides):
    inst = module.AxxonMcpLogicAlerts(
        client_factory=lambda config: FakeClient(config, with_alert),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.logic_alerts_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_batch_get_active_alerts_ok(self) -> None:
        out = _inst(with_alert=True).batch_get_active_alerts(nodes=["Server"])
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["alert_count"], 1)
        self.assertEqual(out["alerts"][0]["id"], "a1")

    def test_batch_get_empty_nodes_error_no_wire(self) -> None:
        inst = _inst()
        out = inst.batch_get_active_alerts(nodes=[])
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_batch_filter_ok_empty_result(self) -> None:
        out = _inst().batch_filter_active_alerts(nodes=["Server"], groups=["g1"])
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["alert_count"], 0)


class GateTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.batch_begin_alerts_review(nodes=["Server"], confirmation=module.LOGIC_ALERTS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.batch_cancel_alerts_review(nodes=["Server"], confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_empty_nodes_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.batch_escalate_alerts(nodes=[], confirmation=module.LOGIC_ALERTS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class ReviewTests(unittest.TestCase):
    def test_all_five_reviews_applied(self) -> None:
        for tool, rpc in [
            ("batch_begin_alerts_review", "BatchBeginAlertsReview"),
            ("batch_continue_alerts_review", "BatchContinueAlertsRewiew"),
            ("batch_cancel_alerts_review", "BatchCancelAlertsReview"),
            ("batch_complete_alerts_review", "BatchCompleteAlertsReview"),
            ("batch_escalate_alerts", "BatchEscalateAlerts"),
        ]:
            inst = _inst(enabled=True)
            out = getattr(inst, tool)(nodes=["Server"], confirmation=module.LOGIC_ALERTS_CONFIRMATION)
            self.assertEqual(out["status"], "applied", tool)
            self.assertEqual(out["success"], [])
            self.assertEqual(inst.client.calls[0][0], rpc)

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.batch_begin_alerts_review(nodes=["Server"], confirmation=module.LOGIC_ALERTS_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
