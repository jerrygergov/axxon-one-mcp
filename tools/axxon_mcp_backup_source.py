#!/usr/bin/env python3
"""BackupSourceService tools for Axxon One MCP."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary


BACKUP_SOURCE_APPROVE_ENV = "AXXON_BACKUP_SOURCE_APPROVE"
BACKUP_SOURCE_CONFIRMATION = "CONFIRM-backup-source"
BACKUP_SOURCE_PROTO = "axxonsoft/bl/archive/BackupSource.proto"
BACKUP_SOURCE_PB2 = "axxonsoft.bl.archive.BackupSource_pb2"

BACKUP_SOURCE_TOOL_NAMES = (
    "backup_source_connect_axxon_profile",
    "bundle_backup",
    "make_backup",
    "cancel_backup",
)

DEFAULT_BUNDLE_ITEMS = 8
MAX_BUNDLE_ITEMS = 64
DEFAULT_BUNDLE_TIMEOUT_S = 10.0
MAX_BUNDLE_TIMEOUT_S = 60.0


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(BACKUP_SOURCE_APPROVE_ENV) == "1"


def _cap_int(value: int | float | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value not in (None, 0) else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _cap_float(value: int | float | None, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value) if value not in (None, 0) else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _status_name(value: int) -> str:
    return {0: "BUSY", 1: "DONE"}.get(int(value), f"UNRECOGNIZED_{value}")


@dataclass
class AxxonMcpBackupSource:
    """BackupSourceService status and control tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def backup_source_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+backup-control",
            "approval_env": BACKUP_SOURCE_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.backup_source_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.backup_source_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(BACKUP_SOURCE_PROTO, "BackupSourceService"), client.import_module(BACKUP_SOURCE_PB2)

    def _intervals(self, pb2: Any, intervals: list[dict[str, Any]] | None) -> list[Any]:
        out = []
        for interval in intervals or []:
            begin = interval.get("begin_time", interval.get("beginTime", 0))
            end = interval.get("end_time", interval.get("endTime", 0))
            out.append(pb2.BackupTimeInterval(beginTime=int(begin), endTime=int(end)))
        return out

    def _write_gate(self, confirmation: str, action: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {BACKUP_SOURCE_APPROVE_ENV}=1 to enable {action}.", "approval_env": BACKUP_SOURCE_APPROVE_ENV}
        if confirmation != BACKUP_SOURCE_CONFIRMATION:
            return {"status": "gap", "message": f"{action} requires confirmation={BACKUP_SOURCE_CONFIRMATION}"}
        return None

    def bundle_backup(
        self,
        access_points: list[str] | None = None,
        intervals: list[dict[str, Any]] | None = None,
        report_timeout_sec: int = 1,
        max_items: int = DEFAULT_BUNDLE_ITEMS,
        timeout_s: float = DEFAULT_BUNDLE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Run a bounded BundleBackup status sample. No backup bytes are returned by this RPC."""
        aps = [ap for ap in (access_points or []) if ap]
        if not aps:
            return {"status": "error", "tool": "bundle_backup", "message": "provide at least one access point."}
        stub, pb2 = self._stub_and_pb2()
        item_cap = _cap_int(max_items, default=DEFAULT_BUNDLE_ITEMS, minimum=1, maximum=MAX_BUNDLE_ITEMS)
        timeout = _cap_float(timeout_s, default=DEFAULT_BUNDLE_TIMEOUT_S, minimum=1.0, maximum=MAX_BUNDLE_TIMEOUT_S)
        request = pb2.BundleBackupRequest(
            access_points=aps,
            intervals=self._intervals(pb2, intervals),
            report_timeout_sec=max(1, int(report_timeout_sec or 1)),
        )
        items: list[dict[str, Any]] = []
        stop_reason = "completed"
        deadline = time.monotonic() + timeout
        for response in stub.BundleBackup(request, timeout=timeout):
            items.append(
                {
                    "remainder_ms": int(getattr(response, "remainder_ms", 0)),
                    "status": _status_name(getattr(response, "status", 0)),
                    "status_code": int(getattr(response, "status", 0)),
                }
            )
            if len(items) >= item_cap:
                stop_reason = "item_cap"
                break
            if time.monotonic() > deadline:
                stop_reason = "time_cap"
                break
        return {
            "status": "ok",
            "tool": "bundle_backup",
            "items": items,
            "items_seen": len(items),
            "truncated": stop_reason != "completed",
            "stop_reason": stop_reason,
        }

    def make_backup(self, access_point: str = "", intervals: list[dict[str, Any]] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Start MakeBackup. Approval-gated and confirmation-gated."""
        gated = self._write_gate(confirmation, "make_backup")
        if gated is not None:
            return {"tool": "make_backup", **gated}
        if not access_point:
            return {"status": "error", "tool": "make_backup", "message": "access_point is required."}
        stub, pb2 = self._stub_and_pb2()
        response = stub.MakeBackup(
            pb2.MakeBackupRequest(access_point=access_point, intervals=self._intervals(pb2, intervals)),
            timeout=self.ensure_client().config.timeout,
        )
        return {
            "status": "started",
            "tool": "make_backup",
            "access_point": access_point,
            "task_id": getattr(response, "task_id", ""),
            "worker_id": getattr(response, "worker_id", ""),
        }

    def cancel_backup(self, access_point: str = "", task_id: str = "", confirmation: str = "") -> dict[str, Any]:
        """Cancel MakeBackup. Approval-gated and confirmation-gated."""
        gated = self._write_gate(confirmation, "cancel_backup")
        if gated is not None:
            return {"tool": "cancel_backup", **gated}
        if not access_point or not task_id:
            return {"status": "error", "tool": "cancel_backup", "message": "access_point and task_id are required."}
        stub, pb2 = self._stub_and_pb2()
        stub.CancelBackup(pb2.CancelBackupRequest(access_point=access_point, task_id=task_id), timeout=self.ensure_client().config.timeout)
        return {"status": "cancelled", "tool": "cancel_backup", "access_point": access_point, "task_id": task_id}
