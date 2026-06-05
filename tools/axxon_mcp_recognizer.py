#!/usr/bin/env python3
"""Read-only RealtimeRecognizerService watchlist tools for Axxon One MCP (Phase 11).

Inspect face/LPR recognition watchlists: which lists exist and who/what is enrolled.
Privacy-first: the item reader never loads face images or biometric vectors (it calls
GetItems with empty required_items, which the server answers with metadata only).
List mutation (ChangeLists/ChangeItems/Clear) is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

RECOGNIZER_PROTO = "axxonsoft/bl/realtimeRecognizer/RealtimeRecognizer.proto"
RECOGNIZER_PB2 = "axxonsoft.bl.realtimeRecognizer.RealtimeRecognizer_pb2"
ITEM_CAP = 2000

# Friendly name -> EListType enum attribute on the generated pb2 module.
LIST_TYPES = {"any": "ELT_Any", "face": "ELT_Face", "lpr": "ELT_LPR", "food": "ELT_Food"}

RECOGNIZER_TOOL_NAMES = (
    "recognizer_connect_axxon_profile",
    "list_recognizer_lists",
    "get_recognizer_list",
    "list_recognizer_items",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Render a privacy-safe item summary (no images, no vectors)."""
    body = item.get("item", item)
    summary: dict[str, Any] = {"id": body.get("id", "")}
    meta = body.get("data_meta")
    if isinstance(meta, dict):
        if meta.get("name"):
            summary["name"] = meta["name"]
        face = meta.get("face_meta")
        if isinstance(face, dict) and face.get("full_name"):
            summary["full_name"] = face["full_name"]
    if body.get("data_string"):
        summary["value"] = body["data_string"]
    return summary


@dataclass
class AxxonMcpRecognizer:
    """Phase 11 read-only face/LPR watchlist tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def recognizer_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read-only"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.recognizer_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.recognizer_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(RECOGNIZER_PROTO, "RealtimeRecognizerService"), client.import_module(RECOGNIZER_PB2)

    def list_recognizer_lists(self, list_type: str = "any") -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        enum_attr = LIST_TYPES.get(list_type.lower(), "ELT_Any")
        request = pb2.GetListsRequest(type=getattr(pb2, enum_attr))
        data = self.client.message_to_dict(stub.GetLists(request, timeout=self.client.config.timeout))
        lists = [
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "score": item.get("score"),
                "item_count": len(item.get("item_ids", [])),
            }
            for item in data.get("lists", [])
        ]
        return {"status": "ok", "count": len(lists), "lists": lists}

    def get_recognizer_list(self, list_id: str) -> dict[str, Any]:
        if not str(list_id or "").strip():
            return {"status": "error", "message": "list_id is required"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.GetListStreamRequest(list_id=list_id)
        descriptor: dict[str, Any] = {}
        for page in stub.GetListStream(request, timeout=self.client.config.timeout):
            page_dict = self.client.message_to_dict(page)
            if page_dict.get("list"):
                descriptor = page_dict["list"]
        return {"status": "ok", "list": descriptor}

    def list_recognizer_items(self, list_ids: list[str] | None = None, limit: int = 200) -> dict[str, Any]:
        limit = min(max(int(limit), 1), ITEM_CAP)
        stub, pb2 = self._stub_and_pb2()
        # Empty required_items => server returns metadata only (no images/vectors).
        req_kwargs: dict[str, Any] = {"required_items": [], "load_images": False, "load_vectors": False}
        if list_ids:
            req_kwargs["list_ids"] = list(list_ids)
        request = pb2.GetItemsRequest(**req_kwargs)
        items: list[dict[str, Any]] = []
        truncated = False
        for page in stub.GetItems(request, timeout=self.client.config.timeout):
            items.append(_summarize_item(self.client.message_to_dict(page)))
            if len(items) >= limit:
                truncated = True
                break
        return {"status": "ok", "count": len(items), "truncated": truncated, "items": items, "_req": req_kwargs}
