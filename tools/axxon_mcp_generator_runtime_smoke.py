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
import subprocess
import sys
import tempfile
import time
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
]


HOST_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b")
CN_ENV_RE = re.compile(r"AXXON_TLS_CN=\S+")
CN_LOG_RE = re.compile(r"tls_cn=\S+")


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


def resolve_export_window(env: dict[str, str]) -> tuple[str, str] | None:
    """Use AxxonApiClient to find a recent archive interval for camera 1."""
    sys.path.insert(0, "/Users/jerrygergov/Documents/GitHub/axxonnext.docker/arm64-docker/tools")
    try:
        from axxon_api_client import AxxonApiClient, AxxonClientConfig
    except ImportError:
        return None
    bare_env = dict(env)
    host = bare_env.get("AXXON_HOST", "")
    if ":" in host:
        bare_env["AXXON_HOST"], bare_env["AXXON_GRPC_PORT"] = host.split(":", 1)
    saved = {k: os.environ.get(k) for k in ("AXXON_HOST", "AXXON_GRPC_PORT")}
    os.environ["AXXON_HOST"] = bare_env["AXXON_HOST"]
    if "AXXON_GRPC_PORT" in bare_env:
        os.environ["AXXON_GRPC_PORT"] = bare_env["AXXON_GRPC_PORT"]
    try:
        cfg = AxxonClientConfig.from_env(repo_root=Path("/Users/jerrygergov/Documents/GitHub/axxonnext.docker/arm64-docker"))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    client = AxxonApiClient(cfg)
    try:
        client.authenticate_grpc()
        history = client.get_archive_history(
            access_point="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            begin_time=0,
            end_time=int(time.time() * 1000) * 10000,
            max_count=8,
        )
        intervals = history.get("intervals", [])
        if not intervals:
            return None
        last = intervals[-1]
        return last.get("begin_time"), last.get("end_time")
    except Exception as exc:  # noqa: BLE001
        print(f"window resolve failed: {exc}", file=sys.stderr)
    return None


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

    # Window pre-resolution is unused now that export_job is read-only.
    rows: list[dict] = []
    overall_ok = True

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        for case in CASES:
            template = case["template"]
            if template in args.skip:
                rows.append({"template": template, "status": "skipped"})
                continue
            params = dict(case["params"])
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
                outcome = run_bundle(bundle_dir, env, args.timeout)
            except subprocess.TimeoutExpired:
                outcome = {"exit": 124, "elapsed": args.timeout, "stdout": "", "stderr": "timeout"}
            rows.append({
                "template": template,
                "status": "ok" if outcome["exit"] == 0 else "fail",
                **outcome,
            })
            if outcome["exit"] != 0:
                overall_ok = False

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
