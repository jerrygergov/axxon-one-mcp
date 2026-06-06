from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_groups as module


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


class _Group:
    def __init__(self, group_id="", name="", description="", parent="", groups=None, permissions=None):
        self.group_id = group_id
        self.name = name
        self.description = description
        self.parent = parent
        self.groups = groups or []


class _Membership:
    def __init__(self, group_id="", object=""):
        self.group_id = group_id
        self.object = object


class _ListResp:
    def __init__(self, groups=None):
        self.groups = groups if groups is not None else [
            _Group("g-1", "Demo", parent=""),
            _Group("g-2", "Cameras", parent="g-1"),
        ]


class _ChangeReq:
    def __init__(self, removed_groups=None, changed_groups_info=None, added_groups=None):
        self.removed_groups = list(removed_groups or [])
        self.changed_groups_info = list(changed_groups_info or [])
        self.added_groups = list(added_groups or [])


class _ListReq:
    def __init__(self, view=0):
        self.view = view


class _SetMembReq:
    def __init__(self, added_objects=None, removed_objects=None):
        self.added_objects = list(added_objects or [])
        self.removed_objects = list(removed_objects or [])


class _SetMembResp:
    def __init__(self, failed_added=None, failed_removed=None):
        self.failed_added_objects = failed_added or []
        self.failed_removed_objects = failed_removed or []


class _Empty:
    def __init__(self, **kw):
        pass


class _GroupsPb2:
    Group = _Group
    Membership = _Membership
    ListGroupsRequest = _ListReq
    ChangeGroupsRequest = _ChangeReq
    SetObjectsMembershipRequest = _SetMembReq
    VIEW_MODE_DEFAULT = 0
    VIEW_MODE_TREE = 1


class _FakeStub:
    def __init__(self, recorder, listing=None):
        self._rec = recorder
        self._listing = listing or _ListResp()

    def ListGroups(self, request, timeout=None):
        self._rec.append(("ListGroups", request, timeout))
        return self._listing

    def ChangeGroups(self, request, timeout=None):
        self._rec.append(("ChangeGroups", request, timeout))
        return _Empty()

    def SetObjectsMembership(self, request, timeout=None):
        self._rec.append(("SetObjectsMembership", request, timeout))
        return _SetMembResp()


class FakeGroupsClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "GroupManager"
        return _FakeStub(self.calls)

    def import_module(self, name):
        return _GroupsPb2()


def _grp(**overrides):
    inst = module.AxxonMcpGroups(
        client_factory=lambda config: FakeGroupsClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.groups_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_list_groups_shape(self) -> None:
        out = _grp().list_groups()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["groups"][0]["group_id"], "g-1")
        self.assertEqual(out["groups"][1]["parent"], "g-1")


class GatingTests(unittest.TestCase):
    def test_change_groups_disabled(self) -> None:
        inst = _grp(enabled=False)
        out = inst.change_groups(removed_groups=["x"], confirmation=module.GROUPS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_change_groups_bad_token(self) -> None:
        inst = _grp(enabled=True)
        out = inst.change_groups(removed_groups=["x"], confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_membership_disabled(self) -> None:
        inst = _grp(enabled=False)
        out = inst.set_objects_membership(added=[{"group_id": "g", "object": "o"}], confirmation=module.GROUPS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_membership_bad_token(self) -> None:
        inst = _grp(enabled=True)
        out = inst.set_objects_membership(added=[{"group_id": "g", "object": "o"}], confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])


class EmptyInputTests(unittest.TestCase):
    def test_change_groups_no_edit_errors(self) -> None:
        inst = _grp(enabled=True)
        out = inst.change_groups(confirmation=module.GROUPS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_membership_no_edit_errors(self) -> None:
        inst = _grp(enabled=True)
        out = inst.set_objects_membership(confirmation=module.GROUPS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class ChangeGroupsTests(unittest.TestCase):
    def test_add_and_remove_shape(self) -> None:
        inst = _grp(enabled=True)
        out = inst.change_groups(
            removed_groups=["old-id"],
            added_groups=[{"group_id": "new-id", "name": "probe", "parent": "g-1", "description": "d"}],
            confirmation=module.GROUPS_CONFIRMATION,
        )
        self.assertEqual(out["status"], "applied")
        req = inst.client.calls[0][1]
        self.assertEqual(list(req.removed_groups), ["old-id"])
        self.assertEqual(req.added_groups[0].group_id, "new-id")
        self.assertEqual(req.added_groups[0].name, "probe")
        self.assertEqual(req.added_groups[0].parent, "g-1")
        self.assertEqual(req.added_groups[0].description, "d")

    def test_changed_groups_passed(self) -> None:
        inst = _grp(enabled=True)
        inst.change_groups(
            changed_groups=[{"group_id": "g-2", "name": "Renamed"}],
            confirmation=module.GROUPS_CONFIRMATION,
        )
        req = inst.client.calls[0][1]
        self.assertEqual(req.changed_groups_info[0].group_id, "g-2")
        self.assertEqual(req.changed_groups_info[0].name, "Renamed")


class MembershipTests(unittest.TestCase):
    def test_add_and_remove_shape(self) -> None:
        inst = _grp(enabled=True)
        out = inst.set_objects_membership(
            added=[{"group_id": "g-2", "object": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"}],
            removed=[{"group_id": "g-1", "object": "hosts/Server/DeviceIpint.2/SourceEndpoint.video:0:0"}],
            confirmation=module.GROUPS_CONFIRMATION,
        )
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["failed_added"], [])
        self.assertEqual(out["failed_removed"], [])
        req = inst.client.calls[0][1]
        self.assertEqual(req.added_objects[0].group_id, "g-2")
        self.assertEqual(req.added_objects[0].object, "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(req.removed_objects[0].group_id, "g-1")


if __name__ == "__main__":
    unittest.main()
