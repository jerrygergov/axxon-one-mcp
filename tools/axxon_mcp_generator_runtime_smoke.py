#!/usr/bin/env python3
"""Runtime smoke for the Phase 4 generator.

Generates each template into a temporary directory and executes the generated
`main.py` with the AXXON_* env vars from the calling shell. Captures stdout,
exit code, and elapsed seconds. Writes a sanitized evidence report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_generator import Generator, GenerationRequest, GeneratedBundle, GenerationRefusal


CASES = [
    {
        "template": "grpc_consumer",
        "params": {"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
    },
    {
        "template": "http_grpc_consumer",
        "params": {"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits"},
    },
    {
        "template": "legacy_http_consumer",
        "params": {"path": "/v1/security/checklogin"},
    },
    {
        "template": "event_consumer",
        "params": {"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "duration": 10, "count": 20},
    },
    {
        "template": "external_event_producer",
        "params": {"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1"},
    },
    {
        "template": "export_job",
        "params": {
            "camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "begin": "2026-05-15T00:00:00Z",
            "end": "2026-05-15T00:05:00Z",
            "format": "jpeg",
        },
    },
    {
        "template": "webhook_bridge",
        "params": {"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "duration": 10, "count": 20},
        "needs_webhook": True,
    },
    {
        "template": "inventory_sync",
        "params": {"output_path": "{tmp}/inventory.json"},
        "needs_tmp_path": True,
    },
]


HOST_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b")
CN_ENV_RE = re.compile(r"AXXON_TLS_CN=\S+")
CN_LOG_RE = re.compile(r"tls_cn=\S+")


class WebhookReceiver(BaseHTTPRequestHandler):
    counter = 0

    def do_POST(self):
        WebhookReceiver.counter += 1
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args, **kwargs):
        return


def start_webhook_server() -> tuple[HTTPServer, str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = HTTPServer(("127.0.0.1", port), WebhookReceiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}/hook"


def sanitize(text: str) -> str:
    text = HOST_RE.sub("<demo-host>", text)
    text = CN_ENV_RE.sub("AXXON_TLS_CN=<your-tls-cn>", text)
    text = CN_LOG_RE.sub("tls_cn=<your-tls-cn>", text)
    return text


def run_bundle(bundle_dir: Path, env: dict[str, str], timeout: int) -> dict:
    start = time.time()
    proc = subprocess.run(
        [sys.executable, str(bundle_dir / "main.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "exit": proc.returncode,
        "elapsed": round(time.time() - start, 2),
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "api-audit" / "mcp-generation-runtime-smoke-latest.md",
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--skip", action="append", default=[])
    args = parser.parse_args()

    required_env = ("AXXON_HOST", "AXXON_HTTP_URL", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD")
    missing = [k for k in required_env if not os.environ.get(k)]
    if missing:
        print(f"missing env: {','.join(missing)}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.setdefault("AXXON_STUBS_PATH", "/tmp/axxon-grpc-py")
    gen = Generator()

    rows: list[dict] = []
    overall_ok = True

    webhook_server, webhook_url = start_webhook_server()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for case in CASES:
                template = case["template"]
                if template in args.skip:
                    rows.append({"template": template, "status": "skipped"})
                    continue
                params = dict(case["params"])
                if case.get("needs_tmp_path"):
                    params = {k: v.format(tmp=str(tmp_root)) if isinstance(v, str) else v for k, v in params.items()}
                case_env = env.copy()
                if case.get("needs_webhook"):
                    case_env["WEBHOOK_URL"] = webhook_url
                req = GenerationRequest(template=template, params=params)
                result = gen.generate(req)
                if isinstance(result, GenerationRefusal):
                    rows.append({"template": template, "status": "refused", "reason": result.reason, "detail": result.detail})
                    overall_ok = False
                    continue
                assert isinstance(result, GeneratedBundle)
                bundle_dir = tmp_root / template
                bundle_dir.mkdir()
                for name, content in result.files.items():
                    (bundle_dir / name).write_text(content, encoding="utf-8")
                try:
                    outcome = run_bundle(bundle_dir, case_env, args.timeout)
                except subprocess.TimeoutExpired:
                    outcome = {"exit": 124, "elapsed": args.timeout, "stdout": "", "stderr": "timeout"}
                rows.append({
                    "template": template,
                    "status": "ok" if outcome["exit"] == 0 else "fail",
                    **outcome,
                })
                if outcome["exit"] != 0:
                    overall_ok = False
    finally:
        webhook_server.shutdown()
        webhook_server.server_close()

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    md = [
        "# MCP Generation Runtime Smoke",
        "",
        f"_run at {timestamp}_",
        "",
        "| template | status | exit | elapsed_s |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        md.append(f"| {r['template']} | {r.get('status', '')} | {r.get('exit', '')} | {r.get('elapsed', '')} |")
    md.append("")
    md.append("## Output detail (sanitized)")
    for r in rows:
        md.append("")
        md.append(f"### {r['template']}")
        if "reason" in r:
            md.append(f"reason: `{r['reason']}`")
        if "stdout" in r:
            md.append("")
            md.append("stdout:")
            md.append("```")
            md.append(sanitize(r["stdout"]).strip() or "<empty>")
            md.append("```")
        if r.get("stderr"):
            md.append("")
            md.append("stderr:")
            md.append("```")
            md.append(sanitize(r["stderr"]).strip())
            md.append("```")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(md) + "\n", encoding="utf-8")
    summary = [{k: v for k, v in r.items() if k not in {"stdout", "stderr"}} for r in rows]
    print(json.dumps({"ok": overall_ok, "report": str(args.report), "rows": summary}, indent=2))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
