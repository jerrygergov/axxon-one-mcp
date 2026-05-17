#!/usr/bin/env python3
"""Live smoke for Phase 5A view tools against a configured Axxon stand.

Reads AXXON_HOST / AXXON_HTTP_URL / AXXON_USERNAME / AXXON_PASSWORD / AXXON_TLS_CN
from the environment via AxxonClientConfig.from_env. URLs and reports are
sanitized before printing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import urllib.request

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_view import AxxonMcpView  # noqa: E402


def sanitize_url(url: str, host: str) -> str:
    return url.replace(host, "<demo-host>")


def fetch_head(url: str, token: str, byte_cap: int, timeout: float = 15.0) -> dict[str, object]:
    """Fetch up to byte_cap bytes from url with Bearer auth; return a small summary."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(byte_cap + 1)
        return {
            "http_status": resp.status,
            "content_type": resp.headers.get("Content-Type"),
            "bytes_read": len(data),
            "truncated": len(data) > byte_cap,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-cameras", type=int, default=2)
    parser.add_argument("--fetch", action="store_true", help="Also fetch a bounded HEAD-equivalent for each returned URL.")
    args = parser.parse_args()

    view = AxxonMcpView()
    view.connect_axxon_profile("env")
    view.client.authenticate_http_grpc()
    inventory = view._ensure_inventory()
    cameras = [c.get("access_point") for c in inventory.get("cameras", []) if c.get("access_point")][: args.max_cameras]
    if not cameras:
        print(json.dumps({"status": "fixture-needed", "message": "no cameras in inventory"}, indent=2))
        return 2

    results: list[dict[str, object]] = []
    results.append({"name": "live_view_mjpeg", "result": view.live_view(cameras[0], format="mjpeg")})
    results.append({"name": "live_view_hls", "result": view.live_view(cameras[0], format="hls")})
    results.append({"name": "snapshot_batch_now", "result": view.snapshot_batch(cameras)})
    results.append({"name": "archive_scrub", "result": view.archive_scrub(cameras[0], hours=1)})

    scrub = results[-1]["result"]
    intervals = scrub.get("intervals", []) if isinstance(scrub, dict) else []
    sample_ts = None
    if intervals and isinstance(intervals[-1], dict):
        sample_ts = intervals[-1].get("end") or intervals[-1].get("begin")
    if sample_ts:
        results.append({"name": "archive_frame", "result": view.archive_frame(cameras[0], ts=sample_ts)})
        results.append({"name": "archive_mjpeg_bounded", "result": view.archive_mjpeg_bounded(cameras[0], begin_ts=sample_ts)})
    else:
        results.append({"name": "archive_frame", "result": {"status": "fixture-needed", "message": "no intervals found"}})
        results.append({"name": "archive_mjpeg_bounded", "result": {"status": "fixture-needed", "message": "no intervals found"}})

    results.append({"name": "stream_health", "result": view.stream_health(cameras[0])})

    host = view.client.config.host
    if args.fetch:
        token = getattr(view.client, "http_token", "") or ""
        for entry in results:
            r = entry["result"]
            if isinstance(r, dict) and r.get("status") == "ok" and isinstance(r.get("url"), str):
                byte_cap = int(r.get("caps", {}).get("bytes") or 1_048_576)
                try:
                    entry["fetch"] = fetch_head(r["url"], token, byte_cap=byte_cap)
                except Exception as exc:
                    entry["fetch"] = {"error": type(exc).__name__, "message": str(exc)[:160]}

    # Sanitize URLs in-place after fetches
    for entry in results:
        r = entry["result"]
        if isinstance(r, dict) and isinstance(r.get("url"), str):
            r["url"] = sanitize_url(r["url"], host)
        if isinstance(r, dict) and isinstance(r.get("sample_frame_url"), str):
            r["sample_frame_url"] = sanitize_url(r["sample_frame_url"], host)
        if isinstance(r, dict) and isinstance(r.get("items"), list):
            for item in r["items"]:
                if isinstance(item, dict) and isinstance(item.get("url"), str):
                    item["url"] = sanitize_url(item["url"], host)

    report = {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": "<demo-host>",
        "results": results,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
