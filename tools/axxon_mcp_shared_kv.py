#!/usr/bin/env python3
"""SharedKVStorageService tools for Axxon One MCP (Phase A).

Read the shared key-value store used by plugins and integrations (ListRecords,
BatchGetRecords, GetRecordsStream) and commit records (Commit). The three reads are ungated;
Commit is the one mutation, approval-gated (`AXXON_SHARED_KV_APPROVE=1`) plus a per-call
confirmation token, mirroring the ServerSettings idiom. Commit uses optimistic concurrency via
each record's `revision`, so a caller rolls back by committing the prior revision (or removing
the key). Record values are opaque bytes: a value is surfaced as text only when it decodes as
UTF-8, otherwise only its size is reported. Direct gRPC against `SharedKVStorageService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

SHARED_KV_APPROVE_ENV = "AXXON_SHARED_KV_APPROVE"
SHARED_KV_CONFIRMATION = "CONFIRM-shared-kv-commit"
SHARED_KV_PROTO = "axxonsoft/bl/config/SharedKeyValueStorage.proto"
SHARED_KV_PB2 = "axxonsoft.bl.config.SharedKeyValueStorage_pb2"

SHARED_KV_TOOL_NAMES = (
    "shared_kv_connect_axxon_profile",
    "list_records",
    "get_records",
    "get_records_stream",
    "commit_record",
)

MAX_CHUNKS = 256
DEFAULT_CHUNKS = 32
MAX_VALUE_TEXT_BYTES = 4096


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _approval_from_env() -> bool:
    return os.environ.get(SHARED_KV_APPROVE_ENV) == "1"


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpSharedKv:
    """Phase A SharedKVStorageService tools (reads + gated Commit)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def shared_kv_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": SHARED_KV_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.shared_kv_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.shared_kv_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(SHARED_KV_PROTO, "SharedKVStorageService"), client.import_module(SHARED_KV_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {SHARED_KV_APPROVE_ENV}=1 to enable shared-KV writes.", "approval_env": SHARED_KV_APPROVE_ENV}
        if confirmation != SHARED_KV_CONFIRMATION:
            return {"status": "gap", "message": f"shared-KV commit requires confirmation={SHARED_KV_CONFIRMATION}"}
        return None

    def _view_value(self, pb2: Any, view: str) -> int | None:
        if not view:
            return 0
        try:
            return pb2.ESharedKVRecordView.Value(view)
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _record_summary(record: Any) -> dict[str, Any]:
        value = record.value
        try:
            text = value.decode("utf-8") if len(value) <= MAX_VALUE_TEXT_BYTES else None
        except UnicodeDecodeError:
            text = None
        return {"key": record.key, "revision": record.revision, "value_size_bytes": len(value), "value_text": text}

    def list_records(self, prefix: str = "", view: str = "") -> dict[str, Any]:
        """List shared-KV records under a key prefix (deprecated server RPC; reads are safe)."""
        stub, pb2 = self._stub_and_pb2()
        view_value = self._view_value(pb2, view)
        if view_value is None:
            return {"status": "gap", "tool": "list_records", "message": f"Unknown view: {view!r}. Use ESHKV_FULL or ESHKV_STRIPPED."}
        response = stub.ListRecords(pb2.ListRecordsRequest(prefix=prefix, view=view_value), timeout=self.ensure_client().config.timeout)
        items = list(response.items)
        return {"status": "ok", "tool": "list_records", "count": len(items), "records": [self._record_summary(r) for r in items]}

    def get_records(self, keys: list[str] | None = None, prefix: str = "", view: str = "") -> dict[str, Any]:
        """Batch-read specific shared-KV records by key (optionally under a prefix)."""
        stub, pb2 = self._stub_and_pb2()
        view_value = self._view_value(pb2, view)
        if view_value is None:
            return {"status": "gap", "tool": "get_records", "message": f"Unknown view: {view!r}. Use ESHKV_FULL or ESHKV_STRIPPED."}
        request = pb2.BatchGetRecordsRequest(prefix=prefix, view=view_value)
        for key in keys or []:
            request.items.add(key=key)
        response = stub.BatchGetRecords(request, timeout=self.ensure_client().config.timeout)
        items = list(response.items)
        return {"status": "ok", "tool": "get_records", "count": len(items), "records": [self._record_summary(r) for r in items]}

    def get_records_stream(self, prefix: str = "", view: str = "", max_chunks: int | None = None) -> dict[str, Any]:
        """Stream shared-KV record chunks under a prefix (chunk-capped); values not returned."""
        stub, pb2 = self._stub_and_pb2()
        view_value = self._view_value(pb2, view)
        if view_value is None:
            return {"status": "gap", "tool": "get_records_stream", "message": f"Unknown view: {view!r}. Use ESHKV_FULL or ESHKV_STRIPPED."}
        cap = _clamp(int(max_chunks if max_chunks is not None else DEFAULT_CHUNKS), 1, MAX_CHUNKS)
        request = pb2.GetRecordsStreamRequest(prefix=prefix, view=view_value)
        keys: list[str] = []
        chunks_seen = 0
        bytes_seen = 0
        truncated = False
        for chunk in stub.GetRecordsStream(request, timeout=self.ensure_client().config.timeout):
            keys.append(chunk.info.key)
            chunks_seen += 1
            bytes_seen += len(chunk.chunk_data)
            if chunks_seen >= cap:
                truncated = True
                break
        return {"status": "ok", "tool": "get_records_stream", "chunks_seen": chunks_seen, "bytes_seen": bytes_seen, "keys": list(dict.fromkeys(keys)), "truncated": truncated}

    def commit_record(
        self,
        prefix: str = "",
        set_records: list[dict[str, Any]] | None = None,
        removed: list[dict[str, Any]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Commit shared-KV records (set and/or remove). Approval-gated + per-call confirmation.

        Uses optimistic concurrency via each record's `revision`; roll back by committing the
        prior revision or removing the key. Requires AXXON_SHARED_KV_APPROVE=1 and
        confirmation=CONFIRM-shared-kv-commit.

        Args:
            prefix (str, optional): Key prefix scope for the commit.
            set_records (list, optional): Records to set, each {"key", "value", "revision"}.
            removed (list, optional): Records to remove, each {"key", "revision"}.
            confirmation (str): Must equal CONFIRM-shared-kv-commit.

        Returns:
            (dict): {"status": "applied", "tool": "commit_record", "error_code", "updated"} or a gate dict.
        """
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        stub, pb2 = self._stub_and_pb2()
        request = pb2.SharedKVCommitRequest(prefix=prefix)
        for record in set_records or []:
            value = record.get("value", "")
            request.set.add(key=record.get("key", ""), revision=record.get("revision", ""), value=value.encode("utf-8") if isinstance(value, str) else value)
        for record in removed or []:
            request.removed.add(key=record.get("key", ""), revision=record.get("revision", ""))
        response = stub.Commit(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "applied",
            "tool": "commit_record",
            "error_code": pb2.SharedKVCommitResponse.EErrorCode.Name(response.error_code),
            "updated": [{"key": info.key, "revision": info.revision} for info in response.updated],
        }
