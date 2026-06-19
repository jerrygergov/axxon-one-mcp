#!/usr/bin/env python3
"""Reusable Axxon One gRPC and HTTP API client helpers.

This module is intentionally small and dependency-light. It centralizes the
parts that every Axxon One integration needs: proto stub generation/imports,
direct gRPC TLS/auth, HTTP /grpc auth, /v1 request handling, response shaping,
and a few local-lab inventory helpers.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


SENSITIVE_KEYS = {
    "password",
    "token",
    "token_value",
    "auth_token",
    "license_key",
    "serial_number",
    "jwt_token",
    "session_token",
}


@dataclass(slots=True)
class AxxonClientConfig:
    host: str
    grpc_port: int
    http_port: int
    http_url: str
    username: str
    password: str
    tls_cn: str
    ca: Path
    proto_dir: Path
    stubs_dir: Path
    timeout: float = 10.0

    @classmethod
    def from_env(cls, *, repo_root: Path | None = None) -> "AxxonClientConfig":
        root = repo_root or Path(__file__).resolve().parents[1]
        return cls(
            host=os.getenv("AXXON_HOST", "127.0.0.1"),
            grpc_port=int(os.getenv("AXXON_GRPC_PORT", "20109")),
            http_port=int(os.getenv("AXXON_HTTP_PORT", "8000")),
            http_url=os.getenv("AXXON_HTTP_URL", "http://127.0.0.1:8000"),
            username=os.getenv("AXXON_USERNAME", "root"),
            password=os.getenv("AXXON_PASSWORD", ""),
            tls_cn=os.getenv("AXXON_TLS_CN", "F4E66972EC19"),
            ca=Path(os.getenv("AXXON_CA", str(root / "docs/grpc-proto-files/api.ngp.root-ca.crt"))),
            proto_dir=Path(os.getenv("AXXON_PROTO_DIR", str(root / "docs/grpc-proto-files"))),
            stubs_dir=Path(os.getenv("AXXON_GRPC_STUBS", "/tmp/axxon-grpc-py")),
            timeout=float(os.getenv("AXXON_TIMEOUT", "10.0")),
        )


def add_common_args(parser: argparse.ArgumentParser, *, repo_root: Path | None = None) -> None:
    root = repo_root or Path(__file__).resolve().parents[1]
    parser.add_argument("--host", default=os.getenv("AXXON_HOST", "127.0.0.1"))
    parser.add_argument("--grpc-port", type=int, default=int(os.getenv("AXXON_GRPC_PORT", "20109")))
    parser.add_argument("--http-port", type=int, default=int(os.getenv("AXXON_HTTP_PORT", "8000")))
    parser.add_argument("--http-url", default=os.getenv("AXXON_HTTP_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--username", default=os.getenv("AXXON_USERNAME", "root"))
    parser.add_argument("--password", default=os.getenv("AXXON_PASSWORD"))
    parser.add_argument("--tls-cn", default=os.getenv("AXXON_TLS_CN", "F4E66972EC19"))
    parser.add_argument(
        "--ca",
        type=Path,
        default=Path(os.getenv("AXXON_CA", str(root / "docs/grpc-proto-files/api.ngp.root-ca.crt"))),
    )
    parser.add_argument(
        "--proto-dir",
        type=Path,
        default=Path(os.getenv("AXXON_PROTO_DIR", str(root / "docs/grpc-proto-files"))),
    )
    parser.add_argument(
        "--stubs-dir",
        type=Path,
        default=Path(os.getenv("AXXON_GRPC_STUBS", "/tmp/axxon-grpc-py")),
    )
    parser.add_argument("--timeout", type=float, default=float(os.getenv("AXXON_TIMEOUT", "10.0")))


def config_from_args(args: argparse.Namespace) -> AxxonClientConfig:
    if not args.password:
        raise ValueError("password is required via --password or AXXON_PASSWORD")
    return AxxonClientConfig(
        host=args.host,
        grpc_port=args.grpc_port,
        http_port=args.http_port,
        http_url=args.http_url,
        username=args.username,
        password=args.password,
        tls_cn=args.tls_cn,
        ca=args.ca,
        proto_dir=args.proto_dir,
        stubs_dir=args.stubs_dir,
        timeout=args.timeout,
    )


class AxxonApiClient:
    def __init__(self, config: AxxonClientConfig) -> None:
        if not config.password:
            raise ValueError("password is required")
        self.config = config
        self.grpc: Any | None = None
        self.pb: dict[str, Any] = {}
        self.base_creds: Any | None = None
        self.grpc_channel: Any | None = None
        self.grpc_auth_response: Any | None = None
        self.http_token: str = ""
        self.inventory: dict[str, Any] = {}
        self._archive_volume_id: str | None = None
        self._node_name: str | None = None

    @property
    def grpc_target(self) -> str:
        return f"{self.config.host}:{self.config.grpc_port}"

    def socket_check(self, host: str | None = None, port: int | None = None) -> dict[str, Any]:
        target_host = host or self.config.host
        target_port = port or self.config.grpc_port
        with socket.create_connection((target_host, target_port), timeout=self.config.timeout):
            return {"host": target_host, "port": target_port, "connected": True}

    def ensure_stubs(self) -> None:
        required = self.config.stubs_dir / "axxonsoft/bl/auth/Authentication_pb2.py"
        if required.exists():
            if str(self.config.stubs_dir) not in sys.path:
                sys.path.insert(0, str(self.config.stubs_dir))
            return

        try:
            import grpc_tools.protoc  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "grpc_tools is not installed. Install grpcio grpcio-tools "
                "pyOpenSSL googleapis-common-protos in the active venv."
            ) from exc

        proto_files = sorted((self.config.proto_dir / "axxonsoft").rglob("*.proto"))
        if not proto_files:
            raise RuntimeError(f"no proto files found under {self.config.proto_dir / 'axxonsoft'}")

        self.config.stubs_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            "-I",
            str(self.config.proto_dir),
            f"--python_out={self.config.stubs_dir}",
            f"--grpc_python_out={self.config.stubs_dir}",
            *map(str, proto_files),
        ]
        subprocess.run(cmd, check=True)
        if str(self.config.stubs_dir) not in sys.path:
            sys.path.insert(0, str(self.config.stubs_dir))

    def import_module(self, name: str) -> Any:
        if name not in self.pb:
            self.pb[name] = importlib.import_module(name)
        return self.pb[name]

    def import_common_modules(self) -> dict[str, Any]:
        self.grpc = importlib.import_module("grpc")
        names = {
            "json_format": "google.protobuf.json_format",
            "empty": "google.protobuf.empty_pb2",
            "auth_pb2": "axxonsoft.bl.auth.Authentication_pb2",
            "auth_grpc": "axxonsoft.bl.auth.Authentication_pb2_grpc",
            "domain_pb2": "axxonsoft.bl.domain.Domain_pb2",
            "domain_grpc": "axxonsoft.bl.domain.Domain_pb2_grpc",
            "config_pb2": "axxonsoft.bl.config.ConfigurationService_pb2",
            "config_grpc": "axxonsoft.bl.config.ConfigurationService_pb2_grpc",
            "archive_pb2": "axxonsoft.bl.archive.ArchiveSupport_pb2",
            "archive_grpc": "axxonsoft.bl.archive.ArchiveSupport_pb2_grpc",
        }
        for key, module in names.items():
            self.pb[key] = importlib.import_module(module)
        return self.pb

    def prepare_grpc(self) -> None:
        self.ensure_stubs()
        self.import_common_modules()

    def message_to_dict(self, message: Any) -> dict[str, Any]:
        json_format = self.import_module("google.protobuf.json_format")
        return json_format.MessageToDict(message, preserving_proto_field_name=True)

    def sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            out = {}
            for key, val in value.items():
                lower = str(key).lower()
                if any(sensitive in lower for sensitive in SENSITIVE_KEYS):
                    out[key] = "<redacted>" if val else val
                else:
                    out[key] = self.sanitize(val)
            return out
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, bytes):
            return f"<bytes:{len(value)}>"
        return value

    def shape(self, value: Any) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, item in value.items():
                if isinstance(item, list):
                    out[key] = {"type": "list", "count": len(item)}
                elif isinstance(item, dict):
                    out[key] = {"type": "object", "keys": len(item)}
                else:
                    out[key] = {"type": type(item).__name__, "present": item is not None}
            return out
        if isinstance(value, list):
            return {"type": "list", "count": len(value)}
        return {"type": type(value).__name__, "present": value is not None}

    def shape_protobuf(self, message: Any) -> dict[str, Any]:
        try:
            data = self.message_to_dict(message)
        except Exception as exc:
            return {
                "message": message.DESCRIPTOR.full_name,
                "serialized_bytes": message.ByteSize(),
                "fields": self._shape_message_fields(message),
                "json_conversion_error": str(exc)[:500],
            }
        return {
            "message": message.DESCRIPTOR.full_name,
            "serialized_bytes": message.ByteSize(),
            "fields": self.shape(data),
        }

    def _shape_message_fields(self, message: Any) -> dict[str, Any]:
        shape: dict[str, Any] = {}
        for field, value in message.ListFields():
            if field.is_repeated:
                shape[field.name] = {"type": "list", "count": len(value)}
            elif field.message_type:
                shape[field.name] = {"type": "object", "present": True}
            else:
                shape[field.name] = {"type": "scalar", "present": True}
        return shape

    def parse_http_body(self, raw: bytes, content_type: str | None = None, *, max_items: int = 5) -> Any:
        text = raw.decode(errors="replace")
        if not raw:
            return {}
        normalized_content_type = content_type or ""
        if "text/event-stream" in normalized_content_type:
            events = []
            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    events.append({"text": payload[:500]})
                if len(events) >= max_items:
                    break
            return {"event_stream_items": events, "event_stream_count": len(events)}
        if "ngpboundary" in normalized_content_type or "ngpboundary" in text:
            parts = []
            for chunk in text.split("--ngpboundary"):
                if "{" not in chunk:
                    continue
                payload = chunk[chunk.find("{") :].strip()
                try:
                    parts.append(json.loads(payload))
                except json.JSONDecodeError:
                    parts.append({"text": payload[:500]})
                if len(parts) >= max_items:
                    break
            return {"multipart_parts": parts, "multipart_part_count": len(parts)}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text_prefix": text[:1000]}

    def raw_http_body_summary(self, raw: bytes, content_type: str | None = None) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "raw_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        normalized_content_type = content_type or ""
        if (
            normalized_content_type.startswith("text/")
            or "json" in normalized_content_type
            or "xml" in normalized_content_type
            or "mpegurl" in normalized_content_type
        ):
            summary["text_prefix"] = raw.decode(errors="replace")[:1000]
        return summary

    def connect_grpc(self) -> Any:
        if self.grpc is None:
            self.prepare_grpc()
        assert self.grpc is not None
        with self.config.ca.open("rb") as file:
            root_ca = file.read()
        self.base_creds = self.grpc.ssl_channel_credentials(root_certificates=root_ca)
        return self.grpc.secure_channel(
            self.grpc_target,
            self.base_creds,
            options=(("grpc.ssl_target_name_override", self.config.tls_cn),),
        )

    def authenticate_grpc(self) -> Any:
        if self.grpc is None:
            self.prepare_grpc()
        assert self.grpc is not None
        channel = self.connect_grpc()
        stub = self.pb["auth_grpc"].AuthenticationServiceStub(channel)
        request = self.pb["auth_pb2"].AuthenticateRequest(
            user_name=self.config.username,
            password=self.config.password,
        )
        response = stub.AuthenticateEx2(request, timeout=self.config.timeout)
        if response.error_code != 0:
            raise RuntimeError(f"AuthenticateEx2 returned error_code={response.error_code}")
        metadata = ((response.token_name, response.token_value),)
        auth_creds = self.grpc.metadata_call_credentials(lambda _ctx, cb: cb(metadata, None))
        self.grpc_channel = self.grpc.secure_channel(
            self.grpc_target,
            self.grpc.composite_channel_credentials(self.base_creds, auth_creds),
            options=(("grpc.ssl_target_name_override", self.config.tls_cn),),
        )
        self.grpc_auth_response = response
        return response

    def stub_from_proto(self, proto_path: str, service_name: str) -> Any:
        if self.grpc_channel is None:
            self.authenticate_grpc()
        module_base = proto_path.removesuffix(".proto").replace("/", ".")
        grpc_module = self.import_module(f"{module_base}_pb2_grpc")
        stub_class = getattr(grpc_module, f"{service_name}Stub")
        return stub_class(self.grpc_channel)

    def common_stubs(self) -> dict[str, Any]:
        if self.grpc_channel is None:
            self.authenticate_grpc()
        return {
            "auth": self.pb["auth_grpc"].AuthenticationServiceStub(self.grpc_channel),
            "domain": self.pb["domain_grpc"].DomainServiceStub(self.grpc_channel),
            "config": self.pb["config_grpc"].ConfigurationServiceStub(self.grpc_channel),
            "archive": self.pb["archive_grpc"].ArchiveServiceStub(self.grpc_channel),
        }

    def get_archive_history(
        self,
        *,
        access_point: str,
        begin_time: int,
        end_time: int,
        max_count: int = 32,
        min_gap_ms: int = 1000,
    ) -> dict[str, Any]:
        if self.grpc_channel is None:
            self.authenticate_grpc()
        archive_pb2 = self.import_module("axxonsoft.bl.archive.ArchiveSupport_pb2")
        archive = self.common_stubs()["archive"]
        response = archive.GetHistory2(
            archive_pb2.GetHistory2Request(
                access_point=access_point,
                begin_time=begin_time,
                end_time=end_time,
                max_count=max_count,
                min_gap_ms=min_gap_ms,
                scan_mode=archive_pb2.GetHistory2Request.SM_APPROXIMATE,
            ),
            timeout=self.config.timeout,
        )
        return self.message_to_dict(response)

    def archive_calendar(self, source_access_point: str, archive_access_point: str) -> dict[str, Any]:
        """Return ArchiveService.GetCalendar response over HTTP /grpc for a source/archive pair."""
        response = self.http_grpc(
            "axxonsoft.bl.archive.ArchiveService.GetCalendar",
            {"access_point": source_access_point, "archive_access_point": archive_access_point},
        )
        return response.get("body", {}) if isinstance(response, dict) else {}

    def archive_intervals(
        self,
        camera_legacy_access_point: str,
        begin: str,
        end: str,
        archive_ap: str | None = None,
        max_count: int = 32,
        min_gap_ms: int = 1000,
    ) -> list[dict[str, str]]:
        """Return bounded archive intervals via legacy /archive/contents/intervals."""
        path = f"/archive/contents/intervals/{camera_legacy_access_point}/{begin}/{end}"
        if archive_ap:
            path += "?archive=" + archive_ap
        response = self.http_request("GET", path, bearer=True, max_items=max_count)
        body = response.get("body") if isinstance(response, dict) else None
        if isinstance(body, list):
            return body[:max_count]
        if isinstance(body, dict):
            return body.get("intervals", [])[:max_count]
        return []

    def batch_get_factories(self, factory_ids: list[dict[str, Any]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.config.ConfigurationService.BatchGetFactories",
            {"factories": [dict(factory) for factory in factory_ids]},
        )

    def list_similar_units(self, unit_uid: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.config.ConfigurationService.ListSimilarUnits",
            {
                "uid": unit_uid,
                "node_name": self.node_name(),
                "page_size": 1000,
                "search_mode": "BY_UNIT_TYPE",
            },
        )

    def acquire_dynamic_parameters(self, unit_uid: str, property_path: str | None = None) -> dict[str, Any]:
        if property_path is not None:
            raise ValueError("property_path is not supported by DynamicParametersService.AcquireDynamicParameters")
        return self.http_grpc(
            "axxonsoft.bl.config.DynamicParametersService.AcquireDynamicParameters",
            {"uid": unit_uid},
        )

    def acquire_device_additional_data(self, unit_uid: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.config.DynamicParametersService.AcquireDeviceAdditionalData",
            {"uid": unit_uid},
        )

    def archive_format_volumes(self, access_point: str, volume_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.archive.ArchiveService.FormatVolumes",
            {"access_point": access_point, "volumes": [{"id": volume_id} for volume_id in volume_ids]},
        )

    def archive_reindex(self, access_point: str, volume_ids: list[str], full: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {"access_point": access_point, "volume_ids": list(volume_ids)}
        if full:
            data["full_reindex"] = {}
        return self.http_grpc(
            "axxonsoft.bl.archive.ArchiveService.Reindex",
            data,
        )

    def archive_cancel_reindex(self, access_point: str, volume_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.archive.ArchiveService.CancelReindex",
            {"access_point": access_point, "volume_ids": list(volume_ids)},
        )

    def archive_probe_volume(self, path_or_volume_hint: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.archive.ArchiveVolumeService.ProbeVolume",
            {"volume_type": "local", "connection_params": {"path": path_or_volume_hint}},
        )

    def security_list_roles(self, *, page_size: int = 100, page_token: str = "") -> dict[str, Any]:
        data: dict[str, Any] = {"page_size": page_size}
        if page_token:
            data["page_token"] = page_token
        return self.http_grpc("axxonsoft.bl.security.SecurityService.ListRoles", data)

    def security_list_users(
        self,
        *,
        page_size: int = 100,
        page_token: str = "",
        role_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"page_size": page_size}
        if page_token:
            data["page_token"] = page_token
        if role_ids:
            data["role_ids"] = list(role_ids)
        return self.http_grpc("axxonsoft.bl.security.SecurityService.ListUsers", data)

    def security_list_ldap_servers(self, *, page_size: int = 100, page_token: str = "") -> dict[str, Any]:
        data: dict[str, Any] = {"page_size": page_size}
        if page_token:
            data["page_token"] = page_token
        return self.http_grpc("axxonsoft.bl.security.SecurityService.ListLDAPServers", data)

    def security_get_policies(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.security.SecurityService.GetPolicies", {})

    def security_get_restricted_config(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.security.SecurityService.GetRestrictedConfig", {})

    def security_list_global_permissions(self, role_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.security.SecurityService.ListGlobalPermissions",
            {"role_ids": list(role_ids)},
        )

    def security_list_object_permissions_info(
        self,
        *,
        role_id: str,
        node_name: str,
        page_size: int = 50,
        page_token: str = "",
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"role_id": role_id, "node_name": node_name, "page_size": page_size}
        if page_token:
            data["page_token"] = page_token
        return self.http_grpc("axxonsoft.bl.security.SecurityService.ListObjectsPermissionsInfo", data)

    def security_change_config(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.security.SecurityService.ChangeConfig", dict(data))

    def security_set_global_permissions(self, role_id: str, permissions: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.security.SecurityService.SetGlobalPermissions",
            {"permissions": {role_id: dict(permissions)}},
        )

    def security_set_object_permissions(self, role_id: str, permissions: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.security.SecurityService.SetObjectPermissions",
            {"role_to_permissions": {role_id: dict(permissions)}},
        )

    def security_set_groups_permissions(self, permissions: list[dict[str, Any]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.security.SecurityService.SetGroupsPermissions",
            {"permissions": [dict(item) for item in permissions]},
        )

    def security_set_macros_permissions(self, role_id: str, macros_access: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.security.SecurityService.SetMacrosPermissions",
            {"role_id": role_id, "macros_access": dict(macros_access)},
        )

    def security_list_groups_permissions_info(
        self,
        *,
        role_id: str,
        page_size: int = 50,
        page_token: str = "",
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"role_id": role_id, "page_size": page_size}
        if page_token:
            data["page_token"] = page_token
        return self.http_grpc("axxonsoft.bl.security.SecurityService.ListGroupsPermissionsInfo", data)

    def security_list_macros_permissions_paged(
        self,
        *,
        role_id: str,
        page_size: int = 50,
        page_token: str = "",
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"role_id": role_id, "page_size": page_size}
        if page_token:
            data["page_token"] = page_token
        return self.http_grpc("axxonsoft.bl.security.SecurityService.ListMacrosPermissionsPaged", data)

    def security_get_ldap_synchronization(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.security.SecurityService.GetLDAPSynchronization", {})

    def security_get_ldap_synchronization_state(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.security.SecurityService.GetLDAPSynchronizationState", {})

    def security_gen_google_auth_secret(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.security.SecurityService.GenGoogleAuthSecret", {})

    def security_enable_google_auth(self, user_index: str, secret_key: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.security.SecurityService.EnableGoogleAuth",
            {"assignments": [{"user_index": user_index, "secret_key": secret_key}]},
        )

    def security_disable_google_auth(self, user_index: str, verification_code: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.security.SecurityService.DisableGoogleAuth",
            {"assignments": [{"user_index": user_index, "verification_code": verification_code}]},
        )

    def bookmark_list(
        self, time_range: dict[str, Any], *, page_size: int = 100, page_token: str = ""
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"range": time_range, "page_size": page_size}
        if page_token:
            data["page_token"] = page_token
        return self.http_grpc("axxonsoft.bl.bookmarks.BookmarkService.ListBookmarks", data)

    def bookmark_get(self, bookmark_id: str) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.bookmarks.BookmarkService.GetBookmark", {"id": bookmark_id})

    def bookmark_create(self, bookmark: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.bookmarks.BookmarkService.CreateBookmark", {"bookmark": bookmark})

    def bookmark_update(self, bookmark: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.bookmarks.BookmarkService.UpdateBookmark", {"bookmark": bookmark})

    def bookmark_delete(self, bookmark_id: str) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.bookmarks.BookmarkService.DeleteBookmark", {"id": bookmark_id})

    def bookmark_set_exported_time(self, bookmark_id: str, exported_time: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.bookmarks.BookmarkService.SetExportedTime",
            {"id": bookmark_id, "exported_time": exported_time},
        )

    def license_get_global_restrictions(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.license.LicenseService.GetGlobalRestrictions", {})

    def license_get_domain_key_info(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.license.LicenseService.GetDomainLicenseKeyInfo", {})

    def license_get_host_info(self) -> dict[str, Any]:
        # HTTP /grpc closes the connection for GetHostInfo (RemoteDisconnected),
        # so this read uses the direct gRPC transport.
        stub = self.stub_from_proto("axxonsoft/bl/license/LicenseService.proto", "LicenseService")
        pb2 = self.import_module("axxonsoft.bl.license.LicenseService_pb2")
        response = stub.GetHostInfo(pb2.GetHostInfoRequest(), timeout=self.config.timeout)
        return {"status": 200, "body": self.message_to_dict(response)}

    def license_key_info(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.license.LicenseService.LicenseKeyInfo", {})

    def license_get_node_restrictions(self, node_names: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.license.LicenseService.GetNodeRestrictions",
            {"nodes": [{"name": name} for name in node_names]},
        )

    def license_is_possible_to_launch(self, service_name: str, quantity: int = 1) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.license.LicenseService.IsPossibleToLaunch",
            {"service_name": service_name, "quantity": quantity},
        )

    def time_get_time_zone(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.tz.TimeZoneManager.GetTimeZone", {})

    def time_get_ntp(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.tz.TimeZoneManager.GetNTP", {})

    def time_list_time_zones(self) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.tz.TimeZoneManager.ListTimeZones", {})

    def time_batch_get_zones(self, zone_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc("axxonsoft.bl.tz.TimeZoneManager.BatchGetZones", {"ids": list(zone_ids)})

    def http_get_json(self, path: str, max_items: int = 32) -> dict[str, Any]:
        """GET a legacy HTTP JSON endpoint with Bearer auth and return the parsed body."""
        response = self.http_request("GET", path, bearer=True, max_items=max_items)
        body = response.get("body") if isinstance(response, dict) else None
        if isinstance(body, dict):
            return body
        return {"body": body}

    def pull_events_bounded(
        self,
        *,
        subjects: list[str],
        event_types: list[str],
        timeout: float,
        max_events: int,
    ) -> list[dict[str, Any]]:
        import uuid as _uuid
        from axxon_subscription_smoke import build_pull_event_filters

        if self.grpc_channel is None:
            self.authenticate_grpc()
        notify_pb2 = self.import_module("axxonsoft.bl.events.Notification_pb2")
        events_pb2 = self.import_module("axxonsoft.bl.events.Events_pb2")
        notify = self.stub_from_proto("axxonsoft/bl/events/Notification.proto", "DomainNotifier")

        filters = build_pull_event_filters(
            notify_pb2,
            events_pb2,
            subjects=subjects,
            event_types=event_types,
        )
        subscription_id = f"codex-{_uuid.uuid4()}"
        request = notify_pb2.PullEventsRequest(subscription_id=subscription_id, filters=filters)
        collected: list[dict[str, Any]] = []
        try:
            for page in notify.PullEvents(request, timeout=timeout):
                data = self.message_to_dict(page)
                for item in data.get("items", []):
                    collected.append(item)
                    if len(collected) >= max_events:
                        break
                if len(collected) >= max_events:
                    break
        except Exception:
            pass
        finally:
            try:
                notify.DisconnectEventChannel(
                    notify_pb2.DisconnectEventChannelRequest(subscription_id=subscription_id),
                    timeout=2,
                )
            except Exception:
                pass
        return collected[:max_events]

    def pull_notifier_events_bounded(
        self,
        *,
        notifier: str,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict[str, Any]:
        import uuid as _uuid
        from axxon_subscription_smoke import build_pull_event_filters

        service_by_notifier = {"domain": "DomainNotifier", "node": "NodeNotifier"}
        if notifier not in service_by_notifier:
            raise ValueError("notifier must be 'domain' or 'node'")
        timeout = max(0.1, min(float(timeout_s), 30.0))
        max_events = max(1, min(int(limit), 500))
        if self.grpc_channel is None:
            self.authenticate_grpc()
        notify_pb2 = self.import_module("axxonsoft.bl.events.Notification_pb2")
        events_pb2 = self.import_module("axxonsoft.bl.events.Events_pb2")
        service_name = service_by_notifier[notifier]
        notify = self.stub_from_proto("axxonsoft/bl/events/Notification.proto", service_name)
        filters = build_pull_event_filters(
            notify_pb2,
            events_pb2,
            subjects=list(subjects or []),
            event_types=list(event_types or []),
        )
        subscription_id = f"codex-{_uuid.uuid4()}"
        request = notify_pb2.PullEventsRequest(subscription_id=subscription_id, filters=filters)
        collected: list[dict[str, Any]] = []
        status = "ok"
        stream_error = ""
        deadline_reached = False
        try:
            pull = notify.PullDetailedEvents if detailed else notify.PullEvents
            for page in pull(request, timeout=timeout):
                data = self.message_to_dict(page)
                for item in data.get("items", []):
                    collected.append(item)
                    if len(collected) >= max_events:
                        break
                if len(collected) >= max_events:
                    break
        except Exception as exc:
            # A bounded long-poll that stays open until the deadline raises
            # DEADLINE_EXCEEDED with no events: the stream was established and
            # simply idle, which is healthy, not a transport failure.
            code = getattr(exc, "code", None)
            deadline_reached = bool(callable(code) and getattr(code(), "name", "") == "DEADLINE_EXCEEDED")
            status = "idle" if (deadline_reached and not collected) else "warn"
            stream_error = str(exc)[:300]
        finally:
            disconnect_clean = True
            try:
                notify.DisconnectEventChannel(
                    notify_pb2.DisconnectEventChannelRequest(subscription_id=subscription_id),
                    timeout=min(timeout, 2.0),
                )
            except Exception:
                disconnect_clean = False
        result: dict[str, Any] = {
            "status": status,
            "notifier": notifier,
            "service": service_name,
            "detailed": detailed,
            "count": len(collected),
            "events": collected[:max_events],
            "caps": {"timeout_s": timeout, "limit": max_events},
            "stream_idle": deadline_reached and not collected,
            "disconnect_clean": disconnect_clean,
        }
        if stream_error:
            result["stream_error"] = stream_error
        return result

    def update_subscription_bounded(
        self,
        *,
        notifier: str,
        event_types: list[str] | None = None,
        new_event_types: list[str] | None = None,
        subjects: list[str] | None = None,
        new_subjects: list[str] | None = None,
        timeout_s: float = 5.0,
    ) -> dict[str, Any]:
        """Update a live event subscription's filters, self-contained.

        UpdateSubscription only targets a subscription that has an open PullEvents
        stream, so this opens a short-lived subscription on a background daemon
        thread, applies UpdateSubscription with the new filters on the main thread,
        then disconnects. The subscription is fully torn down; nothing persists.

        Args:
            notifier (str): "domain" (DomainNotifier) or "node" (NodeNotifier).
            event_types (list, optional): Initial subscription event types.
            new_event_types (list, optional): Updated event types to apply.
            subjects (list, optional): Initial subjects.
            new_subjects (list, optional): Updated subjects.
            timeout_s (float, optional): Per-call timeout bound.

        Returns:
            (dict): status, notifier, service, subscription_applied, before/after
            event types, disconnect_clean, and update_error when the update failed.
        """
        import threading
        import time as _time
        import uuid as _uuid
        from axxon_subscription_smoke import build_pull_event_filters

        service_by_notifier = {"domain": "DomainNotifier", "node": "NodeNotifier"}
        if notifier not in service_by_notifier:
            raise ValueError("notifier must be 'domain' or 'node'")
        timeout = max(0.1, min(float(timeout_s), 30.0))
        if self.grpc_channel is None:
            self.authenticate_grpc()
        notify_pb2 = self.import_module("axxonsoft.bl.events.Notification_pb2")
        events_pb2 = self.import_module("axxonsoft.bl.events.Events_pb2")
        service_name = service_by_notifier[notifier]
        notify = self.stub_from_proto("axxonsoft/bl/events/Notification.proto", service_name)

        before = list(event_types or [])
        after = list(new_event_types or [])
        filters_before = build_pull_event_filters(notify_pb2, events_pb2, subjects=list(subjects or []), event_types=before)
        filters_after = build_pull_event_filters(notify_pb2, events_pb2, subjects=list(new_subjects or subjects or []), event_types=after)
        subscription_id = f"codex-{_uuid.uuid4()}"

        def _hold() -> None:
            try:
                request = notify_pb2.PullEventsRequest(subscription_id=subscription_id, filters=filters_before)
                for _ in notify.PullEvents(request, timeout=timeout):
                    break
            except Exception:
                pass

        holder = threading.Thread(target=_hold, daemon=True)
        holder.start()
        _time.sleep(min(timeout / 2.0, 2.0))

        applied = True
        update_error = ""
        try:
            notify.UpdateSubscription(
                notify_pb2.UpdateSubscriptionRequest(subscription_id=subscription_id, filters=filters_after),
                timeout=timeout,
            )
        except Exception as exc:
            applied = False
            update_error = str(exc)[:300]
        disconnect_clean = True
        try:
            notify.DisconnectEventChannel(
                notify_pb2.DisconnectEventChannelRequest(subscription_id=subscription_id),
                timeout=min(timeout, 2.0),
            )
        except Exception:
            disconnect_clean = False
        holder.join(timeout=2.0)

        result: dict[str, Any] = {
            "status": "ok" if applied else "warn",
            "notifier": notifier,
            "service": service_name,
            "subscription_applied": applied,
            "before_event_types": before,
            "after_event_types": after,
            "disconnect_clean": disconnect_clean,
        }
        if update_error:
            result["update_error"] = update_error
        return result

    def get_active_alerts(self, camera_ap: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.GetActiveAlerts",
            {"camera_ap": camera_ap},
        )

    def batch_get_active_alerts(self, nodes: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.BatchGetActiveAlerts",
            {"nodes": list(nodes)},
        )

    def batch_filter_active_alerts(self, nodes: list[str], filter: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.BatchFilterActiveAlerts",
            {"nodes": list(nodes), "filter": dict(filter or {})},
        )

    def raise_alert(self, camera_ap: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.RaiseAlert",
            {"camera_ap": camera_ap},
        )

    def begin_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.BeginAlertReview",
            {"camera_ap": camera_ap, "alert_id": alert_id},
        )

    def continue_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.ContinueAlertReview",
            {"camera_ap": camera_ap, "alert_id": alert_id},
        )

    def cancel_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.CancelAlertReview",
            {"camera_ap": camera_ap, "alert_id": alert_id},
        )

    def complete_alert_review(
        self, camera_ap: str, alert_id: str, *, severity: str, bookmark_message: str
    ) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.CompleteAlertReview",
            {
                "camera_ap": camera_ap,
                "alert_id": alert_id,
                "severity": severity,
                "bookmark": {"message": bookmark_message},
            },
        )

    def escalate_alert(
        self,
        camera_ap: str,
        alert_id: str,
        *,
        priority: str,
        user_roles: list[str],
        comment: str,
    ) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.EscalateAlert",
            {
                "camera_ap": camera_ap,
                "alert_id": alert_id,
                "priority": priority,
                "user_roles": list(user_roles),
                "comment": comment,
            },
        )

    def list_layouts(self, view: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.ListLayouts",
            {"view": view},
        )

    def batch_get_layouts(self, items: list[dict[str, str]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.BatchGetLayouts",
            {"items": [dict(it) for it in items]},
        )

    def layouts_on_view(self, layouts: list[dict[str, str]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.LayoutsOnView",
            {"layouts": [dict(layout) for layout in layouts]},
        )

    def list_layout_images(self, layout_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages",
            {"layout_id": layout_id},
        )

    def list_layout_images_grpc(self, layout_id: str) -> dict[str, Any]:
        """Return LayoutImagesManager.ListLayoutImages over direct gRPC.

        The HTTP /grpc bridge returns HTTP 500 for LayoutImagesManager, so layout
        image enumeration must use the direct gRPC transport.

        Args:
            layout_id (str): Layout UID whose image metadata to list.

        Returns:
            (dict): MessageToDict of ListLayoutImagesResponse with an images list.
        """
        stub = self.stub_from_proto(
            "axxonsoft/bl/layout/LayoutImagesManager.proto", "LayoutImagesManager"
        )
        pb2 = self.import_module("axxonsoft.bl.layout.LayoutImagesManager_pb2")
        response = stub.ListLayoutImages(
            pb2.ListLayoutImagesRequest(layout_id=layout_id), timeout=self.config.timeout
        )
        return self.message_to_dict(response)

    def remove_layout_images(self, layout_id: str, images_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutImagesManager.RemoveLayoutImages",
            {"layout_id": layout_id, "images_ids": list(images_ids)},
        )

    def upload_layout_image_grpc(
        self, layout_id: str, image_id: str, chunk_data: bytes, etag: str = ""
    ) -> dict[str, Any]:
        """Upload a single-chunk layout image over direct gRPC.

        Args:
            layout_id (str): Target layout UID.
            image_id (str): Client-generated image UID.
            chunk_data (bytes): Full image payload (single chunk).
            etag (str, optional): Last-seen revision, empty for a first upload.

        Returns:
            (dict): MessageToDict of UploadLayoutImageResponse (status, message, etag).
        """
        stub = self.stub_from_proto(
            "axxonsoft/bl/layout/LayoutImagesManager.proto", "LayoutImagesManager"
        )
        pb2 = self.import_module("axxonsoft.bl.layout.LayoutImagesManager_pb2")
        request = pb2.UploadLayoutImageRequest(
            layout_id=layout_id,
            image_id=image_id,
            etag=etag,
            total_size_bytes=len(chunk_data),
            chunk_data=chunk_data,
        )
        response = stub.UploadLayoutImage(iter((request,)), timeout=self.config.timeout)
        return self.message_to_dict(response)

    def remove_layout_images_grpc(self, layout_id: str, images_ids: list[str]) -> dict[str, Any]:
        """Remove layout images over direct gRPC.

        Args:
            layout_id (str): Target layout UID.
            images_ids (list): Image UIDs to remove.

        Returns:
            (dict): MessageToDict of RemoveLayoutImagesResponse.
        """
        stub = self.stub_from_proto(
            "axxonsoft/bl/layout/LayoutImagesManager.proto", "LayoutImagesManager"
        )
        pb2 = self.import_module("axxonsoft.bl.layout.LayoutImagesManager_pb2")
        response = stub.RemoveLayoutImages(
            pb2.RemoveLayoutImagesRequest(layout_id=layout_id, images_ids=list(images_ids)),
            timeout=self.config.timeout,
        )
        return self.message_to_dict(response)

    def download_layout_image_grpc(self, layout_id: str, image_id: str, chunk_size_kb: int = 32) -> dict[str, Any]:
        """Download a layout image over the direct-gRPC server stream.

        The HTTP /grpc bridge 500s for LayoutImagesManager, so this assembles the
        DownloadLayoutImage chunk stream. etag and total_size_bytes are only
        guaranteed on the first response.

        Args:
            layout_id (str): Target layout UID.
            image_id (str): Image UID to download.
            chunk_size_kb (int, optional): Requested chunk size in KiB.

        Returns:
            (dict): etag, total_size_bytes, chunk_count, and the assembled data bytes.
        """
        stub = self.stub_from_proto(
            "axxonsoft/bl/layout/LayoutImagesManager.proto", "LayoutImagesManager"
        )
        pb2 = self.import_module("axxonsoft.bl.layout.LayoutImagesManager_pb2")
        request = pb2.DownloadLayoutImageRequest(layout_id=layout_id, image_id=image_id, chunk_size_kb=chunk_size_kb)
        data = bytearray()
        etag = ""
        total_size_bytes = 0
        chunk_count = 0
        for response in stub.DownloadLayoutImage(request, timeout=self.config.timeout):
            if chunk_count == 0:
                etag = response.etag
                total_size_bytes = response.total_size_bytes
            data += response.chunk_data
            chunk_count += 1
        return {"etag": etag, "total_size_bytes": total_size_bytes, "chunk_count": chunk_count, "data": bytes(data)}

    def collect_backup_grpc(self, node: str, backup_types: list[str] | None = None, chunk_size_kb: int = 64) -> dict[str, Any]:
        """Drain the ConfigurationManager.CollectBackup config-export stream.

        Read-only export: this assembles the backup chunk stream that the server
        produces from the current configuration. It is the inverse of RestoreBackup
        and changes nothing on the node. total_size_bytes is taken from the first
        response.

        Args:
            node (str): Target node name, for instance "Server".
            backup_types (list, optional): Human backup-type names to collect
                (LOCAL, SHARED, LICENSE, TICKETS). Defaults to ["LOCAL"].
            chunk_size_kb (int, optional): Requested chunk size in KiB.

        Returns:
            (dict): node, backup_types, total_size_bytes, chunk_count, byte_count,
                and the assembled data bytes.
        """
        stub = self.stub_from_proto("axxonsoft/bl/maintenance/ConfigurationManager.proto", "ConfigurationManager")
        pb2 = self.import_module("axxonsoft.bl.maintenance.ConfigurationManager_pb2")
        names = list(backup_types or ["LOCAL"])
        enum_values = [pb2.CollectBackupRequest.EBackupType.Value(name) for name in names]
        request = pb2.CollectBackupRequest(type=enum_values, node=node, chunk_size_kb=chunk_size_kb)
        data = bytearray()
        total_size_bytes = 0
        chunk_count = 0
        for response in stub.CollectBackup(request, timeout=self.config.timeout):
            if chunk_count == 0:
                total_size_bytes = response.total_size_bytes
            data += response.chunk_data
            chunk_count += 1
        return {
            "node": node,
            "backup_types": names,
            "total_size_bytes": total_size_bytes,
            "chunk_count": chunk_count,
            "byte_count": len(data),
            "data": bytes(data),
        }

    def list_maps(self) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.ListMaps",
            {},
        )

    def batch_get_maps(self, map_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.BatchGetMaps",
            {"map_ids": list(map_ids)},
        )

    def get_map_image(self, map_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.GetMapImage",
            {"map_id": map_id},
        )

    def get_markers(self, map_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.GetMarkers",
            {"map_id": map_id},
        )

    def list_map_providers(self) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.ListMapProviders",
            {},
        )

    def update_markers(self, map_id: str, markers: list[dict[str, Any]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.UpdateMarkers",
            {"changed": [{"map_id": map_id, "updated": list(markers)}]},
        )

    def change_maps(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.ChangeMaps",
            dict(payload),
        )

    def list_walls(self) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.ListWalls",
            {},
        )

    def register_wall(
        self,
        *,
        host_name: str,
        pid: int,
        ppid: int,
        name: str,
        display_name: str,
        data_bytes: bytes,
    ) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.RegisterWall",
            {
                "host_name": host_name,
                "pid": pid,
                "ppid": ppid,
                "name": name,
                "display_name": display_name,
                "data": {"data": base64.b64encode(data_bytes).decode("ascii")},
            },
        )

    def change_wall(self, *, cookie: str, data_bytes: bytes, seq_number: int) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.ChangeWall",
            {
                "cookie": cookie,
                "data": {"data": base64.b64encode(data_bytes).decode("ascii")},
                "seq_number": seq_number,
            },
        )

    def set_control_data(self, *, wall_id: str, seq_number: int, data_bytes: bytes) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.SetControlData",
            {
                "wall_id": wall_id,
                "seq_number": seq_number,
                "data": {"data": base64.b64encode(data_bytes).decode("ascii")},
            },
        )

    def unregister_wall(self, cookie: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.UnregisterWall",
            {"cookie": cookie},
        )

    def get_my_control_data(self, cookie: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.GetMyControlData",
            {"cookie": cookie},
        )

    def http_request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        basic: bool = False,
        bearer: bool | str = False,
        query: str = "",
        headers: dict[str, str] | None = None,
        max_items: int = 5,
        raw_body: bool = False,
        max_bytes: int | None = None,
    ) -> dict[str, Any]:
        url = self.config.http_url.rstrip("/") + path
        if query:
            url += ("&" if "?" in url else "?") + query
        data = None
        req_headers = dict(headers or {})
        if isinstance(body, bytes):
            data = body
        elif body is not None:
            data = json.dumps(body).encode()
            req_headers["Content-Type"] = "application/json"
        if basic:
            raw = f"{self.config.username}:{self.config.password}".encode()
            req_headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
        if bearer:
            token = self.http_token if bearer is True else str(bearer)
            req_headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(url, data=data, method=method, headers=req_headers)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                raw = response.read(max_bytes) if max_bytes is not None else response.read()
                content_type = response.headers.get("Content-Type", "")
                return {
                    "status": response.status,
                    "content_type": content_type,
                    "size": len(raw),
                    "headers": dict(response.headers.items()),
                    "body": self.raw_http_body_summary(raw, content_type)
                    if raw_body
                    else self.parse_http_body(raw, content_type, max_items=max_items),
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read(max_bytes) if max_bytes is not None else exc.read()
            content_type = exc.headers.get("Content-Type", "")
            return {
                "status": exc.code,
                "content_type": content_type,
                "size": len(raw),
                "headers": dict(exc.headers.items()),
                "body": self.raw_http_body_summary(raw, content_type)
                if raw_body
                else self.parse_http_body(raw, content_type, max_items=max_items),
            }

    def authenticate_http_grpc(self) -> str:
        response = self.http_request(
            "POST",
            "/grpc",
            {
                "method": "axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2",
                "data": {"user_name": self.config.username, "password": self.config.password},
            },
            basic=True,
        )
        if response["status"] != 200:
            raise RuntimeError(f"HTTP /grpc auth failed: {self.sanitize(response)}")
        body = response.get("body", {})
        if body.get("error_code") not in (0, "AUTHENTICATE_CODE_OK"):
            raise RuntimeError(f"HTTP /grpc auth returned error: {self.sanitize(body)}")
        self.http_token = body.get("token_value", "")
        if not self.http_token:
            raise RuntimeError("HTTP /grpc auth returned no token")
        return self.http_token

    def http_grpc(self, fqmn: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.http_token:
            self.authenticate_http_grpc()
        return self.http_request(
            "POST",
            "/grpc",
            {"method": fqmn, "data": data or {}},
            bearer=True,
        )

    def to_json_data(self, message: Any) -> dict[str, Any]:
        return self.message_to_dict(message)

    def query_string(self, data: dict[str, Any]) -> str:
        params: list[tuple[str, str]] = []
        for key, value in data.items():
            if value in (None, "", [], {}):
                continue
            if isinstance(value, list):
                for item in value:
                    params.append((key, self.query_value(item)))
            else:
                params.append((key, self.query_value(value)))
        return urllib.parse.urlencode(params, doseq=True)

    def query_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value, separators=(",", ":"))
        return str(value)

    def load_inventory(self) -> dict[str, Any]:
        try:
            stubs = self.common_stubs()
        except (FileNotFoundError, OSError):
            return self.load_inventory_http()
        domain = stubs["domain"]
        config = stubs["config"]
        domain_pb2 = self.pb["domain_pb2"]
        config_pb2 = self.pb["config_pb2"]

        version = self.message_to_dict(domain.GetVersion(domain_pb2.GetVersionRequest(), timeout=self.config.timeout))
        platform = self.message_to_dict(
            domain.GetHostPlatformInfo(domain_pb2.GetHostPlatformInfoRequest(), timeout=self.config.timeout)
        )
        nodes = self.message_to_dict(
            domain.ListNodes(domain_pb2.ListNodesRequest(), timeout=self.config.timeout)
        ).get("nodes", [])

        cameras = []
        for page in domain.ListCameras(domain_pb2.ListCamerasRequest(page_size=100), timeout=self.config.timeout):
            cameras.extend(self.message_to_dict(page).get("items", []))

        archives = []
        for page in domain.ListArchives(domain_pb2.ListArchivesRequest(page_size=100), timeout=self.config.timeout):
            archives.extend(self.message_to_dict(page).get("items", []))

        components = []
        for page in domain.ListComponents(domain_pb2.ListComponentsRequest(page_size=200), timeout=self.config.timeout):
            components.extend(self.message_to_dict(page).get("items", []))

        host_uid = f"hosts/{self.config.tls_cn}"
        host_unit = self.message_to_dict(
            config.ListUnits(config_pb2.ListUnitsRequest(unit_uids=[host_uid]), timeout=self.config.timeout)
        )
        self.inventory = {
            "version": version,
            "platform": platform,
            "nodes": nodes,
            "cameras": cameras,
            "archives": archives,
            "components": components,
            "host_unit": host_unit,
        }
        return self.inventory

    def _domain_batch_read(self, request_name: str, method_name: str, access_points: list[str], items_key: str) -> dict[str, Any]:
        """Run a DomainService batch-read RPC over a list of ResourceLocator access points.

        Drains the server stream into items/maps plus not_found/unreachable lists.

        Args:
            request_name (str): Domain_pb2 request message name.
            method_name (str): DomainService stub method name.
            access_points (list): Resource access points to look up.
            items_key (str): Response field holding the entities ("items" or "maps").

        Returns:
            (dict): items_key list plus not_found_objects and unreachable_objects.
        """
        domain = self.common_stubs()["domain"]
        domain_pb2 = self.pb["domain_pb2"]
        locators = [domain_pb2.ResourceLocator(access_point=ap) for ap in access_points]
        request = getattr(domain_pb2, request_name)(items=locators)
        entities: list[dict[str, Any]] = []
        not_found: list[str] = []
        unreachable: list[str] = []
        for page in getattr(domain, method_name)(request, timeout=self.config.timeout):
            data = self.message_to_dict(page)
            entities.extend(data.get(items_key, []))
            not_found.extend(data.get("not_found_objects", []))
            unreachable.extend(data.get("unreachable_objects", []))
        return {items_key: entities, "not_found_objects": not_found, "unreachable_objects": unreachable}

    def get_cameras_by_components(self, access_points: list[str]) -> dict[str, Any]:
        return self._domain_batch_read("GetCamerasByComponentsRequest", "GetCamerasByComponents", list(access_points), "items")

    def batch_get_archives_domain(self, access_points: list[str]) -> dict[str, Any]:
        return self._domain_batch_read("BatchGetArchivesRequest", "BatchGetArchives", list(access_points), "items")

    def search_maps(self, access_points: list[str]) -> dict[str, Any]:
        return self._domain_batch_read("SearchMapsRequest", "SearchMaps", list(access_points), "maps")

    def _http_grpc_body(self, fqmn: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.http_grpc(fqmn, data or {})
        body = response.get("body") if isinstance(response, dict) else None
        return body if isinstance(body, dict) else {}

    def _http_grpc_stream_items(self, fqmn: str, page_size: int) -> list[dict[str, Any]]:
        """Drain a server-streaming DomainService listing over HTTP /grpc into a flat items list."""
        items: list[dict[str, Any]] = []
        token = ""
        while True:
            body = self._http_grpc_body(fqmn, {"page_size": page_size, "page_token": token})
            events = body.get("event_stream_items", []) if body.get("event_stream_items") is not None else [body]
            next_token = ""
            page_total = 0
            for event in events:
                page_items = event.get("items", []) if isinstance(event, dict) else []
                items.extend(page_items)
                page_total += len(page_items)
                if isinstance(event, dict) and event.get("next_page_token"):
                    next_token = event["next_page_token"]
            if not next_token or page_total == 0:
                break
            token = next_token
        return items

    def load_inventory_http(self) -> dict[str, Any]:
        """Build the inventory dict over HTTP /grpc only (no gRPC stubs, no CA)."""
        domain = "axxonsoft.bl.domain.DomainService"
        nodes = self._http_grpc_body(f"{domain}.ListNodes").get("nodes", [])
        host_name = nodes[0].get("node_name") if nodes else self.config.tls_cn
        host_unit = self._http_grpc_body(
            "axxonsoft.bl.config.ConfigurationService.ListUnits",
            {"unit_uids": [f"hosts/{host_name}"]},
        )
        self.inventory = {
            "version": self._http_grpc_body(f"{domain}.GetVersion"),
            "platform": self._http_grpc_body(f"{domain}.GetHostPlatformInfo"),
            "nodes": nodes,
            "cameras": self._http_grpc_stream_items(f"{domain}.ListCameras", 100),
            "archives": self._http_grpc_stream_items(f"{domain}.ListArchives", 100),
            "components": self._http_grpc_stream_items(f"{domain}.ListComponents", 200),
            "host_unit": host_unit,
        }
        return self.inventory

    def node_name(self) -> str:
        if self._node_name is not None:
            return self._node_name
        nodes = self.inventory.get("nodes") if self.inventory else None
        if not nodes:
            nodes = self._http_grpc_body("axxonsoft.bl.domain.DomainService.ListNodes").get("nodes", [])
        self._node_name = nodes[0].get("node_name", self.config.tls_cn) if nodes else self.config.tls_cn
        return self._node_name

    def archive_access_point(self) -> str:
        if not self.inventory:
            self.load_inventory()
        archives = self.inventory.get("archives", [])
        main = next((a for a in archives if "AliceBlue" in a.get("access_point", "")), archives[0] if archives else None)
        if not main or not main.get("access_point"):
            raise RuntimeError("no archive access point available")
        return main["access_point"]

    def archive_source_access_point(self) -> str:
        if not self.inventory:
            self.load_inventory()
        sources = [
            item["access_point"]
            for item in self.inventory.get("components", [])
            if "/Sources/src." in item.get("access_point", "")
        ]
        if not sources:
            raise RuntimeError("no archive source access point available")
        return sources[0]

    def archive_time_range_1900_ms(self, hours: float = 1.0) -> tuple[int, int]:
        epoch_1900_ms = 2208988800000
        now = dt.datetime.now(dt.UTC)
        begin = int((now - dt.timedelta(hours=hours)).timestamp() * 1000) + epoch_1900_ms
        end = int(now.timestamp() * 1000) + epoch_1900_ms
        return begin, end

    def archive_time_range_legacy(self, hours: float = 1.0) -> tuple[str, str]:
        now = dt.datetime.now(dt.UTC)
        begin = (now - dt.timedelta(hours=hours)).strftime("%Y%m%dT%H%M%S.%f")
        end = now.strftime("%Y%m%dT%H%M%S.%f")
        return begin, end

    def archive_volume_id(self) -> str:
        if self._archive_volume_id is not None:
            return self._archive_volume_id
        archive_pb2 = self.import_module("axxonsoft.bl.archive.ArchiveSupport_pb2")
        archive_stub = self.common_stubs()["archive"]
        state = archive_stub.GetVolumesState(
            archive_pb2.GetVolumesStateRequest(access_point=self.archive_access_point()),
            timeout=self.config.timeout,
        )
        if not state.volumes_state:
            raise RuntimeError("archive has no volume IDs")
        self._archive_volume_id = next(iter(state.volumes_state.keys()))
        return self._archive_volume_id
