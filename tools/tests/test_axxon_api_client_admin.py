from __future__ import annotations

import sys
from pathlib import Path
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class _FakePullEventsRequest:
    def __init__(self, **kwargs) -> None:
        self.subscription_id = kwargs.get("subscription_id", "")
        self.filters = kwargs.get("filters")


class _FakeDisconnectEventChannelRequest:
    def __init__(self, **kwargs) -> None:
        self.subscription_id = kwargs.get("subscription_id", "")


class _FakeEventFilter:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class _FakeEventFilters:
    def __init__(self, **kwargs) -> None:
        self.include = kwargs.get("include", [])


class _FakeNotifyPb:
    PullEventsRequest = _FakePullEventsRequest
    DisconnectEventChannelRequest = _FakeDisconnectEventChannelRequest
    EventFilter = _FakeEventFilter
    EventFilters = _FakeEventFilters


class _FakeEventsPb:
    ET_Alert = 1
    ET_ConfigChangedEvent = 2


class _FakeNotifierStub:
    def __init__(self, *, raise_on_pull: bool = False) -> None:
        self.raise_on_pull = raise_on_pull
        self.pull_requests: list[_FakePullEventsRequest] = []
        self.detailed_requests: list[_FakePullEventsRequest] = []
        self.disconnect_requests: list[_FakeDisconnectEventChannelRequest] = []

    def PullEvents(self, request, timeout):
        self.pull_requests.append(request)
        if self.raise_on_pull:
            raise RuntimeError("stream failed")
        return [{"items": [{"event_type": "ET_Alert"}]}, {"items": [{"event_type": "ET_ConfigChangedEvent"}]}]

    def PullDetailedEvents(self, request, timeout):
        self.detailed_requests.append(request)
        if self.raise_on_pull:
            raise RuntimeError("stream failed")
        return [{"items": [{"event_type": "ET_Alert", "details": {"a": 1}}]}]

    def DisconnectEventChannel(self, request, timeout):
        self.disconnect_requests.append(request)
        return {}


class _FakeClient(AxxonApiClient):
    def __init__(self) -> None:
        cfg = AxxonClientConfig(
            host="example.local",
            grpc_port=20109,
            http_port=80,
            http_url="http://example.local",
            username="root",
            password="secret",
            tls_cn="Server",
            ca=Path("/tmp/ca.crt"),
            proto_dir=Path("/tmp"),
            stubs_dir=Path("/tmp"),
            timeout=5.0,
        )
        super().__init__(cfg)
        self.calls: list[tuple[str, dict]] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append((fqmn, dict(data or {})))
        return {"status": 200, "body": {"ok": True}}


class _FakeNotifierClient(_FakeClient):
    def __init__(self, *, raise_on_pull: bool = False) -> None:
        super().__init__()
        self.grpc_channel = object()
        self.stub = _FakeNotifierStub(raise_on_pull=raise_on_pull)
        self.stub_calls: list[tuple[str, str]] = []

    def import_module(self, name: str):
        if name == "axxonsoft.bl.events.Notification_pb2":
            return _FakeNotifyPb
        if name == "axxonsoft.bl.events.Events_pb2":
            return _FakeEventsPb
        return super().import_module(name)

    def stub_from_proto(self, proto_path: str, service_name: str):
        self.stub_calls.append((proto_path, service_name))
        return self.stub

    def message_to_dict(self, message):
        return dict(message)


