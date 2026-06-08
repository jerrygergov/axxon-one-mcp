#!/usr/bin/env python3
"""Bounded smoke checks for legacy HTTP media and snapshot endpoints."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import time
import traceback
from typing import Any
from urllib.parse import quote

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


DEFAULT_MAX_BYTES = 1048576


def media_checks() -> list[dict[str, Any]]:
    return [
        {
            "name": "camera_stream_info",
            "path": "/stream-info/{camera_legacy_ap}",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "camera_snapshot",
            "path": "/live/media/snapshot/{camera_legacy_ap}?w=640&h=0",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "camera_live_mjpeg",
            "path": "/live/media/{camera_legacy_ap}?w=640&h=0",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "camera_live_hls",
            "path": "/live/media/{camera_legacy_ap}?format=hls",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "camera_live_mp4",
            "path": "/live/media/{camera_legacy_ap}?format=mp4",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "camera_live_rtsp_descriptor",
            "path": "/live/media/{camera_legacy_ap}?format=rtsp",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "rtsp_statistics",
            "path": "/rtsp/stat",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "rtsp_playback_ffprobe",
            "path": "rtsp://{host}:554/{camera_ap}",
            "max_bytes": 0,
        },
        {
            "name": "composite_rtsp_playback_ffprobe",
            "path": "rtsp://{host}:554/composite/{composite_sources}?res=640x360&fps=5&quality=4&softacceleration=1",
            "max_bytes": 0,
        },
        {
            "name": "onvif_rtp_timestamp_probe",
            "path": "rtsp://{host}:554/{camera_ap}",
            "max_bytes": 0,
        },
        {
            "name": "archive_frame_by_time",
            "path": "/archive/media/{camera_legacy_ap}/{archive_media_time}?threshold=60000&w=640&h=0",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
        {
            "name": "archive_media_mjpeg",
            "path": "/archive/media/{camera_legacy_ap}/{archive_media_time}?w=640&h=0&speed=1",
            "max_bytes": DEFAULT_MAX_BYTES,
        },
    ]


class MediaStreamSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.fixtures: dict[str, str] = {}
        self.results: list[dict[str, Any]] = []

    def setup(self) -> None:
        if self.args.auth_mode == "bearer":
            self.client.authenticate_http_grpc()
        inventory = self.client.load_inventory()
        camera = self.choose_camera(inventory.get("cameras", []))
        camera_ap = camera.get("access_point", "")
        composite_sources = self.composite_sources(inventory.get("cameras", []))
        begin, end = self.client.archive_time_range_legacy(hours=self.args.hours)
        archive_interval = self.archive_interval(camera_ap.removeprefix("hosts/"), begin, end)
        archive_media_time = archive_interval.get("end") or archive_interval.get("begin") or begin
        self.fixtures = {
            "camera_ap": camera_ap,
            "camera_legacy_ap": camera_ap.removeprefix("hosts/"),
            "composite_sources": composite_sources,
            "begin": begin,
            "end": end,
            "archive_interval_begin": archive_interval.get("begin", ""),
            "archive_interval_end": archive_interval.get("end", ""),
            "archive_media_time": archive_media_time,
            "host": self.args.host,
        }

    def choose_camera(self, cameras: list[dict[str, Any]]) -> dict[str, Any]:
        preferred_names = {"Tracker", "Face", "LPR + MMR", "Traffic Analyzer RR 1"}
        for camera in cameras:
            if camera.get("display_name") in preferred_names and camera.get("access_point"):
                return camera
        return next((camera for camera in cameras if camera.get("access_point")), {})

    def composite_sources(self, cameras: list[dict[str, Any]], limit: int = 2) -> str:
        tokens: list[str] = []
        for camera in cameras:
            access_point = str(camera.get("access_point", ""))
            if not access_point.startswith("hosts/"):
                continue
            parts = access_point.split("/")
            if len(parts) < 4:
                continue
            node = parts[1]
            display_id = str(camera.get("display_id") or "")
            if not display_id and parts[2].startswith("DeviceIpint."):
                display_id = parts[2].split(".", 1)[1]
            stream_suffix = parts[-1].removeprefix("SourceEndpoint.video:")
            stream_parts = stream_suffix.split(":")
            if len(stream_parts) < 2 or not display_id:
                continue
            tokens.append(f"{node}/{display_id}/{stream_parts[0]}/{stream_parts[1]}")
            if len(tokens) >= limit:
                break
        return "+".join(tokens)

    def auth_kwargs(self) -> dict[str, bool]:
        return {
            "basic": self.args.auth_mode == "basic",
            "bearer": self.args.auth_mode == "bearer",
        }

    def archive_interval(self, camera_legacy_ap: str, begin: str, end: str) -> dict[str, str]:
        if not camera_legacy_ap:
            return {}
        try:
            response = self.client.http_request(
                "GET",
                f"/archive/contents/intervals/{camera_legacy_ap}/{end}/{begin}",
                **self.auth_kwargs(),
                max_items=1,
            )
        except Exception:
            return {}
        if response.get("status") != 200:
            return {}
        body = response.get("body", {})
        intervals = body.get("intervals", []) if isinstance(body, dict) else []
        if not intervals:
            return {}
        interval = intervals[0]
        return {
            "begin": str(interval.get("begin", "")),
            "end": str(interval.get("end", "")),
        }

    def selected_checks(self) -> list[dict[str, Any]]:
        checks = media_checks()
        if not self.args.check:
            return checks
        wanted = set(self.args.check)
        return [check for check in checks if check["name"] in wanted]

    def invoke(self, check: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        path = check["path"].format(**self.fixtures)
        max_bytes = min(int(check["max_bytes"]), int(self.args.max_bytes))
        if not self.fixtures.get("camera_legacy_ap"):
            return self.result(check, path, "WARN", {"reason": "missing camera fixture"}, start)
        if check["name"] == "rtsp_playback_ffprobe":
            return self.invoke_rtsp_playback(check, path, start)
        if check["name"] == "composite_rtsp_playback_ffprobe":
            return self.invoke_composite_rtsp_playback(check, path, start)
        if check["name"] == "onvif_rtp_timestamp_probe":
            return self.invoke_onvif_rtp_timestamp_probe(check, path, start)
        try:
            response = self.client.http_request(
                "GET",
                path,
                **self.auth_kwargs(),
                raw_body=True,
                max_bytes=max_bytes,
            )
            body = response.get("body", {})
            details = {
                "http_status": response["status"],
                "content_type": response["content_type"],
                "size": response["size"],
                "raw_bytes": body.get("raw_bytes", response["size"]),
                "sha256": body.get("sha256"),
                "max_bytes": max_bytes,
            }
            status = "PASS" if 200 <= response["status"] < 300 and response["size"] > 0 else "WARN"
            return self.result(check, path, status, details, start)
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(check, path, "WARN", details, start)

    def invoke_rtsp_playback(self, check: dict[str, Any], display_path: str, start: float) -> dict[str, Any]:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return self.result(check, display_path, "WARN", {"reason": "ffprobe not found"}, start, method="FFPROBE")
        descriptor = self.rtsp_descriptor()
        rtsp = descriptor.get("rtsp", {}) if isinstance(descriptor, dict) else {}
        rtsp_path = rtsp.get("path") or self.fixtures.get("camera_ap", "")
        rtsp_port = str(rtsp.get("port") or "554")
        safe_url = f"rtsp://{self.args.host}:{rtsp_port}/{rtsp_path}"
        auth_url = f"rtsp://{quote(self.args.username, safe='')}:{quote(self.args.password, safe='')}@{self.args.host}:{rtsp_port}/{rtsp_path}"
        command = [
            ffprobe,
            "-v",
            "error",
            "-rtsp_transport",
            "tcp",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            "-timeout",
            str(int(max(1.0, self.args.timeout) * 1_000_000)),
            auth_url,
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(2.0, self.args.timeout + 2.0),
            )
            data = json.loads(completed.stdout or "{}")
            streams = data.get("streams", []) if isinstance(data, dict) else []
            details = {
                "tool": Path(ffprobe).name,
                "returncode": completed.returncode,
                "rtsp_url": safe_url,
                "rtsp_port": rtsp_port,
                "stream_count": len(streams),
                "first_stream": streams[0] if streams else {},
            }
            if completed.returncode != 0 or not streams:
                details["stderr_prefix"] = completed.stderr[:400]
            status = "PASS" if completed.returncode == 0 and streams else "WARN"
            return self.result(check, safe_url, status, details, start, method="FFPROBE")
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800], "rtsp_url": safe_url}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(check, safe_url, "WARN", details, start, method="FFPROBE")

    def invoke_composite_rtsp_playback(self, check: dict[str, Any], display_path: str, start: float) -> dict[str, Any]:
        if not self.fixtures.get("composite_sources"):
            return self.result(
                check,
                display_path,
                "WARN",
                {"reason": "missing composite camera sources"},
                start,
                method="FFPROBE",
            )
        safe_url = display_path
        auth_url = safe_url.replace(
            f"rtsp://{self.args.host}:",
            f"rtsp://{quote(self.args.username, safe='')}:{quote(self.args.password, safe='')}@{self.args.host}:",
            1,
        )
        return self.invoke_ffprobe(
            check,
            safe_url,
            auth_url,
            start,
            {
                "composite_sources": self.fixtures["composite_sources"],
                "source_count": len(self.fixtures["composite_sources"].split("+")),
            },
        )

    def invoke_onvif_rtp_timestamp_probe(self, check: dict[str, Any], display_path: str, start: float) -> dict[str, Any]:
        descriptor = self.rtsp_descriptor()
        rtsp = descriptor.get("rtsp", {}) if isinstance(descriptor, dict) else {}
        rtsp_path = rtsp.get("path") or self.fixtures.get("camera_ap", "")
        rtsp_port = int(rtsp.get("port") or 554)
        safe_url = f"rtsp://{self.args.host}:{rtsp_port}/{rtsp_path}"
        try:
            details = self.probe_onvif_rtp_timestamp(rtsp_path, rtsp_port)
            details["rtsp_url"] = safe_url
            status = "PASS" if details.get("onvif_extension_count", 0) > 0 else "WARN"
            return self.result(check, safe_url, status, details, start, method="RTSP")
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800], "rtsp_url": safe_url}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(check, safe_url, "WARN", details, start, method="RTSP")

    def rtsp_descriptor(self) -> dict[str, Any]:
        response = self.client.http_request(
            "GET",
            f"/live/media/{self.fixtures['camera_legacy_ap']}?format=rtsp",
            **self.auth_kwargs(),
            max_bytes=DEFAULT_MAX_BYTES,
        )
        return response.get("body", {}) if response.get("status") == 200 else {}

    def probe_onvif_rtp_timestamp(self, rtsp_path: str, rtsp_port: int) -> dict[str, Any]:
        host = self.args.host
        uri = f"rtsp://{host}:{rtsp_port}/{rtsp_path}"
        auth = "Basic " + base64.b64encode(f"{self.args.username}:{self.args.password}".encode()).decode()
        deadline = time.monotonic() + max(2.0, self.args.timeout)
        with socket.create_connection((host, rtsp_port), timeout=self.args.timeout) as sock:
            sock.settimeout(min(2.0, self.args.timeout))
            session = ""

            def send_request(method: str, request_uri: str, cseq: int, headers: list[str] | None = None) -> tuple[str, bytes]:
                lines = [
                    f"{method} {request_uri} RTSP/1.0",
                    f"CSeq: {cseq}",
                    f"Authorization: {auth}",
                    "User-Agent: codex-rtsp-onvif-probe",
                ]
                if session:
                    lines.append(f"Session: {session}")
                if headers:
                    lines.extend(headers)
                sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
                return self.read_rtsp_response(sock)

            send_request("OPTIONS", uri, 1)
            _, sdp = send_request("DESCRIBE", uri, 2, ["Accept: application/sdp"])
            control = self.sdp_control_track(sdp.decode("latin1", "replace"))
            setup_uri = uri.rstrip("/") + "/" + control
            setup_response, _ = send_request("SETUP", setup_uri, 3, ["Transport: RTP/AVP/TCP;unicast;interleaved=0-1"])
            session = self.rtsp_session_id(setup_response)
            send_request("PLAY", uri, 4, ["Range: npt=0-"])

            packet_count = 0
            extension_count = 0
            onvif_extension_count = 0
            first_timestamp = ""
            first_profile = ""
            first_sequence = None
            while time.monotonic() < deadline and packet_count < 300:
                marker = self.recv_exact(sock, 1)
                if marker != b"$":
                    continue
                header = self.recv_exact(sock, 3)
                channel = header[0]
                length = struct.unpack("!H", header[1:])[0]
                payload = self.recv_exact(sock, length)
                if channel != 0:
                    continue
                parsed = parse_rtp_onvif_timestamp(payload)
                packet_count += 1
                if parsed.get("has_extension"):
                    extension_count += 1
                if parsed.get("onvif_timestamp"):
                    onvif_extension_count += 1
                    first_timestamp = first_timestamp or str(parsed["onvif_timestamp"])
                    first_profile = first_profile or str(parsed.get("extension_profile", ""))
                    first_sequence = first_sequence if first_sequence is not None else parsed.get("sequence")
                    if onvif_extension_count >= 3:
                        break
            try:
                sock.sendall((f"TEARDOWN {uri} RTSP/1.0\r\nCSeq: 5\r\nAuthorization: {auth}\r\nSession: {session}\r\n\r\n").encode())
            except OSError:
                pass
        return {
            "packet_count": packet_count,
            "rtp_extension_count": extension_count,
            "onvif_extension_count": onvif_extension_count,
            "onvif_profile": first_profile,
            "first_sequence": first_sequence,
            "first_timestamp_utc": first_timestamp,
            "rtsp_transport": "RTP/AVP/TCP;interleaved=0-1",
            "max_packets": 300,
        }

    def read_rtsp_response(self, sock: socket.socket) -> tuple[str, bytes]:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        header, _, rest = data.partition(b"\r\n\r\n")
        text = header.decode("latin1", "replace")
        content_length = 0
        for line in text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break
        body = rest
        while len(body) < content_length:
            body += sock.recv(content_length - len(body))
        if " 200 " not in text.split("\r\n", 1)[0]:
            raise RuntimeError(text.split("\r\n", 1)[0])
        return text, body

    def recv_exact(self, sock: socket.socket, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise EOFError("socket closed")
            data += chunk
        return data

    def sdp_control_track(self, sdp: str) -> str:
        for line in sdp.splitlines():
            if line.startswith("a=control:stream="):
                return line.split(":", 1)[1].strip()
        return "stream=0"

    def rtsp_session_id(self, response: str) -> str:
        for line in response.split("\r\n"):
            if line.lower().startswith("session:"):
                return line.split(":", 1)[1].strip().split(";", 1)[0]
        raise RuntimeError("RTSP SETUP response did not include Session")

    def invoke_ffprobe(
        self,
        check: dict[str, Any],
        safe_url: str,
        auth_url: str,
        start: float,
        extra_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return self.result(check, safe_url, "WARN", {"reason": "ffprobe not found"}, start, method="FFPROBE")
        command = [
            ffprobe,
            "-v",
            "error",
            "-rtsp_transport",
            "tcp",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            "-timeout",
            str(int(max(1.0, self.args.timeout) * 1_000_000)),
            auth_url,
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(2.0, self.args.timeout + 2.0),
            )
            data = json.loads(completed.stdout or "{}")
            streams = data.get("streams", []) if isinstance(data, dict) else []
            details = {
                "tool": Path(ffprobe).name,
                "returncode": completed.returncode,
                "rtsp_url": safe_url,
                "stream_count": len(streams),
                "first_stream": streams[0] if streams else {},
            }
            if extra_details:
                details.update(extra_details)
            if completed.returncode != 0 or not streams:
                details["stderr_prefix"] = completed.stderr[:400]
            status = "PASS" if completed.returncode == 0 and streams else "WARN"
            return self.result(check, safe_url, status, details, start, method="FFPROBE")
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800], "rtsp_url": safe_url}
            if extra_details:
                details.update(extra_details)
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(check, safe_url, "WARN", details, start, method="FFPROBE")

    def result(
        self,
        check: dict[str, Any],
        path: str,
        status: str,
        details: dict[str, Any],
        start: float,
        *,
        method: str = "GET",
    ) -> dict[str, Any]:
        return {
            "name": check["name"],
            "method": method,
            "path": path,
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        for check in self.selected_checks():
            self.results.append(self.invoke(check))
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "http_url": self.args.http_url,
                "username": self.args.username,
                "password": "<redacted>",
            },
            "selection": {
                "checks": [check["name"] for check in self.selected_checks()],
                "timeout_seconds": self.args.timeout,
                "max_bytes": self.args.max_bytes,
                "auth_mode": self.args.auth_mode,
            },
            "fixtures": self.fixtures,
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"media-stream-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"media-stream-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "media-stream-smoke-latest.json"
        latest_md = self.args.report_dir / "media-stream-smoke-latest.md"
        json_text = json.dumps(self.client.sanitize(report), indent=2, ensure_ascii=True) + "\n"
        json_path.write_text(json_text, encoding="utf-8")
        latest_json.write_text(json_text, encoding="utf-8")
        md_text = self.render_markdown(report)
        md_path.write_text(md_text, encoding="utf-8")
        latest_md.write_text(md_text, encoding="utf-8")
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        print(f"Latest markdown: {latest_md}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Media Stream Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Max bytes per check: `{self.args.max_bytes}`",
            f"- Auth mode: `{report['selection']['auth_mode']}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Fixtures", ""])
        for key, value in report["fixtures"].items():
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Results", "", "| Status | Check | Endpoint | Size | Notes |", "| --- | --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            if result["method"] == "FFPROBE":
                stream = details.get("first_stream", {})
                note = f"ffprobe rc={details.get('returncode')} stream={stream.get('codec_name', '')} {stream.get('width', '')}x{stream.get('height', '')}"
            elif result["method"] == "RTSP":
                note = f"packets={details.get('packet_count')} onvif={details.get('onvif_extension_count')} first={details.get('first_timestamp_utc', '')}"
            else:
                note = f"HTTP {details.get('http_status')} {details.get('content_type', '')}"
            note = note.replace("|", "\\|")
            lines.append(f"| {result['status']} | `{result['name']}` | `{result['method']} {result['path']}` | {details.get('size', 0)} | {note} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--check", action="append", help="Limit to one check. Can be repeated.")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--auth-mode", choices=["anonymous", "basic", "bearer"], default="basic")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if args.max_bytes > DEFAULT_MAX_BYTES:
        parser.error(f"--max-bytes must be <= {DEFAULT_MAX_BYTES}")
    return args


def parse_rtp_onvif_timestamp(packet: bytes) -> dict[str, Any]:
    if len(packet) < 12:
        return {"has_extension": False}
    version = packet[0] >> 6
    if version != 2:
        return {"has_extension": False}
    has_extension = bool(packet[0] & 0x10)
    csrc_count = packet[0] & 0x0F
    sequence = struct.unpack("!H", packet[2:4])[0]
    offset = 12 + 4 * csrc_count
    result: dict[str, Any] = {"sequence": sequence, "has_extension": has_extension}
    if not has_extension or len(packet) < offset + 4:
        return result
    profile, word_count = struct.unpack("!HH", packet[offset : offset + 4])
    extension_data = packet[offset + 4 : offset + 4 + word_count * 4]
    result.update({"extension_profile": f"0x{profile:04x}", "extension_words": word_count})
    if profile == 0xABAC and len(extension_data) >= 8:
        ntp_seconds, ntp_fraction = struct.unpack("!II", extension_data[:8])
        unix_seconds = ntp_seconds - 2_208_988_800 + ntp_fraction / 2**32
        timestamp = dt.datetime.fromtimestamp(unix_seconds, dt.UTC).isoformat()
        result["onvif_timestamp"] = timestamp
    return result


def main() -> int:
    smoke = MediaStreamSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
