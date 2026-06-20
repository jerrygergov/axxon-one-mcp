from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_notifier_actions as module

_SECRET = "NOTIFIER-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)
_MESSAGE = "EMAIL-MESSAGE-SHOULD-NOT-LEAK"


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = _SECRET
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class _PushDiagnosticEventsRequest:
    def __init__(self, alerts=None, actions=None):
        self.alerts = list(alerts or [])
        self.actions = list(actions or [])


class _SendEMailRequest:
    def __init__(self, access_point="", subject="", message="", recipients=None, attachments=None):
        self.access_point = access_point
        self.subject = subject
        self.message = message
        self.recipients = list(recipients or [])
        self.attachments = list(attachments or [])


class _EmailResponse:
    guid = "email-guid-1"


class _NotificationPb2:
    PushDiagnosticEventsRequest = _PushDiagnosticEventsRequest


class _EmailPb2:
    SendEMailRequest = _SendEMailRequest


class _NotificationStub:
    def __init__(self, rec, service_name):
        self._rec = rec
        self._service_name = service_name

    def PushDiagnosticEvents(self, request, timeout=None):
        self._rec.append(("PushDiagnosticEvents", self._service_name, len(request.alerts), len(request.actions)))
        return object()


class _EmailStub:
    def __init__(self, rec):
        self._rec = rec

    def SendEMail(self, request, timeout=None):
        self._rec.append(("SendEMail", request.access_point, request.subject, request.message, list(request.recipients), list(request.attachments)))
        return _EmailResponse()


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        if service_name in {"DomainNotifier", "NodeNotifier"}:
            return _NotificationStub(self.calls, service_name)
        return _EmailStub(self.calls)

    def import_module(self, name):
        if name.endswith("Notification_pb2"):
            return _NotificationPb2()
        return _EmailPb2()


def _inst(enabled=False):
    inst = module.AxxonMcpNotifierActions(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
        enabled=enabled,
    )
    inst.notifier_actions_connect_axxon_profile("env")
    return inst


class NotifierActionTests(unittest.TestCase):
    def test_connect_reports_gate(self) -> None:
        out = _inst(enabled=True).notifier_actions_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "write")
        self.assertTrue(out["enabled"])
        self.assertEqual(out["approval_env"], module.NOTIFIER_ACTIONS_APPROVE_ENV)
        self.assertNotIn(_SECRET, str(out))

    def test_push_diagnostic_events_requires_gate(self) -> None:
        inst = _inst(enabled=False)
        out = inst.push_diagnostic_events("domain", alerts=[{"rule_name": "test"}], actions=[], confirmation=module.NOTIFIER_ACTIONS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["approval_env"], module.NOTIFIER_ACTIONS_APPROVE_ENV)
        self.assertEqual(inst.client.calls, [])

    def test_push_diagnostic_events_dispatches_domain_and_node(self) -> None:
        inst = _inst(enabled=True)
        domain = inst.push_diagnostic_events("domain", alerts=[{"rule_name": "a"}], actions=[], confirmation=module.NOTIFIER_ACTIONS_CONFIRMATION)
        node = inst.push_diagnostic_events("node", alerts=[], actions=[{"action_description": "a"}], confirmation=module.NOTIFIER_ACTIONS_CONFIRMATION)
        self.assertEqual(domain["status"], "pushed")
        self.assertEqual(node["status"], "pushed")
        self.assertIn(("PushDiagnosticEvents", "DomainNotifier", 1, 0), inst.client.calls)
        self.assertIn(("PushDiagnosticEvents", "NodeNotifier", 0, 1), inst.client.calls)

    def test_send_email_requires_confirmation(self) -> None:
        inst = _inst(enabled=True)
        out = inst.send_email("ap-1", "subject", _MESSAGE, ["user@example.com"], confirmation="wrong")
        self.assertEqual(out["status"], "gap")
        self.assertIn(module.NOTIFIER_ACTIONS_CONFIRMATION, out["message"])
        self.assertEqual(inst.client.calls, [])

    def test_send_email_dispatches_without_echoing_message(self) -> None:
        inst = _inst(enabled=True)
        out = inst.send_email(
            "ap-1",
            "subject",
            _MESSAGE,
            ["user@example.com"],
            attachments=["a.txt"],
            confirmation=module.NOTIFIER_ACTIONS_CONFIRMATION,
        )
        self.assertEqual(out["status"], "sent")
        self.assertEqual(out["guid"], "email-guid-1")
        self.assertEqual(out["recipient_count"], 1)
        self.assertEqual(out["attachment_count"], 1)
        self.assertNotIn(_MESSAGE, str(out))
        self.assertIn(("SendEMail", "ap-1", "subject", _MESSAGE, ["user@example.com"], ["a.txt"]), inst.client.calls)

    def test_tool_names_exported(self) -> None:
        self.assertIn("push_diagnostic_events", module.NOTIFIER_ACTIONS_TOOL_NAMES)
        self.assertIn("send_email", module.NOTIFIER_ACTIONS_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
