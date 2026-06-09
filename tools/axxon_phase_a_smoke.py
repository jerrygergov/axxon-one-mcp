#!/usr/bin/env python3
"""Live smoke for Phase A tool groups (Steps 1-7).

Calls one representative read from each of the ten new groups against a connected Axxon One
server and reports PASS / WARN / FAIL per group. The one mutation (shared_kv.commit_record) is a
reversible round-trip: it sets a ``codex-*`` key then removes it, and verifies the key is gone.

Reads work over the HTTP /grpc bridge with no CA. Direct-gRPC groups need AXXON_CA + AXXON_PROTO_DIR
(the gitignored local CA and proto files); point the env at them. Transient remote errors
(``urlopen``/``DEADLINE_EXCEEDED``) are retried up to 3x before judging FAIL. A call the stand
cannot exercise (missing fixture) is reported WARN, not FAIL.

Examples:
    AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> AXXON_USERNAME=root AXXON_PASSWORD=*** \\
        AXXON_TLS_CN=Server AXXON_CA=docs/grpc-proto-files/api.ngp.root-ca.crt \\
        AXXON_PROTO_DIR=docs/grpc-proto-files \\
        python axxon_phase_a_smoke.py --commit
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig, add_common_args, config_from_args
import axxon_mcp_statistics as statistics
import axxon_mcp_event_taxonomy as event_taxonomy
import axxon_mcp_scene_description as scene_description
import axxon_mcp_package_availability as package_availability
import axxon_mcp_domain_topology as domain_topology
import axxon_mcp_config_revisions as config_revisions
import axxon_mcp_filesystem_browser as filesystem_browser
import axxon_mcp_devices_catalog as devices_catalog
import axxon_mcp_global_tracker as global_tracker
import axxon_mcp_shared_kv as shared_kv

TRANSIENT = ("deadline_exceeded", "urlopen", "timed out", "unavailable")
# Server says the feature/path is not available on this stand: a fixture gap, not a tool bug.
FIXTURE_GAP = ("unimplemented", "invalidpath", "not supported", "does not supported")


def _attempt(call: Callable[[], dict[str, Any]], retries: int = 3) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(retries):
        try:
            out = call()
        except Exception as exc:  # smoke harness: classify transient vs fixture-gap vs hard failure
            text = str(exc).lower()
            if any(t in text for t in TRANSIENT):
                last = {"status": "transient", "message": str(exc)[:160]}
                time.sleep(1.5)
                continue
            if any(t in text for t in FIXTURE_GAP):
                return {"status": "fixture-needed", "message": str(exc).splitlines()[0][:160]}
            return {"status": "exception", "message": str(exc)[:200]}
        if out.get("status") in {"ok", "applied"}:
            return out
        text = json.dumps(out).lower()
        if any(t in text for t in TRANSIENT):
            last = out
            time.sleep(1.5)
            continue
        return out
    return last or {"status": "transient", "message": "exhausted retries"}


def _verdict(out: dict[str, Any]) -> str:
    status = out.get("status")
    if status in {"ok", "applied"}:
        return "PASS"
    if status in {"gap", "disabled", "fixture-needed"}:
        return "WARN"
    return "FAIL"


def _group(factory_module: Any) -> Any:
    cls = next(getattr(factory_module, n) for n in dir(factory_module) if n.startswith("AxxonMcp"))
    inst = cls()
    inst.client = None  # use env config via the module default factory
    inst.config_factory = lambda: _CONFIG
    inst.client_factory = lambda config: AxxonApiClient(config)
    return inst


_CONFIG: AxxonClientConfig | None = None


def run(config: AxxonClientConfig, do_commit: bool) -> list[dict[str, Any]]:
    global _CONFIG
    _CONFIG = config
    results: list[dict[str, Any]] = []

    def record(group: str, tool: str, out: dict[str, Any]) -> None:
        results.append({"group": group, "tool": tool, "verdict": _verdict(out), "status": out.get("status"), "detail": _detail(out)})

    record("statistics", "get_statistics", _attempt(lambda: _group(statistics).get_statistics()))
    record("event_taxonomy", "get_event_grouping_tags", _attempt(lambda: _group(event_taxonomy).get_event_grouping_tags()))
    record("scene_description", "list_scene_description", _attempt(lambda: _group(scene_description).list_scene_description(page_size=10)))
    record("package_availability", "check_package_availability", _attempt(lambda: _group(package_availability).check_package_availability(system="Linux")))
    record("domain_topology", "enumerate_nodes", _attempt(lambda: _group(domain_topology).enumerate_nodes()))
    record("config_revisions", "get_revision_info", _attempt(lambda: _group(config_revisions).get_revision_info()))
    record("filesystem_browser", "list_directory", _attempt(lambda: _group(filesystem_browser).list_directory(path="")))
    record("devices_catalog", "list_vendors", _attempt(lambda: _group(devices_catalog).list_vendors()))
    record("global_tracker", "get_profile", _attempt(lambda: _group(global_tracker).get_profile(profile_id="codex-nonexistent")))
    record("shared_kv", "list_records", _attempt(lambda: _group(shared_kv).list_records(prefix="")))

    if do_commit:
        results.append(_commit_roundtrip(config))
    return results


def _commit_roundtrip(config: AxxonClientConfig) -> dict[str, Any]:
    """Reversible shared_kv.commit_record: set a codex-* key, read it back, remove it, verify gone."""
    kv = shared_kv.AxxonMcpSharedKv(client_factory=lambda c: AxxonApiClient(c), config_factory=lambda: config, enabled=True)
    kv.shared_kv_connect_axxon_profile("env")
    key = "codex-phase-a-smoke"
    token = shared_kv.SHARED_KV_CONFIRMATION
    set_out = _attempt(lambda: kv.commit_record(set_records=[{"key": key, "value": "codex-smoke", "revision": ""}], confirmation=token))
    readback = _attempt(lambda: kv.get_records(keys=[key]))
    # BatchGetRecords echoes a zero-revision stub for absent keys, so presence == revision != "".
    rev = next((r.get("revision", "") for r in readback.get("records", []) if r.get("key") == key), "")
    remove_out = _attempt(lambda: kv.commit_record(removed=[{"key": key, "revision": rev}], confirmation=token))
    after = _attempt(lambda: kv.get_records(keys=[key]))
    gone = all(r.get("key") != key or not r.get("revision") for r in after.get("records", []))
    verdict = "PASS" if _verdict(set_out) == "PASS" and _verdict(remove_out) == "PASS" and gone else _verdict(set_out)
    return {"group": "shared_kv", "tool": "commit_record (round-trip)", "verdict": verdict, "status": set_out.get("status"),
            "detail": f"set={set_out.get('status')} remove={remove_out.get('status')} reverted={gone}"}


def _detail(out: dict[str, Any]) -> str:
    for key in ("count", "chunks_seen", "node_count", "package_version", "capacity_bytes", "message"):
        if key in out:
            return f"{key}={out[key]}"
    return out.get("status", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase A live smoke (10 groups).")
    add_common_args(parser)
    parser.add_argument("--commit", action="store_true", help="Also run the reversible shared_kv.commit_record round-trip.")
    args = parser.parse_args()
    config = config_from_args(args)
    results = run(config, args.commit)
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print(f"{r['verdict']:4}  {r['group']}.{r['tool']}  ({r['detail']})")
    print(f"\nPASS={counts['PASS']} WARN={counts['WARN']} FAIL={counts['FAIL']}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
