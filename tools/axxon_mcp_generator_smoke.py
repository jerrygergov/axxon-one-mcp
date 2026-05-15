#!/usr/bin/env python3
"""Static smoke for the Phase 4 generator.

Generates one bundle per template, runs the verifier, and runs py_compile on
each main.py. Writes a sanitized evidence report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import py_compile
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_generator import Generator, GenerationRequest, Verifier, GeneratedBundle, GenerationRefusal


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
        "params": {"subject": "hosts/Server/AppDataDetector.27/EventSupplier"},
    },
    {
        "template": "external_event_producer",
        "params": {"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1"},
    },
    {
        "template": "export_job",
        "params": {
            "camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "begin": "2026-05-15T10:00:00Z",
            "end": "2026-05-15T10:05:00Z",
            "format": "jpeg",
        },
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path(__file__).resolve().parents[1] / "docs" / "api-audit" / "mcp-generation-smoke-latest.md")
    args = parser.parse_args()

    gen = Generator()
    verifier = Verifier()
    rows: list[dict] = []
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        for case in CASES:
            req = GenerationRequest(template=case["template"], params=case["params"])
            result = gen.generate(req)
            row = {"template": case["template"], "params": case["params"]}
            if isinstance(result, GenerationRefusal):
                row["status"] = "refused"
                row["reason"] = result.reason
                row["detail"] = result.detail
                ok = False
                rows.append(row)
                continue
            assert isinstance(result, GeneratedBundle)
            bundle_dir = tmp_root / case["template"]
            bundle_dir.mkdir()
            for name, content in result.files.items():
                (bundle_dir / name).write_text(content, encoding="utf-8")
            v = verifier.verify_dir(bundle_dir)
            try:
                py_compile.compile(str(bundle_dir / "main.py"), doraise=True)
                compiles = True
            except py_compile.PyCompileError as exc:
                compiles = False
                row["compile_error"] = str(exc)
            row["status"] = "ok" if v.ok and compiles else "fail"
            row["verifier_ok"] = v.ok
            row["verifier_errors"] = v.errors
            row["compiles"] = compiles
            row["file_count"] = len(result.files)
            row["main_bytes"] = len(result.files["main.py"])
            row["notes"] = result.notes
            row["required_fixtures"] = result.required_fixtures
            row["required_env"] = result.required_env
            if not v.ok or not compiles:
                ok = False
            rows.append(row)

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    md = ["# MCP Generation Static Smoke", "", f"_run at {timestamp}_", "", "| template | status | files | bytes | verifier | compiles |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        md.append(
            f"| {r['template']} | {r['status']} | {r.get('file_count', '')} | {r.get('main_bytes', '')} | {'ok' if r.get('verifier_ok') else 'fail'} | {'yes' if r.get('compiles') else 'no'} |"
        )
    md.append("")
    md.append("## Detail")
    for r in rows:
        md.append("")
        md.append(f"### {r['template']}")
        md.append("```json")
        md.append(json.dumps({k: v for k, v in r.items() if k not in {"params"}}, indent=2, sort_keys=True))
        md.append("```")
    md.append("")
    md.append("## Next step (runtime smoke)")
    md.append("")
    md.append("Each bundle requires the standard `AXXON_*` env vars listed in `required_env`. Run `python main.py` inside the generated directory with the demo profile loaded to exercise live execution. Network execution is intentionally out of scope for this static smoke and is gated on user approval per Stop Conditions in `docs/plans/2026-05-15-mcp-phase-4-integration-generation.md`.")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"ok": ok, "report": str(args.report), "rows": rows}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
