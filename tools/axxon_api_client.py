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
        stubs = self.common_stubs()
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

    def node_name(self) -> str:
        if not self.inventory:
            self.load_inventory()
        nodes = self.inventory.get("nodes", [])
        return nodes[0].get("node_name", self.config.tls_cn) if nodes else self.config.tls_cn

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