class AdminApiWrappersTests(unittest.TestCase):
    def test_security_list_roles_passes_page_controls(self) -> None:
        c = _FakeClient()
        c.security_list_roles(page_size=25, page_token="next")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ListRoles",
                {"page_size": 25, "page_token": "next"},
            ),
        )

    def test_security_list_users_passes_page_controls_and_role_filter(self) -> None:
        c = _FakeClient()
        c.security_list_users(page_size=25, page_token="next", role_ids=["role-a"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ListUsers",
                {"page_size": 25, "page_token": "next", "role_ids": ["role-a"]},
            ),
        )

    def test_security_list_ldap_servers_passes_page_controls(self) -> None:
        c = _FakeClient()
        c.security_list_ldap_servers(page_size=25, page_token="next")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ListLDAPServers",
                {"page_size": 25, "page_token": "next"},
            ),
        )

    def test_security_get_policies_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.security_get_policies()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.GetPolicies",
                {},
            ),
        )

    def test_security_get_restricted_config_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.security_get_restricted_config()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.GetRestrictedConfig",
                {},
            ),
        )

    def test_security_list_global_permissions_passes_role_ids(self) -> None:
        c = _FakeClient()
        c.security_list_global_permissions(["role-a", "role-b"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ListGlobalPermissions",
                {"role_ids": ["role-a", "role-b"]},
            ),
        )

    def test_security_list_object_permissions_info_passes_role_node_and_page_controls(self) -> None:
        c = _FakeClient()
        c.security_list_object_permissions_info(
            role_id="role-a",
            node_name="Server",
            page_size=25,
            page_token="next",
        )
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ListObjectsPermissionsInfo",
                {
                    "role_id": "role-a",
                    "node_name": "Server",
                    "page_size": 25,
                    "page_token": "next",
                },
            ),
        )

    def test_license_get_global_restrictions_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.license_get_global_restrictions()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.license.LicenseService.GetGlobalRestrictions",
                {},
            ),
        )

    def test_license_get_domain_key_info_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.license_get_domain_key_info()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.license.LicenseService.GetDomainLicenseKeyInfo",
                {},
            ),
        )

    def test_license_get_host_info_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.license_get_host_info()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.license.LicenseService.GetHostInfo",
                {},
            ),
        )

    def test_license_key_info_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.license_key_info()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.license.LicenseService.LicenseKeyInfo",
                {},
            ),
        )

    def test_license_get_node_restrictions_wraps_node_names(self) -> None:
        c = _FakeClient()
        c.license_get_node_restrictions(["Server", "Backup"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.license.LicenseService.GetNodeRestrictions",
                {"nodes": [{"name": "Server"}, {"name": "Backup"}]},
            ),
        )

    def test_license_is_possible_to_launch_passes_service_and_quantity(self) -> None:
        c = _FakeClient()
        c.license_is_possible_to_launch("AVDetector", quantity=2)
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.license.LicenseService.IsPossibleToLaunch",
                {"service_name": "AVDetector", "quantity": 2},
            ),
        )

    def test_time_get_time_zone_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.time_get_time_zone()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.tz.TimeZoneManager.GetTimeZone",
                {},
            ),
        )

    def test_time_get_ntp_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.time_get_ntp()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.tz.TimeZoneManager.GetNTP",
                {},
            ),
        )

    def test_time_list_time_zones_uses_empty_request(self) -> None:
        c = _FakeClient()
        c.time_list_time_zones()
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.tz.TimeZoneManager.ListTimeZones",
                {},
            ),
        )

    def test_time_batch_get_zones_passes_zone_ids(self) -> None:
        c = _FakeClient()
        c.time_batch_get_zones(["Europe/Moscow", "UTC"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.tz.TimeZoneManager.BatchGetZones",
                {"ids": ["Europe/Moscow", "UTC"]},
            ),
        )

    def test_pull_notifier_events_bounded_selects_domain_notifier_and_disconnects(self) -> None:
        c = _FakeNotifierClient()
        result = c.pull_notifier_events_bounded(
            notifier="domain",
            subjects=["hosts/Server"],
            event_types=["alert"],
            timeout_s=5.0,
            limit=1,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["notifier"], "domain")
        self.assertEqual(result["count"], 1)
        self.assertEqual(c.stub_calls, [("axxonsoft/bl/events/Notification.proto", "DomainNotifier")])
        self.assertEqual(len(c.stub.pull_requests), 1)
        self.assertEqual(len(c.stub.disconnect_requests), 1)
        self.assertEqual(c.stub.disconnect_requests[0].subscription_id, c.stub.pull_requests[0].subscription_id)

    def test_pull_notifier_events_bounded_selects_node_notifier_and_detailed_pull(self) -> None:
        c = _FakeNotifierClient()
        result = c.pull_notifier_events_bounded(
            notifier="node",
            subjects=[],
            event_types=[],
            timeout_s=5.0,
            limit=10,
            detailed=True,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["notifier"], "node")
        self.assertEqual(result["count"], 1)
        self.assertEqual(c.stub_calls, [("axxonsoft/bl/events/Notification.proto", "NodeNotifier")])
        self.assertEqual(len(c.stub.detailed_requests), 1)
        self.assertEqual(len(c.stub.disconnect_requests), 1)

    def test_pull_notifier_events_bounded_disconnects_on_stream_error(self) -> None:
        c = _FakeNotifierClient(raise_on_pull=True)
        result = c.pull_notifier_events_bounded(
            notifier="domain",
            subjects=[],
            event_types=[],
            timeout_s=5.0,
            limit=10,
        )

        self.assertEqual(result["status"], "warn")
        self.assertEqual(result["count"], 0)
        self.assertIn("stream_error", result)
        self.assertEqual(len(c.stub.disconnect_requests), 1)


if __name__ == "__main__":
    unittest.main()
