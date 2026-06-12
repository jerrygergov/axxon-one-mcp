#!/usr/bin/env python3
"""First-class ExportService tools for Axxon One MCP.

The export group starts only short snapshot exports, tracks sessions it owns in memory, and
downloads generated files through strict byte/chunk/path caps. Tool responses are metadata-only:
raw export bytes are never returned.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary


EXPORT_APPROVE_ENV = "AXXON_EXPORT_APPROVE"
EXPORT_CONFIRMATION = "CONFIRM-export"

EXPORT_SERVICE_PROTO = "axxonsoft/bl/mmexport/ExportService.proto"
EXPORT_SERVICE_PB2 = "axxonsoft.bl.mmexport.ExportService_pb2"
EXPORT_PB2 = "axxonsoft.bl.mmexport.Export_pb2"

DEFAULT_EXPORT_FILE_SIZE = 1_048_576
MAX_EXPORT_FILE_SIZE = 16_777_216
DEFAULT_DOWNLOAD_BYTES = 262_144
MAX_DOWNLOAD_BYTES = 4_194_304
DEFAULT_DOWNLOAD_CHUNKS = 16
MAX_DOWNLOAD_CHUNKS = 64
DEFAULT_CHUNK_SIZE_KB = 64
MAX_CHUNK_SIZE_KB = 256
DEFAULT_EXPORT_TIMEOUT_S = 10.0
MAX_EXPORT_TIMEOUT_S = 60.0

OWNED_MARKER_PREFIX = "codex-owned-export"
DEFAULT_ARTIFACT_SUBDIR = Path(".agent") / "export-artifacts"

EXPORT_TOOL_NAMES = (
    "export_connect_axxon_profile",
    "export_plan_snapshot",
    "export_start_snapshot",
    "export_status",
    "export_download",
    "export_stop",
    "export_destroy",
    "export_cleanup_owned",
)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def default_artifact_root() -> Path:
    return Path(__file__).resolve().parents[1] / DEFAULT_ARTIFACT_SUBDIR


def _approval_from_env() -> bool:
    return os.environ.get(EXPORT_APPROVE_ENV) == "1"


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


def _safe_stem(value: str = "") -> str:
    stem = _SAFE_NAME_RE.sub("-", (value or "").strip()).strip(".-_")
    return stem[:64] or "snapshot"


def _session_token(session_id: str) -> str:
    safe = _SAFE_NAME_RE.sub("-", session_id).strip(".-_")
    return safe[:40] or uuid.uuid4().hex[:12]


@dataclass
class ExportCaps:
    max_file_size: int = DEFAULT_EXPORT_FILE_SIZE
    max_download_bytes: int = DEFAULT_DOWNLOAD_BYTES
    max_chunks: int = DEFAULT_DOWNLOAD_CHUNKS
    chunk_size_kb: int = DEFAULT_CHUNK_SIZE_KB
    timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S

    @classmethod
    def from_inputs(
        cls,
        *,
        max_file_size: int = DEFAULT_EXPORT_FILE_SIZE,
        max_download_bytes: int = DEFAULT_DOWNLOAD_BYTES,
        max_chunks: int = DEFAULT_DOWNLOAD_CHUNKS,
        chunk_size_kb: int = DEFAULT_CHUNK_SIZE_KB,
        timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S,
    ) -> "ExportCaps":
        return cls(
            max_file_size=_cap_int(max_file_size, default=DEFAULT_EXPORT_FILE_SIZE, minimum=1, maximum=MAX_EXPORT_FILE_SIZE),
            max_download_bytes=_cap_int(max_download_bytes, default=DEFAULT_DOWNLOAD_BYTES, minimum=1, maximum=MAX_DOWNLOAD_BYTES),
            max_chunks=_cap_int(max_chunks, default=DEFAULT_DOWNLOAD_CHUNKS, minimum=1, maximum=MAX_DOWNLOAD_CHUNKS),
            chunk_size_kb=_cap_int(chunk_size_kb, default=DEFAULT_CHUNK_SIZE_KB, minimum=1, maximum=MAX_CHUNK_SIZE_KB),
            timeout_s=_cap_float(timeout_s, default=DEFAULT_EXPORT_TIMEOUT_S, minimum=1.0, maximum=MAX_EXPORT_TIMEOUT_S),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_file_size": self.max_file_size,
            "max_download_bytes": self.max_download_bytes,
            "max_chunks": self.max_chunks,
            "chunk_size_kb": self.chunk_size_kb,
            "timeout_s": self.timeout_s,
        }


@dataclass
class OwnedExportSession:
    session_id: str
    marker: str
    file_name: str
    caps: ExportCaps
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "marker": self.marker,
            "file_name": self.file_name,
            "caps": self.caps.to_dict(),
        }


@dataclass
class AxxonMcpExport:
    """ExportService snapshot/session tools with approval gates and local ownership tracking."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    artifact_root_factory: Callable[[], Path] = default_artifact_root
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None
    owned_sessions: dict[str, OwnedExportSession] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def export_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+export",
            "approval_env": EXPORT_APPROVE_ENV,
            "enabled": bool(self.enabled),
            "artifact_root": str(self.artifact_root_factory()),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.export_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.export_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        stub = client.stub_from_proto(EXPORT_SERVICE_PROTO, "ExportService")
        return stub, client.import_module(EXPORT_PB2), client.import_module(EXPORT_SERVICE_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {EXPORT_APPROVE_ENV}=1 to enable export actions.", "approval_env": EXPORT_APPROVE_ENV}
        if confirmation != EXPORT_CONFIRMATION:
            return {"status": "gap", "message": f"export actions require confirmation={EXPORT_CONFIRMATION}"}
        return None

    def _owned_or_refused(self, session_id: str, tool: str) -> OwnedExportSession | dict[str, Any]:
        if not session_id:
            return {"status": "error", "tool": tool, "message": "provide session_id"}
        owned = self.owned_sessions.get(session_id)
        if owned is None:
            return {"status": "refused", "tool": tool, "message": "session is not owned by this export tool"}
        return owned

    def _snapshot_plan(
        self,
        *,
        camera_access_point: str,
        archive_access_point: str,
        timestamp: str,
        max_file_size: int = DEFAULT_EXPORT_FILE_SIZE,
        max_download_bytes: int = DEFAULT_DOWNLOAD_BYTES,
        max_chunks: int = DEFAULT_DOWNLOAD_CHUNKS,
        chunk_size_kb: int = DEFAULT_CHUNK_SIZE_KB,
        timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S,
        filename_stem: str = "",
    ) -> dict[str, Any]:
        missing = [
            name
            for name, value in (
                ("camera_access_point", camera_access_point),
                ("archive_access_point", archive_access_point),
                ("timestamp", timestamp),
            )
            if not value
        ]
        caps = ExportCaps.from_inputs(
            max_file_size=max_file_size,
            max_download_bytes=max_download_bytes,
            max_chunks=max_chunks,
            chunk_size_kb=chunk_size_kb,
            timeout_s=timeout_s,
        )
        safe_stem = _safe_stem(filename_stem)
        return {
            "missing": missing,
            "caps": caps,
            "file_name": f"codex-export-{safe_stem}-{uuid.uuid4().hex[:12]}",
            "options": {
                "mode": "archive_snapshot",
                "snapshot_format": "JPEG",
                "camera_access_point": camera_access_point,
                "archive_access_point": archive_access_point,
                "timestamp": timestamp,
                "max_file_size": caps.max_file_size,
                "store_result_by_export_agent": False,
            },
        }

    def export_plan_snapshot(
        self,
        camera_access_point: str = "",
        archive_access_point: str = "",
        timestamp: str = "",
        max_file_size: int = DEFAULT_EXPORT_FILE_SIZE,
        max_download_bytes: int = DEFAULT_DOWNLOAD_BYTES,
        max_chunks: int = DEFAULT_DOWNLOAD_CHUNKS,
        chunk_size_kb: int = DEFAULT_CHUNK_SIZE_KB,
        timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S,
        filename_stem: str = "",
    ) -> dict[str, Any]:
        plan = self._snapshot_plan(
            camera_access_point=camera_access_point,
            archive_access_point=archive_access_point,
            timestamp=timestamp,
            max_file_size=max_file_size,
            max_download_bytes=max_download_bytes,
            max_chunks=max_chunks,
            chunk_size_kb=chunk_size_kb,
            timeout_s=timeout_s,
            filename_stem=filename_stem,
        )
        if plan["missing"]:
            return {"status": "error", "tool": "export_plan_snapshot", "message": "missing required inputs", "missing": plan["missing"]}
        return {
            "status": "planned",
            "tool": "export_plan_snapshot",
            "approval_env": EXPORT_APPROVE_ENV,
            "confirmation": EXPORT_CONFIRMATION,
            "options": {**plan["options"], "file_name": plan["file_name"]},
            "caps": plan["caps"].to_dict(),
        }

    def _build_snapshot_options(self, export_pb2: Any, plan: dict[str, Any], marker: str) -> Any:
        options = plan["options"]
        return export_pb2.Options(
            archive=export_pb2.ArchiveMode(
                sources=[
                    export_pb2.ArchiveMode.Source(
                        origin=options["camera_access_point"],
                        storages=[options["archive_access_point"]],
                    )
                ],
                start_timestamp=options["timestamp"],
            ),
            snapshot=export_pb2.SnapshotType(format=getattr(export_pb2.SnapshotType, "JPEG", 1)),
            settings=[
                export_pb2.CommonSetting(file_name=plan["file_name"]),
                export_pb2.CommonSetting(comment=marker),
            ],
            max_file_size=plan["caps"].max_file_size,
            store_result_by_export_agent=False,
        )

    def export_start_snapshot(
        self,
        camera_access_point: str = "",
        archive_access_point: str = "",
        timestamp: str = "",
        confirmation: str = "",
        max_file_size: int = DEFAULT_EXPORT_FILE_SIZE,
        max_download_bytes: int = DEFAULT_DOWNLOAD_BYTES,
        max_chunks: int = DEFAULT_DOWNLOAD_CHUNKS,
        chunk_size_kb: int = DEFAULT_CHUNK_SIZE_KB,
        timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S,
        filename_stem: str = "",
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "export_start_snapshot", **gated}
        plan = self._snapshot_plan(
            camera_access_point=camera_access_point,
            archive_access_point=archive_access_point,
            timestamp=timestamp,
            max_file_size=max_file_size,
            max_download_bytes=max_download_bytes,
            max_chunks=max_chunks,
            chunk_size_kb=chunk_size_kb,
            timeout_s=timeout_s,
            filename_stem=filename_stem,
        )
        if plan["missing"]:
            return {"status": "error", "tool": "export_start_snapshot", "message": "missing required inputs", "missing": plan["missing"]}
        marker = f"{OWNED_MARKER_PREFIX}:{uuid.uuid4().hex}"
        try:
            stub, export_pb2, service_pb2 = self._stub_and_pb2()
            options = self._build_snapshot_options(export_pb2, plan, marker)
            response = stub.StartSession(service_pb2.StartSessionRequest(session_options=options), timeout=plan["caps"].timeout_s)
            session_id = str(getattr(response, "started_session_id", ""))
            if not session_id:
                return {"status": "error", "tool": "export_start_snapshot", "message": "ExportService.StartSession returned no session id"}
            owned = OwnedExportSession(session_id=session_id, marker=marker, file_name=plan["file_name"], caps=plan["caps"])
            self.owned_sessions[session_id] = owned
            return {
                "status": "started",
                "tool": "export_start_snapshot",
                "session_id": session_id,
                "ownership": owned.public(),
                "options": {**plan["options"], "file_name": plan["file_name"]},
                "caps": plan["caps"].to_dict(),
                "approval_env": EXPORT_APPROVE_ENV,
            }
        except Exception as exc:
            return {"status": "error", "tool": "export_start_snapshot", "error_type": exc.__class__.__name__, "message": str(exc)[:300]}

    def _state_name(self, service_pb2: Any, value: Any) -> str:
        try:
            return service_pb2.EState.Name(int(value))
        except Exception:
            return str(value)

    def _file_summary(self, file_obj: Any) -> dict[str, Any]:
        return {
            "file_path": str(getattr(file_obj, "path", "")),
            "size": int(getattr(file_obj, "size", 0)),
            "min_timestamp": str(getattr(file_obj, "min_timestamp", "")),
            "max_timestamp": str(getattr(file_obj, "max_timestamp", "")),
            "mime_type": str(getattr(file_obj, "mime_type", "")),
            "cloud_id_present": bool(getattr(file_obj, "cloud_id", "")),
            "timezone": int(getattr(file_obj, "timezone", 0)),
        }

    def _state_summary(self, service_pb2: Any, state: Any) -> dict[str, Any]:
        result = getattr(state, "result", None)
        files = list(getattr(result, "files", []) or []) if result is not None else []
        return {
            "state": self._state_name(service_pb2, getattr(state, "state", 0)),
            "state_code": int(getattr(state, "state", 0)),
            "last_frame_timestamp": str(getattr(state, "last_frame_timestamp", "")),
            "succeeded": bool(getattr(result, "succeeded", False)) if result is not None else False,
            "file_count": len(files),
            "files": [self._file_summary(file_obj) for file_obj in files[:8]],
        }

    def export_status(self, session_id: str = "") -> dict[str, Any]:
        owned = self._owned_or_refused(session_id, "export_status")
        if isinstance(owned, dict):
            return owned
        try:
            stub, _, service_pb2 = self._stub_and_pb2()
            response = stub.GetSessionState(service_pb2.GetSessionStateRequest(session_id=session_id), timeout=owned.caps.timeout_s)
            summary = self._state_summary(service_pb2, getattr(response, "session_state", None))
            return {"status": "ok", "tool": "export_status", "session_id": session_id, **summary}
        except Exception as exc:
            return {"status": "error", "tool": "export_status", "session_id": session_id, "error_type": exc.__class__.__name__, "message": str(exc)[:300]}

    def _safe_destination(self, destination_name: str, session_id: str) -> tuple[Path | None, dict[str, Any] | None]:
        root = self.artifact_root_factory()
        if root.exists() and root.is_symlink():
            return None, {"status": "error", "tool": "export_download", "message": "artifact root must not be a symlink"}
        name = destination_name or f"export-{_session_token(session_id)}.bin"
        if Path(name).is_absolute() or "/" in name or "\\" in name or name in (".", "..") or ".." in name.split("."):
            return None, {"status": "error", "tool": "export_download", "message": "destination_name must be a simple filename under the export artifact root"}
        safe = _SAFE_NAME_RE.sub("-", name).strip(".-_")
        if not safe:
            return None, {"status": "error", "tool": "export_download", "message": "destination_name is empty after sanitization"}
        root.mkdir(parents=True, exist_ok=True)
        root_resolved = root.resolve()
        destination = root / safe
        if destination.exists() and destination.is_symlink():
            return None, {"status": "error", "tool": "export_download", "message": "destination must not be a symlink"}
        if destination.parent.resolve() != root_resolved:
            return None, {"status": "error", "tool": "export_download", "message": "destination escaped the export artifact root"}
        return destination, None

    def export_download(
        self,
        session_id: str = "",
        file_path: str = "",
        confirmation: str = "",
        destination_name: str = "",
        max_bytes: int = DEFAULT_DOWNLOAD_BYTES,
        max_chunks: int = DEFAULT_DOWNLOAD_CHUNKS,
        chunk_size_kb: int = DEFAULT_CHUNK_SIZE_KB,
        timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S,
        save: bool = True,
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "export_download", **gated}
        owned = self._owned_or_refused(session_id, "export_download")
        if isinstance(owned, dict):
            return owned
        if not file_path:
            return {"status": "error", "tool": "export_download", "message": "provide file_path from export_status"}
        caps = ExportCaps.from_inputs(
            max_file_size=owned.caps.max_file_size,
            max_download_bytes=max_bytes,
            max_chunks=max_chunks,
            chunk_size_kb=chunk_size_kb,
            timeout_s=timeout_s,
        )
        destination = None
        if save:
            destination, error = self._safe_destination(destination_name, session_id)
            if error is not None:
                return error
        digest = hashlib.sha256()
        bytes_seen = 0
        chunks_seen = 0
        truncated = False
        mime_type = mimetypes.guess_type(destination_name or file_path)[0] or "application/octet-stream"
        started = time.monotonic()
        try:
            stub, _, service_pb2 = self._stub_and_pb2()
            request = service_pb2.DownloadFileRequest(
                session_id=session_id,
                file_path=file_path,
                chunk_size_kb=caps.chunk_size_kb,
            )
            file_handle = destination.open("wb") if destination is not None else None
            try:
                for chunk in stub.DownloadFile(request, timeout=caps.timeout_s):
                    if time.monotonic() - started > caps.timeout_s:
                        truncated = True
                        break
                    if chunks_seen >= caps.max_chunks or bytes_seen >= caps.max_download_bytes:
                        truncated = True
                        break
                    data = bytes(getattr(chunk, "data", b""))
                    chunks_seen += 1
                    remaining = caps.max_download_bytes - bytes_seen
                    piece = data[:remaining]
                    if len(piece) < len(data):
                        truncated = True
                    if piece:
                        digest.update(piece)
                        if file_handle is not None:
                            file_handle.write(piece)
                        bytes_seen += len(piece)
                    if bytes_seen >= caps.max_download_bytes:
                        truncated = True
                        break
            finally:
                if file_handle is not None:
                    file_handle.close()
            return {
                "status": "ok",
                "tool": "export_download",
                "session_id": session_id,
                "file_path": file_path,
                "bytes_seen": bytes_seen,
                "chunks_seen": chunks_seen,
                "sha256": digest.hexdigest() if bytes_seen else "",
                "truncated": truncated,
                "mime_type": mime_type,
                "chunk_size_kb": caps.chunk_size_kb,
                "max_bytes": caps.max_download_bytes,
                "max_chunks": caps.max_chunks,
                "saved_path": str(destination) if destination is not None else "",
            }
        except Exception as exc:
            return {"status": "error", "tool": "export_download", "session_id": session_id, "error_type": exc.__class__.__name__, "message": str(exc)[:300]}

    def export_stop(self, session_id: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "export_stop", **gated}
        owned = self._owned_or_refused(session_id, "export_stop")
        if isinstance(owned, dict):
            return owned
        try:
            stub, _, service_pb2 = self._stub_and_pb2()
            response = stub.StopSession(service_pb2.StopSessionRequest(session_id=session_id), timeout=owned.caps.timeout_s)
            summary = self._state_summary(service_pb2, getattr(response, "session_state", None))
            return {"status": "stopped", "tool": "export_stop", "session_id": session_id, **summary}
        except Exception as exc:
            return {"status": "error", "tool": "export_stop", "session_id": session_id, "error_type": exc.__class__.__name__, "message": str(exc)[:300]}

    def export_destroy(self, session_id: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "export_destroy", **gated}
        owned = self._owned_or_refused(session_id, "export_destroy")
        if isinstance(owned, dict):
            return owned
        try:
            stub, _, service_pb2 = self._stub_and_pb2()
            stub.DestroySession(service_pb2.DestroySessionRequest(session_id=session_id), timeout=owned.caps.timeout_s)
            self.owned_sessions.pop(session_id, None)
            return {"status": "destroyed", "tool": "export_destroy", "session_id": session_id}
        except Exception as exc:
            return {"status": "error", "tool": "export_destroy", "session_id": session_id, "error_type": exc.__class__.__name__, "message": str(exc)[:300]}

    def export_cleanup_owned(self, confirmation: str = "", stop_running: bool = True, destroy: bool = True) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "export_cleanup_owned", **gated}
        attempted = stopped = destroyed = skipped = failed = 0
        failures: list[dict[str, str]] = []
        for session_id in list(self.owned_sessions):
            attempted += 1
            try:
                if stop_running:
                    stopped_out = self.export_stop(session_id, confirmation)
                    if stopped_out.get("status") == "stopped":
                        stopped += 1
                    elif stopped_out.get("status") == "refused":
                        skipped += 1
                        continue
                    else:
                        raise RuntimeError(stopped_out.get("message", "stop failed"))
                if destroy:
                    destroyed_out = self.export_destroy(session_id, confirmation)
                    if destroyed_out.get("status") == "destroyed":
                        destroyed += 1
                    elif destroyed_out.get("status") == "refused":
                        skipped += 1
                    else:
                        raise RuntimeError(destroyed_out.get("message", "destroy failed"))
                elif not stop_running:
                    skipped += 1
            except Exception as exc:
                failed += 1
                failures.append({"session_id": session_id, "error_type": exc.__class__.__name__, "message": str(exc)[:160]})
        status = "ok" if failed == 0 else "partial"
        return {
            "status": status,
            "tool": "export_cleanup_owned",
            "attempted": attempted,
            "stopped": stopped,
            "destroyed": destroyed,
            "skipped": skipped,
            "failed": failed,
            "remaining_owned": len(self.owned_sessions),
            "failures": failures[:8],
        }
