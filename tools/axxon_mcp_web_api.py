#!/usr/bin/env python3
"""Web server / embeddable video component / WebSocket-event helpers for the Axxon One MCP (Phase 5).

The Axxon One Web server (port 80 on a standard install) hosts an embeddable video component
(`/embedded.html`) controlled from the browser via `postMessage`, and a WebSocket events surface
(`/events`, `/ws`, `/ws/events`). This module exposes read-only / knowledge tools for that surface:

- web_api_connect_axxon_profile: lazy, env-only profile connect (read mode, secrets redacted)
- embeddable_component_url: build the `/embedded.html` iframe `src` and a paste-ready snippet
- embeddable_component_commands: typed postMessage command catalog for the video component
- web_events_probe: a single bounded WebSocket handshake; reports 101/upgrade metadata only
- web_events_sample: open one bounded WS connection, read capped frames, report opcode/size tallies
- web_client_parity_report: knowledge map of what the Web client surface covers vs MCP groups

Every result is metadata only. Raw frame payload bytes, the Sec-WebSocket-Accept value, cookies,
credentials, and CA material are never returned. WS probes are restricted to an allowlist of known
event paths and hard-capped on frame count and wall-clock time.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from pathlib import Path
import socket
import time
from typing import Any, Callable
from urllib.parse import quote, urlsplit

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

EMBEDDED_PATH = "/embedded.html"
KNOWN_EVENT_PATHS = ("/events", "/ws", "/ws/events")
EMBEDDABLE_MODES = ("live", "archive")
MAX_EVENT_FRAMES = 8
MAX_EVENT_SECONDS = 5.0
HANDSHAKE_TIMEOUT_S = 4.0
RECV_CHUNK = 4096

WEB_API_TOOL_NAMES = (
    "web_api_connect_axxon_profile",
    "embeddable_component_url",
    "embeddable_component_commands",
    "web_events_probe",
    "web_events_sample",
    "web_client_parity_report",
)

# postMessage command catalog (Integration APIs 3.0, section 6, pages 525-529).
_COMMAND_CATALOG = (
    {"type": "init", "fields": {"mode": "live | archive", "origin": "VIDEOSOURCEID", "time": "Date", "options": "{archivePane?: boolean}"},
     "purpose": "Select a camera and its mode (first command)."},
    {"type": "reInit", "fields": {"mode": "live | archive", "origin": "VIDEOSOURCEID", "time": "Date", "options": "{archivePane?: boolean}"},
     "purpose": "Switch to a different camera after init."},
    {"type": "live | archive", "fields": {}, "purpose": "SwitchMode: toggle between live and archive."},
    {"type": "play | stop", "fields": {}, "purpose": "PlaybackCommand: start/stop archive playback."},
    {"type": "setTime", "fields": {"time": "Date (ISO 8601)"}, "purpose": "Seek to a time in archive mode."},
    {"type": "setCamera", "fields": {"origin": "VIDEOSOURCEID"}, "purpose": "Focus on the selected camera."},
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def default_socket_factory(host: str, port: int, timeout: float) -> Any:
    return socket.create_connection((host, port), timeout=timeout)


@dataclass
class AxxonMcpWebApi:
    """Web server / embeddable component / WebSocket-event helpers (Phase 5). Read-only, no write gate."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    socket_factory: Callable[[str, int, float], Any] = default_socket_factory
    client: Any | None = None
    profile_name: str | None = None

    def web_api_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.web_api_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.web_api_connect_axxon_profile("env")
        return self.client

    def _http_target(self) -> tuple[str, str, int]:
        """Return (http_url, host, port) for the connected profile's Web server."""
        config = self.ensure_client().config
        http_url = str(getattr(config, "http_url", "")).rstrip("/")
        parts = urlsplit(http_url)
        host = parts.hostname or str(getattr(config, "host", ""))
        port = parts.port or (443 if parts.scheme == "https" else 80)
        return http_url, host, port

    def embeddable_component_url(self, camera_origin: str = "", mode: str = "live", time: str = "", archive_pane: bool | None = None) -> dict[str, Any]:
        """Build the `/embedded.html` iframe src for the embeddable video component (no credentials)."""
        if mode not in EMBEDDABLE_MODES:
            return {"status": "error", "tool": "embeddable_component_url", "message": f"mode must be one of {EMBEDDABLE_MODES}"}
        http_url, _, _ = self._http_target()
        url = http_url + EMBEDDED_PATH
        query: list[str] = []
        if camera_origin:
            query.append("origin=" + quote(camera_origin, safe=""))
        query.append("mode=" + mode)
        if time:
            query.append("time=" + quote(time, safe=""))
        if archive_pane is not None:
            query.append("archivePane=" + ("true" if archive_pane else "false"))
        full_url = url + "?" + "&".join(query) if query else url
        snippet = f'<iframe src="{full_url}" width="800px" height="600px" id="axxon-video"></iframe>'
        return {
            "status": "ok",
            "tool": "embeddable_component_url",
            "url": full_url,
            "iframe_snippet": snippet,
            "control": "Send postMessage commands to the iframe; see embeddable_component_commands.",
        }

    def embeddable_component_commands(self) -> dict[str, Any]:
        """Return the typed postMessage command catalog for the embeddable video component (knowledge only)."""
        return {
            "status": "ok",
            "tool": "embeddable_component_commands",
            "transport": "window.postMessage to the iframe contentWindow",
            "commands": [dict(c) for c in _COMMAND_CATALOG],
            "notes": "Times must be in ISO 8601 format. origin is the VIDEOSOURCEID (camera source endpoint).",
            "source": "Integration APIs 3.0, section 6 (pages 525-529).",
        }

    def web_events_probe(self, path: str = "/events") -> dict[str, Any]:
        """Perform one bounded WebSocket handshake and report 101/upgrade metadata only."""
        if path not in KNOWN_EVENT_PATHS:
            return {"status": "error", "tool": "web_events_probe", "message": f"path must be one of {KNOWN_EVENT_PATHS}"}
        _, host, port = self._http_target()
        sock = self.socket_factory(host, port, HANDSHAKE_TIMEOUT_S)
        try:
            sock.settimeout(HANDSHAKE_TIMEOUT_S)
            status, upgraded = self._handshake(sock, host, path)
        finally:
            self._safe_close(sock)
        return {
            "status": "ok",
            "tool": "web_events_probe",
            "path": path,
            "http_status": status,
            "upgraded": upgraded,
            "is_known_event_path": True,
        }

    def web_events_sample(self, path: str = "/events", max_frames: int = MAX_EVENT_FRAMES) -> dict[str, Any]:
        """Open one bounded WS connection and report frame count + opcode/size tallies (no raw payload bytes)."""
        if path not in KNOWN_EVENT_PATHS:
            return {"status": "error", "tool": "web_events_sample", "message": f"path must be one of {KNOWN_EVENT_PATHS}"}
        cap = max(1, min(int(max_frames), MAX_EVENT_FRAMES))
        _, host, port = self._http_target()
        sock = self.socket_factory(host, port, HANDSHAKE_TIMEOUT_S)
        frames = 0
        total_bytes = 0
        opcode_tallies: dict[str, int] = {}
        deadline = time.monotonic() + MAX_EVENT_SECONDS
        try:
            sock.settimeout(HANDSHAKE_TIMEOUT_S)
            status, upgraded = self._handshake(sock, host, path)
            if upgraded:
                buffer = b""
                while frames < cap and time.monotonic() < deadline:
                    try:
                        chunk = sock.recv(RECV_CHUNK)
                    except (TimeoutError, OSError):
                        break
                    if not chunk:
                        break
                    buffer += chunk
                    parsed, buffer = self._drain_frames(buffer, cap - frames)
                    for opcode, size in parsed:
                        frames += 1
                        total_bytes += size
                        opcode_tallies[opcode] = opcode_tallies.get(opcode, 0) + 1
                        if opcode == "close":
                            break
                    if any(op == "close" for op, _ in parsed):
                        break
        finally:
            self._safe_close(sock)
        return {
            "status": "ok",
            "tool": "web_events_sample",
            "path": path,
            "http_status": status,
            "upgraded": upgraded,
            "frames": frames,
            "payload_bytes_seen": total_bytes,
            "opcode_tallies": opcode_tallies,
            "frame_cap": cap,
            "seconds_cap": MAX_EVENT_SECONDS,
        }

    def web_client_parity_report(self) -> dict[str, Any]:
        """Map the Web client surface to existing MCP groups, highlighting browser-only pieces (offline)."""
        return {
            "status": "ok",
            "tool": "web_client_parity_report",
            "surfaces": [
                {"surface": "Live + archive video", "web_client": "embedded component / web client", "mcp_groups": ["view", "media"], "notes": "Server delivers URLs/probes; rendering is browser-side."},
                {"surface": "Camera/layout inventory", "web_client": "layout switcher", "mcp_groups": ["live", "view_objects", "layout_manager", "site_graph"]},
                {"surface": "Events / alarms", "web_client": "WebSocket /events", "mcp_groups": ["live", "alarms", "logic_alerts"], "notes": "web_events_probe/sample cover the WS transport read-only; bounded."},
                {"surface": "Export", "web_client": "export panel", "mcp_groups": ["export"]},
                {"surface": "Videowall / displays", "web_client": "videowall control", "mcp_groups": ["videowall", "view_objects"]},
                {"surface": "Embeddable video component", "web_client": "iframe + postMessage", "mcp_groups": ["web_api"], "notes": "Browser-only postMessage API; MCP ships URL + command-schema helpers only."},
            ],
            "browser_only": "The embeddable video component is controlled by window.postMessage from the host page; there is no server RPC, so the MCP cannot drive playback itself.",
        }

    @staticmethod
    def _handshake(sock: Any, host: str, path: str) -> tuple[int, bool]:
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode("latin1"))
        raw = sock.recv(RECV_CHUNK)
        head = raw.split(b"\r\n\r\n", 1)[0].decode("latin1", "replace")
        status_line = head.splitlines()[0] if head else ""
        parts = status_line.split(" ")
        status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        upgraded = status == 101 and "upgrade: websocket" in head.lower()
        return status, upgraded

    @staticmethod
    def _drain_frames(buffer: bytes, remaining: int) -> tuple[list[tuple[str, int]], bytes]:
        """Parse complete WS frames from buffer; return (opcode, payload_len) tuples and leftover bytes."""
        opcodes = {0x0: "continuation", 0x1: "text", 0x2: "binary", 0x8: "close", 0x9: "ping", 0xA: "pong"}
        parsed: list[tuple[str, int]] = []
        while remaining > 0 and len(buffer) >= 2:
            b0, b1 = buffer[0], buffer[1]
            opcode = opcodes.get(b0 & 0x0F, f"opcode-{b0 & 0x0F}")
            masked = bool(b1 & 0x80)
            length = b1 & 0x7F
            offset = 2
            if length == 126:
                if len(buffer) < 4:
                    break
                length = int.from_bytes(buffer[2:4], "big")
                offset = 4
            elif length == 127:
                if len(buffer) < 10:
                    break
                length = int.from_bytes(buffer[2:10], "big")
                offset = 10
            if masked:
                offset += 4
            if len(buffer) < offset + length:
                break
            parsed.append((opcode, length))
            buffer = buffer[offset + length:]
            remaining -= 1
        return parsed, buffer

    @staticmethod
    def _safe_close(sock: Any) -> None:
        try:
            sock.close()
        except OSError:
            pass
