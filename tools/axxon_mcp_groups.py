#!/usr/bin/env python3
"""GroupManager tools for Axxon One MCP (Phase 21).

Read object groups and change the group tree / object membership. The two writes
(`ChangeGroups`, `SetObjectsMembership`) are approval-gated
(`AXXON_GROUPS_APPROVE=1`) plus a per-call confirmation token, mirroring the
audit-injector idiom. GroupManager carries no etag, so the writes are plain
builds. Direct gRPC against `GroupManager`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

GROUPS_APPROVE_ENV = "AXXON_GROUPS_APPROVE"
GROUPS_CONFIRMATION = "CONFIRM-groups-set"
GROUPS_PROTO = "axxonsoft/bl/groups/GroupManager.proto"
GROUPS_PB2 = "axxonsoft.bl.groups.GroupManager_pb2"

GROUPS_TOOL_NAMES = (
    "groups_connect_axxon_profile",
    "list_groups",
    "change_groups",
    "set_objects_membership",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(GROUPS_APPROVE_ENV) == "1"


def _group_msg(pb2: Any, spec: dict[str, str]) -> Any:
    return pb2.Group(
        group_id=spec.get("group_id", ""),
        name=spec.get("name", ""),
        parent=spec.get("parent", ""),
        description=spec.get("description", ""),
    )


@dataclass
class AxxonMcpGroups:
    """Phase 21 GroupManager tools (group read + gated group/membership writes)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def groups_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+write",
            "approval_env": GROUPS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.groups_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.groups_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(GROUPS_PROTO, "GroupManager"), client.import_module(GROUPS_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {GROUPS_APPROVE_ENV}=1 to enable group writes.", "approval_env": GROUPS_APPROVE_ENV}
        if confirmation != GROUPS_CONFIRMATION:
            return {"status": "gap", "message": f"group writes require confirmation={GROUPS_CONFIRMATION}"}
        return None

    def list_groups(self, tree: bool = False) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        view = pb2.VIEW_MODE_TREE if tree else pb2.VIEW_MODE_DEFAULT
        resp = stub.ListGroups(pb2.ListGroupsRequest(view=view), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "count": len(resp.groups),
            "groups": [{"group_id": g.group_id, "name": g.name, "parent": g.parent, "description": g.description} for g in resp.groups],
        }

    def change_groups(
        self,
        removed_groups: list[str] | None = None,
        added_groups: list[dict[str, str]] | None = None,
        changed_groups: list[dict[str, str]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        removed_groups = removed_groups or []
        added_groups = added_groups or []
        changed_groups = changed_groups or []
        if not removed_groups and not added_groups and not changed_groups:
            return {"status": "error", "message": "provide at least one of removed_groups, added_groups, changed_groups"}
        stub, pb2 = self._stub_and_pb2()
        req = pb2.ChangeGroupsRequest(removed_groups=list(removed_groups))
        for spec in added_groups:
            req.added_groups.append(_group_msg(pb2, spec))
        for spec in changed_groups:
            req.changed_groups_info.append(_group_msg(pb2, spec))
        stub.ChangeGroups(req, timeout=self.ensure_client().config.timeout)
        return {
            "status": "applied",
            "removed_groups": list(removed_groups),
            "added_groups": [s.get("group_id", "") for s in added_groups],
            "changed_groups": [s.get("group_id", "") for s in changed_groups],
        }

    def set_objects_membership(
        self,
        added: list[dict[str, str]] | None = None,
        removed: list[dict[str, str]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        added = added or []
        removed = removed or []
        if not added and not removed:
            return {"status": "error", "message": "provide at least one of added, removed"}
        stub, pb2 = self._stub_and_pb2()
        req = pb2.SetObjectsMembershipRequest()
        for m in added:
            req.added_objects.append(pb2.Membership(group_id=m["group_id"], object=m["object"]))
        for m in removed:
            req.removed_objects.append(pb2.Membership(group_id=m["group_id"], object=m["object"]))
        resp = stub.SetObjectsMembership(req, timeout=self.ensure_client().config.timeout)
        return {
            "status": "applied",
            "failed_added": [{"group_id": m.group_id, "object": m.object} for m in resp.failed_added_objects],
            "failed_removed": [{"group_id": m.group_id, "object": m.object} for m in resp.failed_removed_objects],
        }
