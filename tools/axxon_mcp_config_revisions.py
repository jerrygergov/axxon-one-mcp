#!/usr/bin/env python3
"""ConfigurationManager tools for Axxon One MCP.

Read config revision history (GetRevisionInfo) and probe backup collectibility
(CollectBackup). Both are reads, so there is no approval gate. CollectBackup is a server stream
of backup chunks; this tool only probes that a backup is collectible and tallies size, with
chunk/byte/time caps. The backup bytes are never persisted or returned. SetRevision and
RestoreBackup are exposed only behind explicit approval and per-call confirmation. Direct gRPC
against `ConfigurationManager`.
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

CONFIG_REVISIONS_PROTO = "axxonsoft/bl/maintenance/ConfigurationManager.proto"
CONFIG_REVISIONS_PB2 = "axxonsoft.bl.maintenance.ConfigurationManager_pb2"
CONFIG_REVISIONS_APPROVE_ENV = "AXXON_CONFIG_REVISIONS_APPROVE"
SET_REVISION_CONFIRMATION = "CONFIRM-config-set-revision"
RESTORE_BACKUP_CONFIRMATION = "CONFIRM-config-restore-backup"

CONFIG_REVISIONS_TOOL_NAMES = (
    "config_revisions_connect_axxon_profile",
    "get_revision_info",
    "collect_backup_probe",
    "set_revision",
    "restore_backup",
)

MAX_BACKUP_CHUNKS = 64
DEFAULT_BACKUP_CHUNKS = 8
MAX_BACKUP_BYTES = 16 * 1024 * 1024
DEFAULT_BACKUP_BYTES = 4 * 1024 * 1024
MAX_BACKUP_SECONDS = 30.0
DEFAULT_BACKUP_SECONDS = 10.0
MAX_RESTORE_CHUNK_KB = 1024
DEFAULT_RESTORE_CHUNK_KB = 64


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _approval_from_env() -> bool:
    return os.environ.get(CONFIG_REVISIONS_APPROVE_ENV) == "1"


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpConfigRevisions:
    """Phase A ConfigurationManager read tools (revision history + capped backup probe)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def config_revisions_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        mode = "read+maintenance" if self.enabled else "read"
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": mode,
            "approval_env": CONFIG_REVISIONS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.config_revisions_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.config_revisions_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(CONFIG_REVISIONS_PROTO, "ConfigurationManager"), client.import_module(CONFIG_REVISIONS_PB2)

    def get_revision_info(self, config_type: str = "LOCAL_CONFIG", nodes: list[str] | None = None) -> dict[str, Any]:
        """Read config revision history per node for a config type.

        Args:
            config_type (str, optional): "LOCAL_CONFIG" or "SHARED_CONFIG".
            nodes (list, optional): Node names to scope to; empty for all known nodes.

        Returns:
            (dict): {"status": "ok", "tool": "get_revision_info", "config_type", "nodes": {node: [revision...]}}.
        """
        stub, pb2 = self._stub_and_pb2()
        try:
            type_value = pb2.EConfigType.Value(config_type)
        except (KeyError, ValueError):
            return {"status": "gap", "tool": "get_revision_info", "message": f"Unknown config_type: {config_type!r}. Use 'LOCAL_CONFIG' or 'SHARED_CONFIG'."}
        request = pb2.GetRevisionInfoRequest(type=type_value, nodes=list(nodes or []))
        response = stub.GetRevisionInfo(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "tool": "get_revision_info",
            "config_type": config_type,
            "nodes": {node: [self._summarize_info(info) for info in info_list.info] for node, info_list in dict(response.info).items()},
        }

    @staticmethod
    def _summarize_info(info: Any) -> dict[str, Any]:
        return {"number": info.revision.number, "timestamp": info.timestamp, "is_current": info.is_current, "comment": info.comment}

    def collect_backup_probe(
        self,
        types: list[str] | None = None,
        node: str = "",
        max_chunks: int | None = None,
        max_bytes: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Probe that a backup is collectible and tally its size, without persisting the bytes.

        Streams CollectBackup chunks only to confirm collectibility and measure size, stopping at
        the chunk, byte, or time cap. The backup blob is never written to disk or returned.

        Args:
            types (list, optional): Backup parts, any of "LOCAL", "SHARED", "LICENSE", "TICKETS".
            node (str, optional): Node to collect from; empty for the current node.
            max_chunks (int, optional): Chunk cap; clamped to MAX_BACKUP_CHUNKS.
            max_bytes (int, optional): Byte cap; clamped to MAX_BACKUP_BYTES.
            timeout (float, optional): Wall-clock cap in seconds; clamped to MAX_BACKUP_SECONDS.

        Returns:
            (dict): {"status": "ok", "tool": "collect_backup_probe", "chunks_seen", "bytes_seen", "total_size_bytes", "truncated", "stop_reason"}.
        """
        stub, pb2 = self._stub_and_pb2()
        type_values = []
        for name in types or ["LOCAL"]:
            try:
                type_values.append(pb2.CollectBackupRequest.EBackupType.Value(name))
            except (KeyError, ValueError):
                return {"status": "gap", "tool": "collect_backup_probe", "message": f"Unknown backup type: {name!r}. Use LOCAL, SHARED, LICENSE, or TICKETS."}
        chunk_cap = int(_clamp(float(max_chunks if max_chunks is not None else DEFAULT_BACKUP_CHUNKS), 1, MAX_BACKUP_CHUNKS))
        byte_cap = int(_clamp(float(max_bytes if max_bytes is not None else DEFAULT_BACKUP_BYTES), 1, MAX_BACKUP_BYTES))
        deadline_s = _clamp(float(timeout if timeout is not None else DEFAULT_BACKUP_SECONDS), 1.0, MAX_BACKUP_SECONDS)

        request = pb2.CollectBackupRequest(type=type_values, node=node)
        deadline = time.monotonic() + deadline_s
        chunks_seen = 0
        bytes_seen = 0
        total_size_bytes = 0
        truncated = False
        stop_reason = "completed"
        for chunk in stub.CollectBackup(request, timeout=deadline_s):
            total_size_bytes = chunk.total_size_bytes
            chunks_seen += 1
            bytes_seen += len(chunk.chunk_data)
            if chunks_seen >= chunk_cap:
                truncated, stop_reason = True, "chunk_cap"
                break
            if bytes_seen >= byte_cap:
                truncated, stop_reason = True, "byte_cap"
                break
            if time.monotonic() > deadline:
                truncated, stop_reason = True, "time_cap"
                break
        return {
            "status": "ok",
            "tool": "collect_backup_probe",
            "chunks_seen": chunks_seen,
            "bytes_seen": bytes_seen,
            "total_size_bytes": total_size_bytes,
            "truncated": truncated,
            "stop_reason": stop_reason,
        }

    def _write_gate(self, confirmation: str, expected: str, action: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {
                "status": "disabled",
                "message": f"Set {CONFIG_REVISIONS_APPROVE_ENV}=1 to enable {action}.",
                "approval_env": CONFIG_REVISIONS_APPROVE_ENV,
            }
        if confirmation != expected:
            return {"status": "gap", "message": f"{action} requires confirmation={expected}"}
        return None

    def set_revision(
        self,
        config_type: str = "LOCAL_CONFIG",
        node: str = "",
        revision_number: int = 0,
        revision_hash: str = "",
        comment: str = "",
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Set the active configuration revision. Approval-gated and confirmation-gated."""
        gated = self._write_gate(confirmation, SET_REVISION_CONFIRMATION, "set_revision")
        if gated is not None:
            return {"tool": "set_revision", **gated}
        if not node:
            return {"status": "error", "tool": "set_revision", "message": "node is required."}
        stub, pb2 = self._stub_and_pb2()
        try:
            type_value = pb2.EConfigType.Value(config_type)
        except (KeyError, ValueError):
            return {"status": "gap", "tool": "set_revision", "message": f"Unknown config_type: {config_type!r}. Use 'LOCAL_CONFIG' or 'SHARED_CONFIG'."}
        revision = pb2.Revision(number=int(revision_number), hash=revision_hash)
        request = pb2.SetRevisionRequest(type=type_value, node=node, revision=revision, comment=comment)
        stub.SetRevision(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "applied",
            "tool": "set_revision",
            "config_type": config_type,
            "node": node,
            "revision": {"number": int(revision_number), "hash": revision_hash},
            "comment_length": len(comment or ""),
        }

    def restore_backup(
        self,
        types: list[str] | None = None,
        node: str = "",
        backup_base64: str = "",
        backup_hex: str = "",
        chunk_size_kb: int = DEFAULT_RESTORE_CHUNK_KB,
        max_bytes: int | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Restore a config backup from base64/hex data. Approval-gated and byte/chunk capped."""
        gated = self._write_gate(confirmation, RESTORE_BACKUP_CONFIRMATION, "restore_backup")
        if gated is not None:
            return {"tool": "restore_backup", **gated}
        if not backup_base64 and not backup_hex:
            return {"status": "error", "tool": "restore_backup", "message": "provide backup_base64 or backup_hex."}
        try:
            backup_bytes = base64.b64decode(backup_base64, validate=True) if backup_base64 else bytes.fromhex(backup_hex)
        except (ValueError, TypeError) as exc:
            return {"status": "error", "tool": "restore_backup", "message": f"backup data could not be decoded: {exc}"}
        byte_cap = int(_clamp(float(max_bytes if max_bytes is not None else DEFAULT_BACKUP_BYTES), 1, MAX_BACKUP_BYTES))
        if len(backup_bytes) > byte_cap:
            return {
                "status": "refused",
                "tool": "restore_backup",
                "message": "backup data exceeds max_bytes cap.",
                "bytes_provided": len(backup_bytes),
                "max_bytes": byte_cap,
            }
        chunk_bytes = int(_clamp(float(chunk_size_kb or DEFAULT_RESTORE_CHUNK_KB), 1, MAX_RESTORE_CHUNK_KB)) * 1024
        stub, pb2 = self._stub_and_pb2()
        type_values = []
        for name in types or ["LOCAL"]:
            try:
                type_values.append(pb2.RestoreBackupRequest.ERestoreType.Value(name))
            except (KeyError, ValueError):
                return {"status": "gap", "tool": "restore_backup", "message": f"Unknown restore type: {name!r}."}

        def requests() -> Any:
            initial = pb2.RestoreBackupRequest.InitialData(
                type=type_values,
                node=node,
                total_size_bytes=len(backup_bytes),
            )
            yield pb2.RestoreBackupRequest(initial_data=initial)
            for offset in range(0, len(backup_bytes), chunk_bytes):
                yield pb2.RestoreBackupRequest(chunk_data=backup_bytes[offset : offset + chunk_bytes])

        stub.RestoreBackup(requests(), timeout=self.ensure_client().config.timeout)
        chunks_sent = (len(backup_bytes) + chunk_bytes - 1) // chunk_bytes if backup_bytes else 0
        return {
            "status": "applied",
            "tool": "restore_backup",
            "types": list(types or ["LOCAL"]),
            "node": node,
            "bytes_sent": len(backup_bytes),
            "chunks_sent": chunks_sent,
            "chunk_size_kb": chunk_bytes // 1024,
        }
