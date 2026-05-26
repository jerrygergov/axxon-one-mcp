from __future__ import annotations

import sys
from pathlib import Path
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class _FakeClient(AxxonApiClient):
    def __init__(self) -> None:
        cfg = AxxonClientConfig(
            host="example.local",
            grpc_port=20109,
            http_port=80,
            http_url="http://example.local",
            username="fixture-admin",
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


class AdminMutationApiWrappersTests(unittest.TestCase):
    def test_security_change_config_posts_payload(self) -> None:
        c = _FakeClient()
        payload = {"added_roles": [{"index": "role-a"}]}

        c.security_change_config(payload)

        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ChangeConfig",
                {"added_roles": [{"index": "role-a"}]},
            ),
        )

    def test_security_set_global_permissions_wraps_role_permissions(self) -> None:
        c = _FakeClient()

        c.security_set_global_permissions("role-a", {"unrestricted_access": "UNRESTRICTED_ACCESS_NO"})

        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.SetGlobalPermissions",
                {"permissions": {"role-a": {"unrestricted_access": "UNRESTRICTED_ACCESS_NO"}}},
            ),
        )

    def test_security_set_object_permissions_wraps_role_permissions(self) -> None:
        c = _FakeClient()

        c.security_set_object_permissions("role-a", {"camera_access": {"cam": "CAMERA_ACCESS_FORBID"}})

        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.SetObjectPermissions",
                {"role_to_permissions": {"role-a": {"camera_access": {"cam": "CAMERA_ACCESS_FORBID"}}}},
            ),
        )

    def test_security_set_groups_permissions_passes_permission_list(self) -> None:
        c = _FakeClient()

        c.security_set_groups_permissions([{"role_id": "role-a", "groups_permissions": {}}])

        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.SetGroupsPermissions",
                {"permissions": [{"role_id": "role-a", "groups_permissions": {}}]},
            ),
        )

    def test_security_set_macros_permissions_wraps_role_access(self) -> None:
        c = _FakeClient()

        c.security_set_macros_permissions("role-a", {"macro-a": "MACROS_ACCESS_FORBID"})

        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.SetMacrosPermissions",
                {"role_id": "role-a", "macros_access": {"macro-a": "MACROS_ACCESS_FORBID"}},
            ),
        )

    def test_security_list_groups_permissions_info_passes_page_controls(self) -> None:
        c = _FakeClient()

        c.security_list_groups_permissions_info(role_id="role-a", page_size=25, page_token="next")

        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ListGroupsPermissionsInfo",
                {"role_id": "role-a", "page_size": 25, "page_token": "next"},
            ),
        )

    def test_security_list_macros_permissions_paged_passes_page_controls(self) -> None:
        c = _FakeClient()

        c.security_list_macros_permissions_paged(role_id="role-a", page_size=25, page_token="next")

        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.security.SecurityService.ListMacrosPermissionsPaged",
                {"role_id": "role-a", "page_size": 25, "page_token": "next"},
            ),
        )

    def test_security_ldap_sync_reads_use_empty_requests(self) -> None:
        c = _FakeClient()

        c.security_get_ldap_synchronization()
        c.security_get_ldap_synchronization_state()

        self.assertEqual(
            c.calls,
            [
                ("axxonsoft.bl.security.SecurityService.GetLDAPSynchronization", {}),
                ("axxonsoft.bl.security.SecurityService.GetLDAPSynchronizationState", {}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
