#!/usr/bin/env python3
"""RealtimeRecognizer watchlist write tools for Axxon One MCP (Phase 14).

Mutation tools for `RealtimeRecognizerService`: ChangeLists (add/change/remove
lists), ChangeItems (add/remove LPR items), and Clear (node-wide wipe). These
mutate the VMS, so they are gated behind an approval env
(`AXXON_RECOGNIZER_WRITE_APPROVE=1`) plus a per-call confirmation token, mirroring
the audit-injector idiom. Clear is irreversible and node-wide, so it requires a
second explicit acknowledgement token.

Biometric ingestion (face/food images, vectors) is out of scope: only LPR string
items are accepted, and the tools never build or emit raw image bytes or vectors.
Direct gRPC against `RealtimeRecognizerService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

WRITE_APPROVE_ENV = "AXXON_RECOGNIZER_WRITE_APPROVE"
WRITE_CONFIRMATION = "CONFIRM-recognizer-write"
CLEAR_ACK = "CONFIRM-clear-node-wipe"
RECOGNIZER_PROTO = "axxonsoft/bl/realtimeRecognizer/RealtimeRecognizer.proto"
RECOGNIZER_PB2 = "axxonsoft.bl.realtimeRecognizer.RealtimeRecognizer_pb2"

LIST_TYPES = {"any": "ELT_Any", "face": "ELT_Face", "lpr": "ELT_LPR", "food": "ELT_Food"}

RECOGNIZER_WRITE_TOOL_NAMES = (
    "recognizer_write_connect_axxon_profile",
    "recognizer_change_lists",
    "recognizer_change_items",
    "recognizer_clear",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(WRITE_APPROVE_ENV) == "1"


def _build_list(pb2: Any, spec: dict[str, Any]) -> Any:
    """Build a pb2.List from a dict, honoring id/name/description/score/type/item_ids."""
    list_msg = pb2.List()
    if spec.get("id"):
        list_msg.id = str(spec["id"])
    if spec.get("name"):
        list_msg.name = str(spec["name"])
    if spec.get("description"):
        list_msg.description = str(spec["description"])
    if spec.get("score"):
        list_msg.score = float(spec["score"])
    list_msg.type = getattr(pb2, LIST_TYPES.get(str(spec.get("type", "any")).lower(), "ELT_Any"))
    for item_id in spec.get("item_ids", []) or []:
        list_msg.item_ids.append(str(item_id))
    return list_msg


@dataclass
class AxxonMcpRecognizerWrite:
    """Phase 14 RealtimeRecognizer watchlist write tools (approval-gated mutations)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def recognizer_write_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "write",
            "approval_env": WRITE_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.recognizer_write_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.recognizer_write_connect_axxon_profile("env")
        return self.client

    def _gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {WRITE_APPROVE_ENV}=1 to enable recognizer writes.", "approval_env": WRITE_APPROVE_ENV}
        if confirmation != WRITE_CONFIRMATION:
            return {"status": "gap", "message": f"recognizer writes require confirmation={WRITE_CONFIRMATION}"}
        return None

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(RECOGNIZER_PROTO, "RealtimeRecognizerService"), client.import_module(RECOGNIZER_PB2)

    def recognizer_change_lists(
        self,
        added: list[dict[str, Any]] | None = None,
        changed: list[dict[str, Any]] | None = None,
        removed_ids: list[str] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        added, changed, removed_ids = added or [], changed or [], removed_ids or []
        if not (added or changed or removed_ids):
            return {"status": "error", "message": "provide at least one of added, changed, removed_ids"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.ChangeListsRequest(
            added_lists=[_build_list(pb2, s) for s in added],
            changed_lists=[_build_list(pb2, s) for s in changed],
            removed_list_ids=[str(x) for x in removed_ids],
        )
        response = stub.ChangeLists(request, timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "failed_lists": list(response.failed_lists)}

    def _item_packets(self, pb2: Any, added: list[dict[str, Any]], removed_item_ids: list[str]) -> Iterator[Any]:
        """Yield ChangeItemsRequest packets; the last one carries EPS_LAST."""
        packets: list[Any] = []
        for spec in added:
            item = pb2.Item(id=str(spec.get("id", "")), type=pb2.DT_Plate, data_string=str(spec.get("data_string", "")))
            packets.append(pb2.ChangeItemsRequest(added_item=item))
        if removed_item_ids:
            packets.append(pb2.ChangeItemsRequest(removed_item=pb2.RemovedItemIds(removed_item_ids=[str(x) for x in removed_item_ids])))
        for index, packet in enumerate(packets):
            if index == len(packets) - 1:
                packet.status = pb2.EPS_LAST
            yield packet

    def recognizer_change_items(
        self,
        list_id: str = "",
        added: list[dict[str, Any]] | None = None,
        removed_item_ids: list[str] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        added, removed_item_ids = added or [], removed_item_ids or []
        if not (added or removed_item_ids):
            return {"status": "error", "message": "provide at least one of added, removed_item_ids"}
        stub, pb2 = self._stub_and_pb2()
        failed: list[str] = []
        for response in stub.ChangeItems(self._item_packets(pb2, added, removed_item_ids), timeout=self.ensure_client().config.timeout):
            failed.extend(response.failed_items)
        return {"status": "applied", "list_id": list_id, "failed_items": failed}

    def recognizer_clear(self, node_name: str = "", confirmation: str = "", clear_ack: str = "") -> dict[str, Any]:
        """Wipe ALL lists and items on a node. Irreversible and node-wide.

        Requires both the standard confirmation token and a second acknowledgement
        token because there is no rollback: every list and item on the node is
        permanently deleted.
        """
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        if clear_ack != CLEAR_ACK:
            return {"status": "gap", "message": f"recognizer_clear deletes ALL lists/items on the node; pass clear_ack={CLEAR_ACK}"}
        stub, pb2 = self._stub_and_pb2()
        stub.Clear(pb2.ClearRequest(node_name=node_name), timeout=self.ensure_client().config.timeout)
        return {"status": "cleared", "node_name": node_name, "warning": "all lists and items on the node were deleted"}
