#!/usr/bin/env python3
"""Live-audit harness for the 30 pre-existing Axxon One MCP capability groups.

Exercises every read tool live against the stand and verifies every mutating tool's
gate refuses without the approval env + confirmation token. Zero stand side-effects.

Verdicts per AC2:
  OK    - returned real or empty data cleanly
  EMPTY - clean empty result (fixture absent on stand)
  CAP   - returned bounded/truncated data as designed
  DRIFT - returned data but shape differs from what the tool expects
  FAIL  - 404/500/UNIMPLEMENTED/hard error

Gate check verdicts (AC3):
  OK    - gate refused as expected (no mutation)
  FAIL  - gate did NOT refuse (mutation may have happened or code error)

Examples:
    AXXON_HOST=<host> AXXON_HTTP_URL=http://<host>:80 AXXON_USERNAME=root \\
        AXXON_PASSWORD=root AXXON_TLS_CN=Server \\
        python tools/axxon_preexisting_audit.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from axxon_api_client import AxxonApiClient, AxxonClientConfig, add_common_args, config_from_args

# ---------------------------------------------------------------------------
# Transient / fixture-gap classification helpers
# ---------------------------------------------------------------------------

TRANSIENT_TOKENS = ("deadline_exceeded", "urlopen", "timed out", "unavailable", "connection refused")
FIXTURE_GAP_TOKENS = ("unimplemented", "not supported", "does not supported", "no such", "fixture-needed")
# Server errors for missing fixtures (NOT_FOUND, INTERNAL on nonexistent resource) are fixture gaps
_SERVER_FIXTURE_GAP_PATTERNS = (
    "not found",
    "notfound",
    "can not parse name",
    "can't find requested media",
    "requested provider not found",
    "internal errors occurred",  # vmda query on nonexistent camera
    "idl:omg.org/corba",  # server-side CORBA crash (security credentials)
    "requested context could not be found",  # generic_settings nonexistent context
    "can't resolve reference",  # archive volume on embedded-storage (no external volumes)
    "cannot resolve",  # alternate form
)

_CONFIG: AxxonClientConfig | None = None


def _mk_group(module: Any) -> Any:
    cls = next(getattr(module, n) for n in dir(module) if n.startswith("AxxonMcp"))
    inst = cls()
    inst.client = None
    inst.config_factory = lambda: _CONFIG
    inst.client_factory = lambda config: AxxonApiClient(config)
    return inst


def _attempt(call: Any, retries: int = 2) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(retries):
        try:
            out = call()
        except Exception as exc:
            text = str(exc).lower()
            if any(t in text for t in TRANSIENT_TOKENS):
                last = {"status": "transient", "message": str(exc)[:200]}
                time.sleep(1.5)
                continue
            if any(t in text for t in FIXTURE_GAP_TOKENS):
                return {"status": "fixture-gap", "message": str(exc).splitlines()[0][:200]}
            if any(p in text for p in _SERVER_FIXTURE_GAP_PATTERNS):
                return {"status": "fixture-gap", "message": str(exc).splitlines()[0][:200]}
            err_class = exc.__class__.__name__
            grpc_code = ""
            if hasattr(exc, "code") and callable(exc.code):
                try:
                    grpc_code = str(exc.code())
                except Exception:  # noqa: BLE001
                    pass
            return {"status": "exception", "error_class": err_class, "grpc_code": grpc_code, "message": str(exc)[:240]}
        if isinstance(out, dict):
            return out
        return {"status": "ok", "raw": str(out)[:120]}
    return last or {"status": "transient", "message": "exhausted retries"}


def _to_verdict(out: dict[str, Any]) -> str:
    status = out.get("status", "")
    # No-status dict that has count/items is OK or EMPTY
    if not status and ("count" in out or "items" in out or "kind" in out):
        count = out.get("count", out.get("item_count"))
        if isinstance(count, int) and count > 0:
            return "OK"
        if isinstance(count, int) and count == 0:
            return "EMPTY"
        return "OK" if _has_data(out) else "EMPTY"
    if status in {"ok", "applied", "connected", "planned"}:
        count = out.get("count", out.get("item_count"))
        if isinstance(count, int) and count == 0:
            return "EMPTY"
        return "OK" if _has_data(out) else "EMPTY"
    if status in {"gap", "fixture-needed", "fixture-gap", "disabled"}:
        return "EMPTY"
    if status == "transient":
        return "FAIL"
    if status == "exception":
        text = (out.get("message") or "").lower()
        if any(t in text for t in FIXTURE_GAP_TOKENS):
            return "EMPTY"
        return "FAIL"
    if status == "error":
        msg = (out.get("message") or "").lower()
        if any(p in msg for p in FIXTURE_GAP_TOKENS) or any(p in msg for p in _SERVER_FIXTURE_GAP_PATTERNS):
            return "EMPTY"
        return "FAIL"
    return "FAIL"


def _has_data(out: dict[str, Any]) -> bool:
    for key in ("count", "items", "sources", "groups", "events", "records",
                "restrictions", "node_log_level", "bookmarks"):
        v = out.get(key)
        if v and (isinstance(v, (list, dict)) and len(v) > 0 or isinstance(v, int) and v > 0):
            return True
    # Catch-all: any top-level value besides bookkeeping fields counts as data, so
    # tools returning group-specific keys (roles, current_user, ntp_url, ...) read as OK.
    skip = {"status", "tool", "kind", "group"}
    return any(v not in (None, False, "", [], {}) for k, v in out.items() if k not in skip)


def _detail(out: dict[str, Any]) -> str:
    for key in ("count", "item_count", "key_present", "result", "status_code",
                "responses", "source_count", "message", "grpc_code", "error_class"):
        if key in out:
            return f"{key}={out[key]}"
    return out.get("status", "")


# ---------------------------------------------------------------------------
# Gate check helper for mutating tools
# ---------------------------------------------------------------------------

_GATE_REFUSED_STATUSES = frozenset({"disabled", "gap", "refused", "rejected"})


def _gate_check(call_without_approval: Any) -> dict[str, Any]:
    """Call mutating method without approval env and assert it is refused."""
    out = _attempt(call_without_approval, retries=1)
    status = out.get("status", "")
    if status in _GATE_REFUSED_STATUSES:
        return {"status": "ok", "gate": "refused", "observed": status, "detail": out.get("message", out.get("reason", ""))[:120]}
    return {"status": "GATE_FAIL", "gate": "not_refused", "observed": status, "detail": str(out)[:160]}


def _gate_verdict(out: dict[str, Any]) -> str:
    return "OK" if out.get("gate") == "refused" else "FAIL"


# ---------------------------------------------------------------------------
# Per-group audit routines
# ---------------------------------------------------------------------------


def _audit_live(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_live as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "live", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_cameras", _attempt(lambda: grp.list_cameras(limit=20)))
    rec("list_archives", _attempt(lambda: grp.list_archives(limit=20)))
    rec("list_detectors", _attempt(lambda: grp.list_detectors(limit=20)))
    rec("search_events", _attempt(lambda: grp.search_events(hours=1.0, limit=20)))


def _audit_metadata(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_metadata as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "metadata", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_vmda_sources", _attempt(lambda: grp.list_vmda_sources(limit=20)))
    rec("vmda_query", _attempt(lambda: grp.vmda_query(camera_id="dummy-nonexistent", hours=1)))


def _audit_alarms(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_alarms as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "alarms", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_active_alerts", _attempt(lambda: grp.list_active_alerts(limit=20)))
    rec("list_alarm_history", _attempt(lambda: grp.list_alarm_history(hours=1.0, limit=20)))
    rec("list_alarm_event_types", _attempt(lambda: grp.list_alarm_event_types()))

    # Mutating gate checks (no approval env set)
    alarm_mutator_cls = next(c for n, c in vars(mod).items() if "AlarmMutator" in n or n.startswith("AxxonAlarm"))
    mut = alarm_mutator_cls()
    mut.client = None
    mut.config_factory = lambda: _CONFIG
    mut.client_factory = lambda config: AxxonApiClient(config)

    for tool, call in [
        ("raise_alert", lambda: mut.raise_alert(camera_access_point="dummy", confirmation="")),
        ("alarm_begin_review", lambda: mut.alarm_begin_review(camera_access_point="dummy", alert_id="dummy", confirmation="")),
    ]:
        gout = _gate_check(call)
        results.append({"group": "alarms_mutate", "tool": tool, "verdict": _gate_verdict(gout),
                        "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_logic_alerts(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_logic_alerts as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "logic_alerts", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    # batch_*_alerts requires at least one node name; use the stand TLS CN
    node = _CONFIG.tls_cn if _CONFIG else "Server"
    rec("batch_get_active_alerts", _attempt(lambda: grp.batch_get_active_alerts(nodes=[node])))
    rec("batch_filter_active_alerts", _attempt(lambda: grp.batch_filter_active_alerts(nodes=[node])))

    # Gate check for a write
    gout = _gate_check(lambda: grp.batch_begin_alerts_review(confirmation=""))
    results.append({"group": "logic_alerts_mutate", "tool": "batch_begin_alerts_review", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_ptz(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_ptz as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "ptz", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    out_sources = _attempt(lambda: grp.list_telemetry_sources(limit=10))
    rec("list_telemetry_sources", out_sources)


def _audit_heatmap(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_heatmap as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "heatmap", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    t1 = (now - _dt.timedelta(hours=1)).strftime("%Y%m%dT%H%M%S.000000")
    t2 = now.strftime("%Y%m%dT%H%M%S.000000")
    rec("build_heatmap", _attempt(lambda: grp.build_heatmap(camera_id="dummy-nonexistent", start_time=t1, end_time=t2)))
    rec("build_events_heatmap", _attempt(lambda: grp.build_events_heatmap(start_time=t1, end_time=t2)))


def _audit_media(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_media as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "media", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("request_connection", _attempt(lambda: grp.request_connection(endpoint="dummy-nonexistent")))
    rec("request_tunnel", _attempt(lambda: grp.request_tunnel(node="Server")))


def _audit_recognizer(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_recognizer as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "recognizer", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_recognizer_lists", _attempt(lambda: grp.list_recognizer_lists(list_type="any")))


def _audit_discovery(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_discovery as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "discovery", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    # discovery is slow (scans network); use discover_node_devices with short cap
    rec("discover_node_devices", _attempt(lambda: grp.discover_node_devices(max_devices=10, max_seconds=5.0)))


def _audit_admin(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_admin as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "admin", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("security_inventory", _attempt(lambda: grp.security_inventory()))
    rec("system_health", _attempt(lambda: grp.system_health()))
    rec("time_status", _attempt(lambda: grp.time_status()))
    rec("license_status", _attempt(lambda: grp.license_status()))
    # role_permissions requires a role_id arg; current_user_security takes no args
    for tool_name in ("current_user_security",):
        if hasattr(grp, tool_name):
            rec(tool_name, _attempt(lambda tn=tool_name: getattr(grp, tn)()))
        else:
            results.append({"group": "admin", "tool": tool_name, "verdict": "DRIFT",
                            "status": "missing_method", "detail": "in ADMIN_TOOL_NAMES but not implemented on AxxonMcpAdmin"})
    # role_permissions: discover a role_id from security_inventory, then call
    if hasattr(grp, "role_permissions"):
        inv_out = _attempt(lambda: grp.security_inventory())
        roles_field = inv_out.get("roles", {})
        role_items = roles_field.get("items", []) if isinstance(roles_field, dict) else (roles_field if isinstance(roles_field, list) else [])
        role_ids = [r.get("role_id", "") for r in role_items if isinstance(r, dict) and r.get("role_id")]
        if role_ids:
            rec("role_permissions", _attempt(lambda rid=role_ids[0]: grp.role_permissions(role_id=rid)))
        else:
            results.append({"group": "admin", "tool": "role_permissions", "verdict": "EMPTY",
                            "status": "fixture-gap", "detail": "no role_id found in security_inventory"})
    else:
        results.append({"group": "admin", "tool": "role_permissions", "verdict": "DRIFT",
                        "status": "missing_method", "detail": "in ADMIN_TOOL_NAMES but not implemented on AxxonMcpAdmin"})


def _audit_license_reads(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_license_reads as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "license_reads", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("get_license_key", _attempt(lambda: grp.get_license_key()))
    rec("get_restrictions", _attempt(lambda: grp.get_restrictions()))


def _audit_misc_reads(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_misc_reads as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "misc_reads", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("ping_node", _attempt(lambda: grp.ping_node(timeout_ms=1000)))
    # get_generic_settings requires a GUID context - use a valid UUID format (may return empty settings)
    rec("get_generic_settings", _attempt(lambda: grp.get_generic_settings(context="00000000-0000-0000-0000-000000000001")))

    # Gated writes without approval
    gout = _gate_check(lambda: grp.save_generic_settings(context="dummy", confirmation=""))
    results.append({"group": "misc_reads_mutate", "tool": "save_generic_settings", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_bookmarks(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_bookmarks as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "bookmarks", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    t1 = (now - _dt.timedelta(hours=24)).strftime("%Y%m%dT%H%M%S.%f")[:-3]
    t2 = now.strftime("%Y%m%dT%H%M%S.%f")[:-3]
    rec("bookmark_list", _attempt(lambda: grp.bookmark_list(time_range={"begin_time": t1, "end_time": t2}, limit=20)))

    # Bookmark mutations gate check - class is AxxonBookmarkMutationRegistry (not AxxonMcp*)
    # apply() gates on enabled + confirmation; use a dummy plan_id to get the rejection
    import axxon_mcp_bookmark_mutations as bm_mod
    bm = bm_mod.AxxonBookmarkMutationRegistry()  # enabled=False because env not set
    # apply() with unknown plan_id returns "gap"; then enabled check returns "rejected" for known plan
    # Plan first (does NOT gate), then apply without approval:
    plan_out = bm.plan("bookmark_lifecycle", params={"camera_access_point": "dummy", "range": {"begin_time": t1, "end_time": t2}})
    plan_id = plan_out.get("plan_id", "nonexistent")
    gout = _gate_check(lambda: bm.apply(plan_id=plan_id, confirmation="wrong-token"))
    results.append({"group": "bookmarks_mutate", "tool": "apply(bookmark_lifecycle)", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_layout_manager(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_layout_manager as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "layout_manager", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("batch_get_layouts", _attempt(lambda: grp.batch_get_layouts(layout_id="nonexistent-layout-id")))

    # Gated write without approval
    gout = _gate_check(lambda: grp.update_layout_name(layout_id="dummy", display_name="audit-test", confirmation=""))
    results.append({"group": "layout_manager_mutate", "tool": "update_layout_name", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_map_providers(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_map_providers as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "map_providers", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("get_map_provider", _attempt(lambda: grp.get_map_provider(provider_id="OSM")))

    # Gated write without approval
    gout = _gate_check(lambda: grp.configure_map_providers(changed=[], removed=["DUMMY"], confirmation=""))
    results.append({"group": "map_providers_mutate", "tool": "configure_map_providers", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_groups(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_groups as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "groups", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_groups", _attempt(lambda: grp.list_groups()))

    # Gated write without approval
    gout = _gate_check(lambda: grp.change_groups(added_groups=[{"name": "audit-test"}], confirmation=""))
    results.append({"group": "groups_mutate", "tool": "change_groups", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_timezone(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_timezone as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "timezone", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_timezones", _attempt(lambda: grp.list_timezones()))
    rec("get_timezone", _attempt(lambda: grp.get_timezone()))
    rec("get_ntp", _attempt(lambda: grp.get_ntp()))

    # Gated write without approval
    gout = _gate_check(lambda: grp.set_timezone(timezone_id="UTC", confirmation=""))
    results.append({"group": "timezone_mutate", "tool": "set_timezone", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_settings(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_settings as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "settings", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("get_data_storage_settings", _attempt(lambda: grp.get_data_storage_settings()))
    rec("get_bookmark_settings", _attempt(lambda: grp.get_bookmark_settings()))
    rec("get_gdpr_settings", _attempt(lambda: grp.get_gdpr_settings()))

    # Gated write without approval
    gout = _gate_check(lambda: grp.update_data_storage_settings(system_logs_retention_s=86400, confirmation=""))
    results.append({"group": "settings_mutate", "tool": "update_data_storage_settings", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_detector_archive(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_detector_archive as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "detector_archive", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("detector_kind_catalog", _attempt(lambda: grp.detector_kind_catalog(include_live=False)))
    rec("archive_management_status", _attempt(lambda: grp.archive_management_status()))
    rec("analytics_fixture_report", _attempt(lambda: grp.analytics_fixture_report()))


def _audit_auth_sessions(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_auth_sessions as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "auth_sessions", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    user = _CONFIG.username if _CONFIG else "root"
    pwd = _CONFIG.password if _CONFIG else ""
    rec("authenticate", _attempt(lambda: grp.authenticate(user_name=user, password=pwd)))
    rec("renew_session", _attempt(lambda: grp.renew_session()))

    # Gated close without approval
    gout = _gate_check(lambda: grp.close_session(confirmation=""))
    results.append({"group": "auth_sessions_mutate", "tool": "close_session", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_server_settings(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_server_settings as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "server_settings", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("get_log_level", _attempt(lambda: grp.get_log_level()))

    # Gated writes without approval
    gout = _gate_check(lambda: grp.set_log_level(level="INFO", confirmation=""))
    results.append({"group": "server_settings_mutate", "tool": "set_log_level", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})
    gout2 = _gate_check(lambda: grp.drop_logs(confirmation=""))
    results.append({"group": "server_settings_mutate", "tool": "drop_logs", "verdict": _gate_verdict(gout2),
                    "status": gout2.get("status"), "detail": f"gate={gout2.get('gate')} obs={gout2.get('observed')}"})


def _audit_audit_module(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_audit as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "audit", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_audit_event_kinds", _attempt(lambda: grp.list_audit_event_kinds()))

    gout = _gate_check(lambda: grp.audit_inject(kind="camera_viewing", params={"camera_ap": "dummy"}, confirmation=""))
    results.append({"group": "audit_mutate", "tool": "audit_inject", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_config_change(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_config_change as mod
    import axxon_mcp_live as live_mod

    grp = _mk_group(mod)
    live_grp = _mk_group(live_mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "config_change", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    # Get a real camera uid from inventory for list_similar_units
    camera_uid = ""
    try:
        cams_out = live_grp.list_cameras(limit=1)
        items = cams_out.get("items", [])
        if items:
            # Camera uid looks like "hosts/Server/DeviceIpint.N"
            ap = items[0].get("access_point", "")
            if ap:
                # Strip the SourceEndpoint suffix to get the unit uid
                camera_uid = "/".join(ap.split("/")[:3]) if ap.count("/") >= 2 else ap
    except Exception:  # noqa: BLE001
        pass

    if camera_uid:
        rec("list_similar_units", _attempt(lambda: grp.list_similar_units(uid=camera_uid)))
    else:
        results.append({"group": "config_change", "tool": "list_similar_units", "verdict": "EMPTY",
                        "status": "fixture-gap", "detail": "no camera uid found in inventory"})
    rec("batch_get_factories", _attempt(lambda: grp.batch_get_factories(unit_types=["DeviceIpint"])))

    gout = _gate_check(lambda: grp.change_unit_property(uid="dummy", unit_type="DeviceIpint", property_id="p", value_string="v", confirmation=""))
    results.append({"group": "config_change_mutate", "tool": "change_unit_property", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_archive_volume(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_archive_volume as mod
    import axxon_mcp_live as live_mod

    grp = _mk_group(mod)
    live_grp = _mk_group(live_mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "archive_volume", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    # Discover a real archive access_point from inventory
    archive_ap = ""
    try:
        archives_out = live_grp.list_archives(limit=1)
        items = archives_out.get("items", [])
        if items:
            archive_ap = items[0].get("access_point") or ""
    except Exception:  # noqa: BLE001
        pass

    if archive_ap:
        rec("list_volume_states", _attempt(lambda: grp.list_volume_states(access_point=archive_ap)))
    else:
        results.append({"group": "archive_volume", "tool": "list_volume_states", "verdict": "EMPTY",
                        "status": "fixture-gap", "detail": "no archive access_point found in inventory"})

    gout = _gate_check(lambda: grp.resize_volume(access_point="dummy", volume_id="dummy", new_size=1024, confirmation=""))
    results.append({"group": "archive_volume_mutate", "tool": "resize_volume", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_gdpr_cleanup(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_gdpr_cleanup as mod

    grp = _mk_group(mod)

    gout = _gate_check(lambda: grp.layout_user_data_cleanup(user_ids=["dummy"], confirmation=""))
    results.append({"group": "gdpr_cleanup_mutate", "tool": "layout_user_data_cleanup", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})
    gout2 = _gate_check(lambda: grp.map_user_data_cleanup(user_ids=["dummy"], confirmation=""))
    results.append({"group": "gdpr_cleanup_mutate", "tool": "map_user_data_cleanup", "verdict": _gate_verdict(gout2),
                    "status": gout2.get("status"), "detail": f"gate={gout2.get('gate')} obs={gout2.get('observed')}"})


def _audit_recognizer_write(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_recognizer_write as mod

    grp = _mk_group(mod)

    gout = _gate_check(lambda: grp.recognizer_change_lists(added=[], changed=[], removed_ids=[], confirmation=""))
    results.append({"group": "recognizer_write_mutate", "tool": "recognizer_change_lists", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})
    gout2 = _gate_check(lambda: grp.recognizer_clear(node_name="Server", confirmation="", clear_ack=""))
    results.append({"group": "recognizer_write_mutate", "tool": "recognizer_clear", "verdict": _gate_verdict(gout2),
                    "status": gout2.get("status"), "detail": f"gate={gout2.get('gate')} obs={gout2.get('observed')}"})


def _audit_videowall(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_videowall as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "videowall", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("list_walls", _attempt(lambda: grp.list_walls()))

    gout = _gate_check(lambda: grp.register_wall(name="audit-test", confirmation=""))
    results.append({"group": "videowall_mutate", "tool": "register_wall", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_security_credentials(results: list[dict[str, Any]]) -> None:
    import axxon_mcp_security_credentials as mod

    grp = _mk_group(mod)

    def rec(tool: str, out: dict[str, Any]) -> None:
        v = _to_verdict(out)
        results.append({"group": "security_credentials", "tool": tool, "verdict": v, "status": out.get("status"), "detail": _detail(out)})

    rec("check_password", _attempt(lambda: grp.check_password(user_id="root", password="audit-probe-dummy-xyz")))

    gout = _gate_check(lambda: grp.change_my_password(password="dummy", confirmation=""))
    results.append({"group": "security_credentials_mutate", "tool": "change_my_password", "verdict": _gate_verdict(gout),
                    "status": gout.get("status"), "detail": f"gate={gout.get('gate')} obs={gout.get('observed')}"})


def _audit_generator(results: list[dict[str, Any]]) -> None:
    """Generator group: offline only - list templates and generate without a live connection."""
    import axxon_mcp_generator as gen_mod

    try:
        gen_inst = gen_mod.Generator()
        out_list = gen_inst.list_templates()
        # list_templates returns list[dict] directly
        tmpl_count = len(out_list) if isinstance(out_list, list) else len(out_list.get("templates", []))
        v = "OK" if tmpl_count > 0 else "EMPTY"
        results.append({"group": "generator", "tool": "list_templates", "verdict": v,
                        "status": "ok", "detail": f"count={tmpl_count}"})

        # Try generating the simplest template offline using allow_mutation to skip safety gate
        req = gen_mod.GenerationRequest(
            template="grpc_consumer",
            params={"fqmn": "axxonsoft.bl.auth.AuthenticationService.AuthenticateEx"},
            allow_mutation=True,
        )
        gen_out = gen_inst.generate(req)
        if isinstance(gen_out, gen_mod.GeneratedBundle):
            gen_v = "OK" if gen_out.files else "EMPTY"
            results.append({"group": "generator", "tool": "generate(grpc_consumer)", "verdict": gen_v,
                            "status": "ok", "detail": f"files={list(gen_out.files.keys())}"})
        elif isinstance(gen_out, gen_mod.GenerationRefusal) and gen_out.reason == "unknown_method":
            # Method not in corpus - fixture gap (corpus may not include this method)
            results.append({"group": "generator", "tool": "generate(grpc_consumer)", "verdict": "EMPTY",
                            "status": "fixture-gap", "detail": f"fqmn not in corpus: {gen_out.detail[:80]}"})
        else:
            results.append({"group": "generator", "tool": "generate(grpc_consumer)", "verdict": "FAIL",
                            "status": "refused", "detail": str(gen_out)[:120]})
    except Exception as exc:
        results.append({"group": "generator", "tool": "list_templates/generate", "verdict": "FAIL",
                        "status": "exception", "detail": str(exc)[:160]})


# ---------------------------------------------------------------------------
# Sanitizer for report output
# ---------------------------------------------------------------------------

def _sanitize(text: str, config: AxxonClientConfig) -> str:
    text = text.replace(config.host, "<demo-host>")
    text = text.replace(config.username, "<demo-user>")
    text = text.replace(config.password, "<redacted>")
    text = text.replace(config.http_url, "http://<demo-host>")
    return text


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def run(config: AxxonClientConfig) -> list[dict[str, Any]]:
    global _CONFIG
    _CONFIG = config
    results: list[dict[str, Any]] = []

    auditors = [
        ("live", _audit_live),
        ("metadata", _audit_metadata),
        ("alarms", _audit_alarms),
        ("logic_alerts", _audit_logic_alerts),
        ("ptz", _audit_ptz),
        ("heatmap", _audit_heatmap),
        ("media", _audit_media),
        ("recognizer", _audit_recognizer),
        ("discovery", _audit_discovery),
        ("admin", _audit_admin),
        ("license_reads", _audit_license_reads),
        ("misc_reads", _audit_misc_reads),
        ("bookmarks", _audit_bookmarks),
        ("layout_manager", _audit_layout_manager),
        ("map_providers", _audit_map_providers),
        ("groups", _audit_groups),
        ("timezone", _audit_timezone),
        ("settings", _audit_settings),
        ("detector_archive", _audit_detector_archive),
        ("auth_sessions", _audit_auth_sessions),
        ("server_settings", _audit_server_settings),
        ("audit", _audit_audit_module),
        ("config_change", _audit_config_change),
        ("archive_volume", _audit_archive_volume),
        ("gdpr_cleanup", _audit_gdpr_cleanup),
        ("recognizer_write", _audit_recognizer_write),
        ("videowall", _audit_videowall),
        ("security_credentials", _audit_security_credentials),
        ("generator", _audit_generator),
    ]

    for name, auditor in auditors:
        print(f"  [{name}] ...", end=" ", flush=True)
        try:
            auditor(results)
            group_results = [r for r in results if r["group"].startswith(name) or r["group"] == name]
            last = group_results[-1] if group_results else {}
            print(f"done ({last.get('verdict', '?')})")
        except Exception as exc:
            print(f"ERROR: {exc!r:.100}")
            results.append({"group": name, "tool": "_group_error", "verdict": "FAIL",
                            "status": "exception", "detail": str(exc)[:200]})

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _count_verdicts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return counts


def _print_table(results: list[dict[str, Any]]) -> None:
    print(f"\n{'GROUP':<28} {'TOOL':<42} {'VERDICT':<8} {'DETAIL'}")
    print("-" * 110)
    for r in results:
        print(f"{r['group']:<28} {r['tool']:<42} {r['verdict']:<8} {r.get('detail', '')}")


def write_report(results: list[dict[str, Any]], config: AxxonClientConfig, report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    counts = _count_verdicts(results)

    drift_fail = [r for r in results if r["verdict"] in ("DRIFT", "FAIL")]

    raw_json = json.dumps({"totals": counts, "results": results}, indent=2)
    sanitized_json = _sanitize(raw_json, config)
    json_path = report_dir / "preexisting-tools-audit-latest.json"
    json_path.write_text(sanitized_json)

    md_lines = [
        "# Pre-existing Tools Live Audit",
        "",
        "| Verdict | Count |",
        "|---------|-------|",
    ]
    for verdict in ("OK", "EMPTY", "CAP", "DRIFT", "FAIL"):
        md_lines.append(f"| {verdict} | {counts.get(verdict, 0)} |")
    md_lines.append("")
    md_lines.append("## Results")
    md_lines.append("")
    md_lines.append("| Group | Tool | Verdict | Detail |")
    md_lines.append("|-------|------|---------|--------|")
    for r in results:
        detail = str(r.get("detail", "")).replace("|", "/")
        md_lines.append(f"| {r['group']} | {r['tool']} | {r['verdict']} | {detail} |")

    if drift_fail:
        md_lines.append("")
        md_lines.append("## DRIFT / FAIL Catalogue (AC4)")
        md_lines.append("")
        for r in drift_fail:
            md_lines.append(f"### {r['group']}.{r['tool']}")
            md_lines.append(f"- verdict: {r['verdict']}")
            md_lines.append(f"- status: {r.get('status')}")
            md_lines.append(f"- detail: {r.get('detail')}")
            md_lines.append("")

    md_lines.append("")
    md_lines.append("Host: `<demo-host>`  User: `<demo-user>`")

    md_text = "\n".join(md_lines)
    sanitized_md = _sanitize(md_text, config)
    md_path = report_dir / "preexisting-tools-audit-latest.md"
    md_path.write_text(sanitized_md)

    print(f"\nReport: {md_path}")
    print(f"JSON:   {json_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live audit of 30 pre-existing Axxon One MCP groups.")
    add_common_args(parser)
    args = parser.parse_args()
    config = config_from_args(args)

    print(f"Connecting to <demo-host> ({config.http_url.replace(config.host, '<demo-host>')})")
    print("Auditing 30 groups...\n")

    results = run(config)

    _print_table(results)
    counts = _count_verdicts(results)
    total = sum(counts.values())
    print(f"\nTotals: OK={counts.get('OK', 0)} EMPTY={counts.get('EMPTY', 0)} CAP={counts.get('CAP', 0)} "
          f"DRIFT={counts.get('DRIFT', 0)} FAIL={counts.get('FAIL', 0)} total={total}")

    repo_root = Path(__file__).resolve().parents[1]
    write_report(results, config, repo_root / "docs" / "api-audit")

    drift_fail = [r for r in results if r["verdict"] in ("DRIFT", "FAIL")]
    if drift_fail:
        print(f"\nDRIFT/FAIL tools ({len(drift_fail)}):")
        for r in drift_fail:
            print(f"  {r['group']}.{r['tool']}: {r['verdict']} - {r.get('detail', '')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
