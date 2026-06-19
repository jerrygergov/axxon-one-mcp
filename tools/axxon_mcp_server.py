#!/usr/bin/env python3
"""FastMCP server for the Axxon One API knowledge and integration tools."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Callable

from axxon_mcp_docs import AxxonMcpDocs, DEFAULT_CORPUS_DIR


CORPUS_FILE_ALLOWLIST = {
    "api_methods.json",
    "http_endpoints.json",
    "task_recipes.json",
    "fixtures.json",
    "safety_policies.json",
    "known_behaviors.json",
}

# Capability groups surfaced by list_capabilities so the assistant can self-discover what this
# server can do and which flag to ask the user for when a needed capability is currently disabled.
# Each entry: create_server param -> (description, example tools, --enable flag).
CAPABILITY_GROUPS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "live": ("Live read-only inspection of a connected server", ("list_cameras", "list_archives", "search_events"), "--enable-live"),
    "operator": ("Create/modify/delete config (cameras, detectors, layouts, macros) via plan/apply/verify/rollback", ("list_operator_workflows", "plan_operator_workflow", "apply_operator_plan"), "--enable-operator"),
    "metadata": ("Metadata / VMDA object-track search", ("list_vmda_sources", "live_track_sample", "vmda_query"), "--enable-metadata"),
    "view": ("Live + archive viewing (URLs, byte/time capped)", ("live_view", "archive_scrub", "stream_health"), "--enable-view"),
    "view_objects": ("Layouts, maps, markers, walls (reads)", ("list_layouts", "list_maps", "get_markers"), "--enable-view-objects"),
    "alarms": ("Alarm reads + raise + review lifecycle", ("list_active_alerts", "raise_alert", "alarm_subscribe"), "--enable-alarms"),
    "logic_alerts": ("Batch alert reads/reviews across nodes", ("batch_get_active_alerts", "batch_begin_alerts_review"), "--enable-logic-alerts"),
    "logic_control": ("Macros, arm-state, config/counters (LogicService)", ("launch_macro", "change_arm_state", "change_counters"), "--enable-logic-control"),
    "ptz": ("PTZ / telemetry control", ("list_telemetry_sources", "ptz_absolute_move", "list_presets"), "--enable-ptz"),
    "heatmap": ("HeatMap image + query tools (metadata only)", ("build_heatmap", "execute_heatmap_query"), "--enable-heatmap"),
    "media": ("Media transport probes (metadata only)", ("request_connection", "stream_probe", "connect_endpoint"), "--enable-media"),
    "export": ("ExportService snapshots, capped downloads, and owned-session cleanup", ("export_start_snapshot", "export_download", "export_cleanup_owned"), "--enable-export"),
    "recognizer": ("RealtimeRecognizer reads", ("list_recognizers", "get_recognizer_lists"), "--enable-recognizer"),
    "recognizer_write": ("RealtimeRecognizer list writes", ("update_recognizer_list",), "--enable-recognizer-write"),
    "discovery": ("DiscoveryService network device discovery", ("discover_devices",), "--enable-discovery"),
    "admin": ("Security/system-health/notifier reads", ("security_inventory", "license_status", "domain_event_subscribe"), "--enable-admin"),
    "license_reads": ("LicenseService reads (key + restrictions)", ("get_license_key", "list_license_restrictions"), "--enable-license-reads"),
    "misc_reads": ("Cross-service batch reads", ("acquire_dynamic_parameters", "acquire_device_additional_data"), "--enable-misc-reads"),
    "bookmarks": ("BookmarkService reads + lifecycle", ("list_bookmarks", "create_bookmark"), "--enable-bookmarks"),
    "layout_manager": ("LayoutManager reads + rename", ("batch_get_layouts", "update_layout_name"), "--enable-layout-manager"),
    "map_providers": ("Map provider configuration", ("list_map_providers", "configure_map_providers"), "--enable-map-providers"),
    "groups": ("Camera/device group management", ("list_groups", "create_group"), "--enable-groups"),
    "timezone": ("Timezone + NTP settings", ("get_timezones", "set_timezone", "set_ntp"), "--enable-timezone"),
    "settings": ("Data-storage settings (retention/cleanup)", ("get_data_storage_settings", "update_data_storage_settings"), "--enable-settings"),
    "audit": ("AuditEventInjector", ("audit_inject",), "--enable-audit"),
    "videowall": ("VideowallService control (register/change/unregister)", ("videowall_list_walls", "register_wall", "unregister_wall"), "--enable-videowall"),
    "generator": ("Generate Python/Node integration skeletons", ("list_integration_templates", "generate_integration"), "--enable-generator"),
    "partner": ("Partner plugin SDK scaffolds", ("scaffold_plugin", "plugin_lint", "plugin_package"), "--enable-partner"),
    "translator": ("Natural-language -> operator recipe translator", ("assemble_recipe", "validate_recipe"), "--enable-translator"),
    "detector_archive": ("Detector schemas + archive policy reads", ("detector_schema_catalog", "archive_policy_get"), "--enable-detector-archive"),
    "detector_playbooks": ("Task-first detector creation/configuration playbooks with gated apply/verify/rollback", ("plan_detector_playbook", "apply_detector_playbook_plan", "list_detector_playbooks"), "--enable-detector-playbooks"),
    "config_change": ("ConfigurationService unit changes", ("apply_unit_change",), "--enable-config-change"),
    "archive_volume": ("ArchiveService volume resize", ("resize_archive_volume",), "--enable-archive-volume"),
    "security_credentials": ("Reversible user credential lifecycle", ("security_user_credential_lifecycle",), "--enable-security-credentials"),
    "auth_sessions": ("AuthenticationService session reads", ("list_auth_sessions",), "--enable-auth-sessions"),
    "gdpr_cleanup": ("GDPR data cleanup", ("gdpr_cleanup_plan",), "--enable-gdpr-cleanup"),
    "control": ("StateControl / device control", ("set_device_state",), "--enable-control"),
    "server_settings": ("Server log-level + settings", ("get_server_loglevel", "set_server_loglevel"), "--enable-server"),
    "statistics": ("Server/stream statistics reads (CPU/disk/FPS/bitrate health)", ("get_statistics",), "--enable-statistics"),
    "event_taxonomy": ("Event grouping tags (event-filter field descriptors)", ("get_event_grouping_tags",), "--enable-event-taxonomy"),
    "scene_description": ("Per-camera scene descriptions (analytics geometry)", ("list_scene_description",), "--enable-scene-description"),
    "package_availability": ("Installer-package availability check", ("check_package_availability",), "--enable-package-availability"),
    "domain_topology": ("Domain + node enumeration (EnumerateNodes)", ("enumerate_nodes",), "--enable-domain-topology"),
    "config_revisions": ("Config revision history + capped backup-collectibility probe", ("get_revision_info", "collect_backup_probe"), "--enable-config-revisions"),
    "filesystem_browser": ("Server-side filesystem browsing (list dir, file info, free space)", ("list_directory", "get_space"), "--enable-filesystem-browser"),
    "devices_catalog": ("Supported-device catalog (vendors, models, traits) for adding cameras", ("list_vendors", "list_devices", "get_device"), "--enable-devices-catalog"),
    "global_tracker": ("Cross-camera tracking profile metadata reads (no images)", ("get_profile",), "--enable-global-tracker"),
    "shared_kv": ("Shared key-value store reads + gated commit (plugin/integration state)", ("list_records", "get_records", "commit_record"), "--enable-shared-kv"),
    "state_control": ("Device state reads + gated SetState (e.g. PTZ patrol controllers)", ("get_current_state", "set_state"), "--enable-state-control"),
    "site_graph": ("Unified read-only site graph for planners and generators", ("build_site_graph",), "--enable-site-graph"),
    "bulk_onboarding": ("Bulk CSV/JSON camera onboarding planner with gated apply/verify/rollback", ("bulk_onboarding_plan", "bulk_onboarding_apply_plan", "bulk_onboarding_verify_plan"), "--enable-bulk-onboarding"),
    "web_api": ("Web server embeddable-component + WebSocket-event helpers (read-only)", ("embeddable_component_url", "web_events_probe", "web_events_sample"), "--enable-web-api"),
    "client_api": ("Client HTTP API preflight + fixture-needed operation catalog (read-only)", ("client_api_preflight", "list_client_api_operations"), "--enable-client-api"),
}


def default_fastmcp_factory(name: str, **kwargs: Any) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "The MCP Python SDK is not installed. Install the MCP dependency with "
            "`python3.12 -m pip install -r tools/requirements-mcp.txt`."
        ) from exc
    return FastMCP(name, **kwargs)


def create_server(
    *,
    docs: AxxonMcpDocs | Any | None = None,
    live: Any | None = None,
    operator: Any | None = None,
    generator: Any | None = None,
    partner: Any | None = None,
    metadata: Any | None = None,
    view: Any | None = None,
    alarms: Any | None = None,
    alarm_mutator: Any | None = None,
    view_objects: Any | None = None,
    detector_archive: Any | None = None,
    detector_playbooks: Any | None = None,
    admin: Any | None = None,
    admin_mutator: Any | None = None,
    bookmarks: Any | None = None,
    bookmark_mutator: Any | None = None,
    translator: Any | None = None,
    ptz: Any | None = None,
    audit: Any | None = None,
    recognizer: Any | None = None,
    recognizer_write: Any | None = None,
    logic_control: Any | None = None,
    settings: Any | None = None,
    timezone: Any | None = None,
    server_settings: Any | None = None,
    statistics: Any | None = None,
    event_taxonomy: Any | None = None,
    scene_description: Any | None = None,
    package_availability: Any | None = None,
    domain_topology: Any | None = None,
    config_revisions: Any | None = None,
    filesystem_browser: Any | None = None,
    devices_catalog: Any | None = None,
    global_tracker: Any | None = None,
    shared_kv: Any | None = None,
    state_control: Any | None = None,
    site_graph: Any | None = None,
    bulk_onboarding: Any | None = None,
    groups: Any | None = None,
    discovery: Any | None = None,
    gdpr_cleanup: Any | None = None,
    control: Any | None = None,
    map_providers: Any | None = None,
    logic_alerts: Any | None = None,
    config_change: Any | None = None,
    archive_volume: Any | None = None,
    bookmark_extras: Any | None = None,
    security_credentials: Any | None = None,
    auth_sessions: Any | None = None,
    layout_manager: Any | None = None,
    license_reads: Any | None = None,
    misc_reads: Any | None = None,
    heatmap: Any | None = None,
    media: Any | None = None,
    export: Any | None = None,
    videowall: Any | None = None,
    web_api: Any | None = None,
    client_api: Any | None = None,
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    fastmcp_factory: Callable[..., Any] = default_fastmcp_factory,
) -> Any:
    docs = docs or AxxonMcpDocs.from_corpus_dir(corpus_dir)
    server = fastmcp_factory("Axxon One MCP", json_response=True)

    @server.tool(name="search_api_docs")
    def search_api_docs(query: str, limit: int = 10) -> dict[str, Any]:
        """Search the verified Axxon One API corpus without connecting to a server."""
        return docs.search_api_docs(query, limit=limit)

    @server.tool(name="get_api_method")
    def get_api_method(fqmn: str) -> dict[str, Any]:
        """Return exact gRPC method details, or a gap if the method is unknown."""
        return docs.get_api_method(fqmn)

    @server.tool(name="get_http_endpoint")
    def get_http_endpoint(path_or_topic: str) -> dict[str, Any]:
        """Return exact HTTP endpoint details, or a gap if the endpoint is unknown."""
        return docs.get_http_endpoint(path_or_topic)

    @server.tool(name="get_verified_example")
    def get_verified_example(topic: str) -> dict[str, Any]:
        """Return a verified behavior/example note and source report for a topic."""
        return docs.get_verified_example(topic)

    @server.tool(name="explain_task_recipe")
    def explain_task_recipe(task: str) -> dict[str, Any]:
        """Explain the recommended API workflow for a natural-language task."""
        return docs.explain_task_recipe(task)

    @server.tool(name="list_remaining_gaps")
    def list_remaining_gaps() -> dict[str, Any]:
        """List current fixture-needed API coverage gaps."""
        return docs.list_remaining_gaps()

    @server.resource("axxon://mcp-corpus/{name}")
    def read_corpus_file(name: str) -> str:
        """Read one sanitized corpus JSON file by name."""
        if name not in CORPUS_FILE_ALLOWLIST:
            return '{"found": false, "status": "gap", "message": "Unknown corpus file."}'
        path = docs.corpus_dir / name
        if not path.exists():
            return '{"found": false, "status": "gap", "message": "Corpus file is missing."}'
        return path.read_text(encoding="utf-8")

    @server.resource("axxon://coverage/gaps")
    def read_remaining_gaps() -> dict[str, Any]:
        """Read the current fixture-needed coverage gap list."""
        return docs.list_remaining_gaps()

    enabled_groups = {name: value is not None for name, value in (
        ("live", live), ("operator", operator), ("generator", generator), ("partner", partner),
        ("metadata", metadata), ("view", view), ("alarms", alarms), ("view_objects", view_objects),
        ("detector_archive", detector_archive), ("detector_playbooks", detector_playbooks), ("admin", admin), ("bookmarks", bookmarks),
        ("translator", translator), ("ptz", ptz), ("audit", audit), ("recognizer", recognizer),
        ("recognizer_write", recognizer_write), ("logic_control", logic_control), ("settings", settings),
        ("timezone", timezone), ("server_settings", server_settings), ("statistics", statistics),
        ("event_taxonomy", event_taxonomy), ("scene_description", scene_description),
        ("package_availability", package_availability), ("domain_topology", domain_topology),
        ("config_revisions", config_revisions), ("filesystem_browser", filesystem_browser),
        ("devices_catalog", devices_catalog), ("global_tracker", global_tracker),
        ("shared_kv", shared_kv), ("state_control", state_control), ("groups", groups),
        ("site_graph", site_graph), ("bulk_onboarding", bulk_onboarding),
        ("discovery", discovery), ("gdpr_cleanup", gdpr_cleanup), ("control", control),
        ("map_providers", map_providers), ("logic_alerts", logic_alerts), ("config_change", config_change),
        ("archive_volume", archive_volume), ("security_credentials", security_credentials),
        ("auth_sessions", auth_sessions), ("layout_manager", layout_manager), ("license_reads", license_reads),
        ("misc_reads", misc_reads), ("heatmap", heatmap), ("media", media), ("export", export), ("videowall", videowall),
        ("web_api", web_api), ("client_api", client_api),
    )}

    @server.tool(name="list_capabilities")
    def list_capabilities() -> dict[str, Any]:
        """Report every capability group, whether it is enabled, and the flag to enable a disabled one.

        Call this first when unsure whether the server can do something (e.g. create a camera).
        A disabled group is not a missing feature: tell the user to add the named flag (or
        --enable-all) and restart. No server connection required.
        """
        groups_out = []
        for key, (description, examples, flag) in CAPABILITY_GROUPS.items():
            on = enabled_groups.get(key, False)
            entry = {"key": key, "description": description, "example_tools": list(examples), "enabled": on}
            if not on:
                entry["enable_flag"] = flag
            groups_out.append(entry)
        enabled_count = sum(1 for g in groups_out if g["enabled"])
        return {
            "status": "ok",
            "enabled_count": enabled_count,
            "total": len(groups_out),
            "groups": groups_out,
            "hint": (
                "If a capability you need shows enabled=false, it is supported but not turned on. "
                "Ask the user to add its enable_flag (or --enable-all for everything) to the MCP "
                "server args and restart. Mutations additionally need their AXXON_*_APPROVE env var."
            ),
        }

    if live is not None:
        register_live_tools(server, live)

    if operator is not None:
        register_operator_tools(server, operator)

    if generator is not None:
        register_generator_tools(server, generator)

    if partner is not None:
        register_partner_tools(server, partner)

    if metadata is not None:
        register_metadata_tools(server, metadata)

    if view is not None:
        register_view_tools(server, view)

    if alarms is not None:
        register_alarm_read_tools(server, alarms)

    if alarm_mutator is not None:
        register_alarm_mutation_tools(server, alarm_mutator)

    if view_objects is not None:
        register_view_objects_tools(server, view_objects)

    if detector_archive is not None:
        register_detector_archive_tools(server, detector_archive)

    if detector_playbooks is not None:
        register_detector_playbooks_tools(server, detector_playbooks)

    if admin is not None:
        register_admin_tools(server, admin)

    if admin_mutator is not None:
        register_admin_mutation_tools(server, admin_mutator)

    if bookmarks is not None:
        register_bookmark_tools(server, bookmarks)

    if bookmark_mutator is not None:
        register_bookmark_mutation_tools(server, bookmark_mutator)

    if translator is not None:
        register_translator_tools(server, translator)

    if ptz is not None:
        register_ptz_tools(server, ptz)

    if audit is not None:
        register_audit_tools(server, audit)

    if recognizer is not None:
        register_recognizer_tools(server, recognizer)

    if recognizer_write is not None:
        register_recognizer_write_tools(server, recognizer_write)

    if logic_control is not None:
        register_logic_control_tools(server, logic_control)

    if settings is not None:
        register_settings_tools(server, settings)

    if timezone is not None:
        register_timezone_tools(server, timezone)

    if server_settings is not None:
        register_server_settings_tools(server, server_settings)

    if statistics is not None:
        register_statistics_tools(server, statistics)

    if event_taxonomy is not None:
        register_event_taxonomy_tools(server, event_taxonomy)

    if scene_description is not None:
        register_scene_description_tools(server, scene_description)

    if package_availability is not None:
        register_package_availability_tools(server, package_availability)

    if domain_topology is not None:
        register_domain_topology_tools(server, domain_topology)

    if config_revisions is not None:
        register_config_revisions_tools(server, config_revisions)

    if filesystem_browser is not None:
        register_filesystem_browser_tools(server, filesystem_browser)

    if devices_catalog is not None:
        register_devices_catalog_tools(server, devices_catalog)

    if global_tracker is not None:
        register_global_tracker_tools(server, global_tracker)

    if shared_kv is not None:
        register_shared_kv_tools(server, shared_kv)

    if state_control is not None:
        register_state_control_tools(server, state_control)

    if site_graph is not None:
        register_site_graph_tools(server, site_graph)

    if bulk_onboarding is not None:
        register_bulk_onboarding_tools(server, bulk_onboarding)

    if groups is not None:
        register_groups_tools(server, groups)

    if discovery is not None:
        register_discovery_tools(server, discovery)

    if gdpr_cleanup is not None:
        register_gdpr_cleanup_tools(server, gdpr_cleanup)

    if control is not None:
        register_control_tools(server, control)

    if map_providers is not None:
        register_map_providers_tools(server, map_providers)

    if logic_alerts is not None:
        register_logic_alerts_tools(server, logic_alerts)

    if config_change is not None:
        register_config_change_tools(server, config_change)

    if archive_volume is not None:
        register_archive_volume_tools(server, archive_volume)

    if bookmark_extras is not None:
        register_bookmark_extras_tools(server, bookmark_extras)

    if security_credentials is not None:
        register_security_credentials_tools(server, security_credentials)

    if auth_sessions is not None:
        register_auth_sessions_tools(server, auth_sessions)

    if layout_manager is not None:
        register_layout_manager_tools(server, layout_manager)

    if license_reads is not None:
        register_license_reads_tools(server, license_reads)

    if misc_reads is not None:
        register_misc_reads_tools(server, misc_reads)

    if heatmap is not None:
        register_heatmap_tools(server, heatmap)

    if media is not None:
        register_media_tools(server, media)

    if export is not None:
        register_export_tools(server, export)

    if videowall is not None:
        register_videowall_tools(server, videowall)

    if web_api is not None:
        register_web_api_tools(server, web_api)

    if client_api is not None:
        register_client_api_tools(server, client_api)

    return server


def _ptz_mutation_refusal(ptz: Any, tool: str) -> dict[str, Any] | None:
    if bool(getattr(ptz, "enabled", False)):
        return None
    return {
        "status": "disabled",
        "tool": tool,
        "message": f"Set {PTZ_APPROVE_ENV}=1 to enable PTZ session and control operations.",
        "approval_env": PTZ_APPROVE_ENV,
    }


def register_ptz_tools(server: Any, ptz: Any) -> None:
    @server.tool(name="ptz_connect_axxon_profile")
    def ptz_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the PTZ/telemetry control layer to the env profile."""
        return ptz.ptz_connect_axxon_profile(profile)

    @server.tool(name="list_telemetry_sources")
    def list_telemetry_sources(limit: int = 64) -> dict[str, Any]:
        """List PTZ telemetry endpoints (*/TelemetryControl.M) from the full config graph."""
        return ptz.list_telemetry_sources(limit)

    @server.tool(name="ptz_session_available")
    def ptz_session_available(access_point: str) -> dict[str, Any]:
        """Report whether a PTZ source has a free control session."""
        return ptz.session_available(access_point)

    @server.tool(name="ptz_acquire_session")
    def ptz_acquire_session(access_point: str, host_name: str = "axxon-mcp") -> dict[str, Any]:
        """Acquire a telemetry control session for a PTZ source."""
        if refusal := _ptz_mutation_refusal(ptz, "acquire_session"):
            return refusal
        return ptz.acquire_session(access_point, host_name)

    @server.tool(name="ptz_keepalive_session")
    def ptz_keepalive_session(access_point: str, session_id: int) -> dict[str, Any]:
        """Extend a telemetry control session."""
        if refusal := _ptz_mutation_refusal(ptz, "keepalive_session"):
            return refusal
        return ptz.keepalive_session(access_point, session_id)

    @server.tool(name="ptz_release_session")
    def ptz_release_session(access_point: str, session_id: int) -> dict[str, Any]:
        """Release a telemetry control session."""
        if refusal := _ptz_mutation_refusal(ptz, "release_session"):
            return refusal
        return ptz.release_session(access_point, session_id)

    @server.tool(name="ptz_get_position")
    def ptz_get_position(access_point: str) -> dict[str, Any]:
        """Read the absolute pan/tilt/zoom position of a PTZ source."""
        return ptz.get_position(access_point)

    @server.tool(name="ptz_move")
    def ptz_move(access_point: str, session_id: int, pan: float, tilt: float, mode: str = "continuous") -> dict[str, Any]:
        """Pan/tilt the camera (mode: continuous, relative, or absolute)."""
        if refusal := _ptz_mutation_refusal(ptz, "move"):
            return refusal
        return ptz.move(access_point, session_id, pan, tilt, mode)

    @server.tool(name="ptz_zoom")
    def ptz_zoom(access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Zoom the camera (mode: continuous, relative, or absolute)."""
        if refusal := _ptz_mutation_refusal(ptz, "zoom"):
            return refusal
        return ptz.zoom(access_point, session_id, value, mode)

    @server.tool(name="ptz_focus")
    def ptz_focus(access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Adjust focus (mode: continuous, relative, or absolute)."""
        if refusal := _ptz_mutation_refusal(ptz, "focus"):
            return refusal
        return ptz.focus(access_point, session_id, value, mode)

    @server.tool(name="ptz_iris")
    def ptz_iris(access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Adjust iris (mode: continuous, relative, or absolute)."""
        if refusal := _ptz_mutation_refusal(ptz, "iris"):
            return refusal
        return ptz.iris(access_point, session_id, value, mode)

    @server.tool(name="ptz_point_move")
    def ptz_point_move(access_point: str, session_id: int, x: float, y: float) -> dict[str, Any]:
        """Center the camera on a normalized [0..1] image point (click-to-center). Needs a session."""
        if refusal := _ptz_mutation_refusal(ptz, "point_move"):
            return refusal
        return ptz.point_move(access_point, session_id, x, y)

    @server.tool(name="ptz_absolute_move")
    def ptz_absolute_move(access_point: str, session_id: int, pan: int, tilt: int, zoom: int, mask: int = 7) -> dict[str, Any]:
        """Move to an absolute pan/tilt/zoom position (mask selects axes; 7 = all)."""
        if refusal := _ptz_mutation_refusal(ptz, "absolute_move"):
            return refusal
        return ptz.absolute_move(access_point, session_id, pan, tilt, zoom, mask)

    @server.tool(name="ptz_get_position_normalized")
    def ptz_get_position_normalized(access_point: str) -> dict[str, Any]:
        """Read the normalized [0..1] pan/tilt/zoom position of a PTZ source."""
        return ptz.get_position_normalized(access_point)

    @server.tool(name="ptz_absolute_move_normalized")
    def ptz_absolute_move_normalized(access_point: str, session_id: int, pan: float, tilt: float, zoom: float, mask: int = 7) -> dict[str, Any]:
        """Move to a normalized [0..1] absolute pan/tilt/zoom position (mask selects axes; 7 = all)."""
        if refusal := _ptz_mutation_refusal(ptz, "absolute_move_normalized"):
            return refusal
        return ptz.absolute_move_normalized(access_point, session_id, pan, tilt, zoom, mask)

    @server.tool(name="ptz_save_preset")
    def ptz_save_preset(access_point: str, session_id: int, position: int, label: str = "") -> dict[str, Any]:
        """Save the current position as a preset via the bare SetPreset RPC."""
        if refusal := _ptz_mutation_refusal(ptz, "save_preset"):
            return refusal
        return ptz.save_preset(access_point, session_id, position, label)

    @server.tool(name="ptz_configure_preset")
    def ptz_configure_preset(access_point: str, position: int, label: str = "", pan: int = 0, tilt: int = 0, zoom: int = 0) -> dict[str, Any]:
        """Create/update a preset at a slot with an explicit absolute position (ConfigurePreset)."""
        if refusal := _ptz_mutation_refusal(ptz, "configure_preset"):
            return refusal
        return ptz.configure_preset(access_point, position, label, pan, tilt, zoom)

    @server.tool(name="ptz_get_tours")
    def ptz_get_tours(access_point: str) -> dict[str, Any]:
        """List the patrol tours configured on a PTZ source."""
        return ptz.get_tours(access_point)

    @server.tool(name="ptz_get_tour_points")
    def ptz_get_tour_points(access_point: str, tour_name: str) -> dict[str, Any]:
        """List the preset points that make up a named patrol tour."""
        return ptz.get_tour_points(access_point, tour_name)

    @server.tool(name="ptz_list_presets")
    def ptz_list_presets(access_point: str) -> dict[str, Any]:
        """List telemetry presets for a PTZ source."""
        return ptz.list_presets(access_point)

    @server.tool(name="ptz_set_preset")
    def ptz_set_preset(access_point: str, session_id: int, position: int, label: str = "") -> dict[str, Any]:
        """Save the current position as a preset at the given slot."""
        if refusal := _ptz_mutation_refusal(ptz, "set_preset"):
            return refusal
        return ptz.set_preset(access_point, session_id, position, label)

    @server.tool(name="ptz_go_preset")
    def ptz_go_preset(access_point: str, session_id: int, position: int, speed: float = 1.0) -> dict[str, Any]:
        """Move the camera to a saved preset."""
        if refusal := _ptz_mutation_refusal(ptz, "go_preset"):
            return refusal
        return ptz.go_preset(access_point, session_id, position, speed)

    @server.tool(name="ptz_remove_preset")
    def ptz_remove_preset(access_point: str, session_id: int, position: int) -> dict[str, Any]:
        """Delete a saved preset."""
        if refusal := _ptz_mutation_refusal(ptz, "remove_preset"):
            return refusal
        return ptz.remove_preset(access_point, session_id, position)

    @server.tool(name="ptz_auxiliary_operations")
    def ptz_auxiliary_operations(access_point: str) -> dict[str, Any]:
        """List auxiliary operations (wiper, light, etc.) a PTZ source supports."""
        return ptz.auxiliary_operations(access_point)


def register_bookmark_tools(server: Any, bookmarks: Any) -> None:
    @server.tool(name="bookmark_connect_axxon_profile")
    def bookmark_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the bookmark layer to an Axxon profile (read-only, env-backed)."""
        return bookmarks.bookmark_connect_axxon_profile(profile)

    @server.tool(name="bookmark_list")
    def bookmark_list(time_range: dict[str, Any], limit: int = 100, page_token: str = "") -> dict[str, Any]:
        """List archive bookmarks within a required time range (bounded page size)."""
        return bookmarks.bookmark_list(time_range, limit, page_token)

    @server.tool(name="bookmark_get")
    def bookmark_get(bookmark_id: str) -> dict[str, Any]:
        """Return a single bookmark by id."""
        return bookmarks.bookmark_get(bookmark_id)


def register_bookmark_mutation_tools(server: Any, bookmark_mutator: Any) -> None:
    @server.tool(name="list_bookmark_mutation_workflows")
    def list_bookmark_mutation_workflows() -> dict[str, Any]:
        """List approval-gated bookmark mutation workflows supported by this MCP server."""
        return bookmark_mutator.list_workflows()

    @server.tool(name="plan_bookmark_mutation_workflow")
    def plan_bookmark_mutation_workflow(workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build a bookmark mutation plan without applying changes."""
        return bookmark_mutator.plan(workflow, params or {})

    @server.tool(name="apply_bookmark_mutation_plan")
    def apply_bookmark_mutation_plan(plan_id: str, confirmation: str) -> dict[str, Any]:
        """Apply a planned bookmark mutation when confirmation matches and approval is enabled."""
        return bookmark_mutator.apply(plan_id, confirmation)

    @server.tool(name="verify_bookmark_mutation_plan")
    def verify_bookmark_mutation_plan(plan_id: str) -> dict[str, Any]:
        """Verify the current state for a planned bookmark mutation."""
        return bookmark_mutator.verify(plan_id)

    @server.tool(name="rollback_bookmark_mutation_plan")
    def rollback_bookmark_mutation_plan(plan_id: str, confirmation: str) -> dict[str, Any]:
        """Roll back a planned bookmark mutation when confirmation matches and approval is enabled."""
        return bookmark_mutator.rollback(plan_id, confirmation)

    @server.tool(name="read_bookmark_mutation_audit_log")
    def read_bookmark_mutation_audit_log() -> dict[str, Any]:
        """Return the redacted in-memory bookmark mutation audit log."""
        return bookmark_mutator.audit_log()


def register_admin_mutation_tools(server: Any, admin_mutator: Any) -> None:
    @server.tool(name="list_admin_mutation_workflows")
    def list_admin_mutation_workflows() -> dict[str, Any]:
        """List approval-gated admin mutation workflows supported by this MCP server."""
        return admin_mutator.list_workflows()

    @server.tool(name="plan_admin_mutation_workflow")
    def plan_admin_mutation_workflow(workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build an admin mutation plan without applying changes."""
        return admin_mutator.plan(workflow, params or {})

    @server.tool(name="apply_admin_mutation_plan")
    def apply_admin_mutation_plan(plan_id: str, confirmation: str) -> dict[str, Any]:
        """Apply a planned admin mutation when confirmation matches and approval is enabled."""
        return admin_mutator.apply(plan_id, confirmation)

    @server.tool(name="verify_admin_mutation_plan")
    def verify_admin_mutation_plan(plan_id: str) -> dict[str, Any]:
        """Verify the current state for a planned admin mutation."""
        return admin_mutator.verify(plan_id)

    @server.tool(name="rollback_admin_mutation_plan")
    def rollback_admin_mutation_plan(plan_id: str, confirmation: str) -> dict[str, Any]:
        """Rollback objects or settings changed by a planned admin mutation."""
        return admin_mutator.rollback(plan_id, confirmation)

    @server.resource("axxon://admin-mutations/audit-log")
    def read_admin_mutation_audit_log() -> dict[str, Any]:
        """Read the in-memory audit log for this admin-mutator session."""
        return {"entries": admin_mutator.audit_log()}


def register_admin_tools(server: Any, admin: Any) -> None:
    @server.tool(name="admin_connect_axxon_profile")
    def admin_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the admin layer to an Axxon profile (read-only, env-backed)."""
        return admin.admin_connect_axxon_profile(profile)

    @server.tool(name="security_inventory")
    def security_inventory(
        include_users: bool = True,
        include_roles: bool = True,
        include_ldap: bool = True,
    ) -> dict[str, Any]:
        """Return a redacted security inventory summary."""
        return admin.security_inventory(
            include_users=include_users,
            include_roles=include_roles,
            include_ldap=include_ldap,
        )

    @server.tool(name="security_policy_summary")
    def security_policy_summary() -> dict[str, Any]:
        """Return a redacted security policy summary."""
        return admin.security_policy_summary()

    @server.tool(name="role_permissions")
    def role_permissions(role_id: str, page_size: int = 50) -> dict[str, Any]:
        """Return global and object permission summaries for a role."""
        return admin.role_permissions(role_id=role_id, page_size=page_size)

    @server.tool(name="current_user_security")
    def current_user_security() -> dict[str, Any]:
        """Return the current user's redacted security context."""
        return admin.current_user_security()

    @server.tool(name="license_status")
    def license_status(
        include_host_info: bool = True,
        include_node_restrictions: bool = True,
        node_names: list[str] | None = None,
        limit: int = 32,
    ) -> dict[str, Any]:
        """Return redacted license status and restriction summaries."""
        return admin.license_status(
            include_host_info=include_host_info,
            include_node_restrictions=include_node_restrictions,
            node_names=node_names,
            limit=limit,
        )

    @server.tool(name="time_status")
    def time_status(include_available: bool = True) -> dict[str, Any]:
        """Return current timezone and NTP status."""
        return admin.time_status(include_available=include_available)

    @server.tool(name="system_health")
    def system_health() -> dict[str, Any]:
        """Return read-only admin health signals."""
        return admin.system_health()

    @server.tool(name="domain_event_subscribe")
    def domain_event_subscribe(
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict[str, Any]:
        """Pull bounded events from DomainNotifier and disconnect the subscription."""
        return admin.domain_event_subscribe(
            subjects=subjects,
            event_types=event_types,
            timeout_s=timeout_s,
            limit=limit,
            detailed=detailed,
        )

    @server.tool(name="node_event_subscribe")
    def node_event_subscribe(
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict[str, Any]:
        """Pull bounded events from NodeNotifier and disconnect the subscription."""
        return admin.node_event_subscribe(
            subjects=subjects,
            event_types=event_types,
            timeout_s=timeout_s,
            limit=limit,
            detailed=detailed,
        )

    @server.tool(name="update_event_subscription")
    def update_event_subscription(
        notifier: str = "domain",
        event_types: list[str] | None = None,
        new_event_types: list[str] | None = None,
        subjects: list[str] | None = None,
        new_subjects: list[str] | None = None,
        timeout_s: float = 5.0,
    ) -> dict[str, Any]:
        """Open a short-lived event subscription, apply UpdateSubscription with new filters, then disconnect."""
        return admin.update_event_subscription(
            notifier=notifier,
            event_types=event_types,
            new_event_types=new_event_types,
            subjects=subjects,
            new_subjects=new_subjects,
            timeout_s=timeout_s,
        )

    @server.tool(name="collect_config_backup")
    def collect_config_backup(
        node: str = "",
        backup_types: list[str] | None = None,
        chunk_size_kb: int = 64,
    ) -> dict[str, Any]:
        """Stream a read-only configuration backup export and return size/chunk metadata only."""
        return admin.collect_config_backup(
            node=node,
            backup_types=backup_types,
            chunk_size_kb=chunk_size_kb,
        )

    @server.tool(name="schedule_descriptor_get")
    def schedule_descriptor_get(uid: str) -> dict[str, Any]:
        """Discover schedule-like descriptor fields for a unit without mutation."""
        return admin.schedule_descriptor_get(uid)


def register_detector_archive_tools(server: Any, detector_archive: Any) -> None:
    @server.tool(name="detector_archive_connect_axxon_profile")
    def detector_archive_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the detector/archive layer to an Axxon profile (read-only, env-backed)."""
        return detector_archive.detector_archive_connect_axxon_profile(profile)

    @server.tool(name="detector_kind_catalog")
    def detector_kind_catalog(include_live: bool = True) -> dict[str, Any]:
        """Return the known detector-kind catalog, optionally enriched from live descriptors."""
        return detector_archive.detector_kind_catalog(include_live=include_live)

    @server.tool(name="detector_parameter_schema")
    def detector_parameter_schema(unit_type: str, detector_kind: str) -> dict[str, Any]:
        """Return the parameter schema for a detector unit type and kind."""
        return detector_archive.detector_parameter_schema(unit_type, detector_kind)

    @server.tool(name="detector_config_get")
    def detector_config_get(detector_uid: str) -> dict[str, Any]:
        """Return a redacted detector configuration snapshot."""
        return detector_archive.detector_config_get(detector_uid)

    @server.tool(name="detector_visual_elements")
    def detector_visual_elements(detector_uid: str) -> dict[str, Any]:
        """Return visual elements configured for a detector."""
        return detector_archive.detector_visual_elements(detector_uid)

    @server.tool(name="metadata_schema_catalog")
    def metadata_schema_catalog() -> dict[str, Any]:
        """Return known metadata schema and endpoint guidance."""
        return detector_archive.metadata_schema_catalog()

    @server.tool(name="metadata_sample_bounded")
    def metadata_sample_bounded(
        access_point: str,
        timeout_s: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Pull a bounded metadata sample from a metadata access point."""
        return detector_archive.metadata_sample_bounded(access_point, timeout_s=timeout_s, limit=limit)

    @server.tool(name="archive_policy_get")
    def archive_policy_get(camera_or_archive: str) -> dict[str, Any]:
        """Return archive policy information for a camera or archive."""
        return detector_archive.archive_policy_get(camera_or_archive)

    @server.tool(name="archive_management_status")
    def archive_management_status() -> dict[str, Any]:
        """Return read-only archive management and health status."""
        return detector_archive.archive_management_status()

    @server.tool(name="archive_volume_probe")
    def archive_volume_probe(path_or_volume_hint: str) -> dict[str, Any]:
        """Probe archive volume information without formatting or mutating volumes."""
        return detector_archive.archive_volume_probe(path_or_volume_hint)

    @server.tool(name="analytics_fixture_report")
    def analytics_fixture_report() -> dict[str, Any]:
        """Report fixture readiness for detector and archive analytics workflows."""
        return detector_archive.analytics_fixture_report()


def register_detector_playbooks_tools(server: Any, detector_playbooks: Any) -> None:
    @server.tool(name="detector_playbooks_connect_axxon_profile")
    def detector_playbooks_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect detector playbooks to an env-backed Axxon profile without applying changes."""
        return detector_playbooks.detector_playbooks_connect_axxon_profile(profile)

    @server.tool(name="list_detector_playbooks")
    def list_detector_playbooks(include_live: bool = True) -> dict[str, Any]:
        """List detector playbook intents, descriptor policy, gates, and family support matrix."""
        return detector_playbooks.list_detector_playbooks(include_live)

    @server.tool(name="detector_playbook_parameter_schema")
    def detector_playbook_parameter_schema(unit_type: str, detector_kind: str, intent: str = "") -> dict[str, Any]:
        """Return detector descriptor schema augmented with playbook-required params."""
        return detector_playbooks.detector_playbook_parameter_schema(unit_type, detector_kind, intent)

    @server.tool(name="plan_detector_playbook")
    def plan_detector_playbook(intent: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build a detector playbook plan without applying or rolling back mutations."""
        return detector_playbooks.plan_detector_playbook(intent, params or {})

    @server.tool(name="apply_detector_playbook_plan")
    def apply_detector_playbook_plan(playbook_plan_id: str, confirmation: str) -> dict[str, Any]:
        """Apply a detector playbook plan after approval env and confirmation gates pass."""
        return detector_playbooks.apply_detector_playbook_plan(playbook_plan_id, confirmation)

    @server.tool(name="verify_detector_playbook_plan")
    def verify_detector_playbook_plan(playbook_plan_id: str) -> dict[str, Any]:
        """Verify an applied detector playbook plan using the underlying operator workflow."""
        return detector_playbooks.verify_detector_playbook_plan(playbook_plan_id)

    @server.tool(name="rollback_detector_playbook_plan")
    def rollback_detector_playbook_plan(playbook_plan_id: str, confirmation: str) -> dict[str, Any]:
        """Roll back a detector playbook plan after approval env and rollback confirmation gates pass."""
        return detector_playbooks.rollback_detector_playbook_plan(playbook_plan_id, confirmation)

    @server.tool(name="detector_playbooks_audit_log")
    def detector_playbooks_audit_log() -> dict[str, Any]:
        """Return the sanitized in-memory detector playbooks audit trail."""
        return detector_playbooks.detector_playbooks_audit_log()


def register_view_tools(server: Any, view: Any) -> None:
    @server.tool(name="view_connect_axxon_profile")
    def view_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the view layer to an Axxon profile (read-only, env-backed)."""
        return view.connect_axxon_profile(profile)

    @server.tool(name="live_view")
    def live_view(
        camera_access_point: str,
        duration_s: int = 10,
        fps: int = 5,
        width: int = 640,
        format: str = "mjpeg",
    ) -> dict[str, Any]:
        """Return a capped URL for a live media stream (mjpeg/hls/mp4/rtsp)."""
        return view.live_view(camera_access_point, duration_s=duration_s, fps=fps, width=width, format=format)

    @server.tool(name="snapshot_batch")
    def snapshot_batch(
        camera_access_points: list[str],
        ts: str = "now",
        width: int = 640,
    ) -> dict[str, Any]:
        """Return one snapshot URL per camera with a per-request count cap."""
        return view.snapshot_batch(camera_access_points, ts=ts, width=width)

    @server.tool(name="archive_scrub")
    def archive_scrub(
        camera_access_point: str,
        hours: int = 1,
        archive_access_point: str | None = None,
    ) -> dict[str, Any]:
        """Return archive calendar + intervals + sample-frame URL for a camera."""
        return view.archive_scrub(camera_access_point, hours=hours, archive_access_point=archive_access_point)

    @server.tool(name="archive_frame")
    def archive_frame(
        camera_access_point: str,
        ts: str,
        width: int = 640,
        threshold_ms: int = 60_000,
    ) -> dict[str, Any]:
        """Return a single archive-frame URL with bounded threshold and width."""
        return view.archive_frame(camera_access_point, ts=ts, width=width, threshold_ms=threshold_ms)

    @server.tool(name="archive_mjpeg_bounded")
    def archive_mjpeg_bounded(
        camera_access_point: str,
        begin_ts: str,
        speed: int = 1,
        fps: int = 5,
        width: int = 640,
    ) -> dict[str, Any]:
        """Return a bounded archive MJPEG URL with speed/fps/byte caps applied."""
        return view.archive_mjpeg_bounded(camera_access_point, begin_ts=begin_ts, speed=speed, fps=fps, width=width)

    @server.tool(name="stream_health")
    def stream_health(camera_access_point: str) -> dict[str, Any]:
        """Return /statistics and /rtsp/stat summary for a camera access point."""
        return view.stream_health(camera_access_point)

    @server.tool(name="get_cameras_by_components")
    def get_cameras_by_components(access_points: list[str] | None = None) -> dict[str, Any]:
        """Batch-lookup cameras by component access points (read-only)."""
        return view.get_cameras_by_components(access_points or [])

    @server.tool(name="batch_get_archives")
    def batch_get_archives(access_points: list[str] | None = None) -> dict[str, Any]:
        """Batch-lookup archives by access points (read-only)."""
        return view.batch_get_archives(access_points or [])

    @server.tool(name="search_maps")
    def search_maps(access_points: list[str] | None = None) -> dict[str, Any]:
        """Search maps associated with object access points (read-only)."""
        return view.search_maps(access_points or [])


def register_alarm_read_tools(server: Any, alarms: Any) -> None:
    @server.tool(name="alarms_connect_axxon_profile")
    def alarms_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the alarms layer to an Axxon profile (read-only, env-backed)."""
        return alarms.connect_axxon_profile(profile)

    @server.tool(name="list_active_alerts")
    def list_active_alerts(camera_access_point: str | None = None, limit: int = 50) -> dict[str, Any]:
        """List active alarms node-wide or for a specific camera."""
        return alarms.list_active_alerts(camera_access_point=camera_access_point, limit=limit)

    @server.tool(name="get_active_alert")
    def get_active_alert(camera_access_point: str, alert_id: str) -> dict[str, Any]:
        """Return a single active alarm by camera+alert_id."""
        return alarms.get_active_alert(camera_access_point, alert_id)

    @server.tool(name="filter_active_alerts")
    def filter_active_alerts(
        severity_min: int | None = None,
        camera: str | None = None,
        state: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Filter active alarms by severity/camera/state."""
        return alarms.filter_active_alerts(severity_min=severity_min, camera=camera, state=state, limit=limit)

    @server.tool(name="list_alarm_history")
    def list_alarm_history(
        hours: float = 1.0,
        limit: int = 100,
        camera: str | None = None,
        severity_min: int | None = None,
    ) -> dict[str, Any]:
        """List historical alarm events via EventHistoryService.ReadEvents."""
        return alarms.list_alarm_history(hours=hours, limit=limit, camera=camera, severity_min=severity_min)

    @server.tool(name="list_alarm_event_types")
    def list_alarm_event_types() -> dict[str, Any]:
        """Return the alarm-related subset of the EEventType enum."""
        return alarms.list_alarm_event_types()

    @server.tool(name="alarm_subscribe")
    def alarm_subscribe(
        severity_min: int | None = None,
        camera_access_point: str | None = None,
        state: str = "all",
        duration_s: int = 10,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Bounded alarm event subscription with normalized transition field."""
        return alarms.alarm_subscribe(
            severity_min=severity_min,
            camera_access_point=camera_access_point,
            state=state,
            duration_s=duration_s,
            limit=limit,
        )


def register_alarm_mutation_tools(server: Any, mutator: Any) -> None:
    @server.tool(name="raise_alert")
    def raise_alert(camera_access_point: str, confirmation: str) -> dict[str, Any]:
        """Raise an alarm on a camera. Requires CONFIRM-raise-alert."""
        return mutator.raise_alert(camera_access_point, confirmation)

    @server.tool(name="alarm_begin_review")
    def alarm_begin_review(camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        """Begin reviewing an active alarm. Requires CONFIRM-alarm-begin."""
        return mutator.alarm_begin_review(camera_access_point, alert_id, confirmation)

    @server.tool(name="alarm_continue_review")
    def alarm_continue_review(camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        """Continue reviewing an alarm in review. Requires CONFIRM-alarm-continue."""
        return mutator.alarm_continue_review(camera_access_point, alert_id, confirmation)

    @server.tool(name="alarm_cancel_review")
    def alarm_cancel_review(camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        """Cancel reviewing an alarm. Requires CONFIRM-alarm-cancel."""
        return mutator.alarm_cancel_review(camera_access_point, alert_id, confirmation)

    @server.tool(name="alarm_complete_review")
    def alarm_complete_review(
        camera_access_point: str,
        alert_id: str,
        severity: str,
        bookmark_message: str,
        confirmation: str,
    ) -> dict[str, Any]:
        """Complete an alarm review with a severity tag and bookmark. Requires CONFIRM-alarm-complete."""
        return mutator.alarm_complete_review(camera_access_point, alert_id, severity, bookmark_message, confirmation)

    @server.tool(name="alarm_escalate")
    def alarm_escalate(
        camera_access_point: str,
        alert_id: str,
        priority: str,
        user_roles: list[str],
        comment: str,
        confirmation: str,
    ) -> dict[str, Any]:
        """Escalate an alarm to a set of user roles with priority + comment. Requires CONFIRM-alarm-escalate."""
        return mutator.alarm_escalate(camera_access_point, alert_id, priority, user_roles, comment, confirmation)

    @server.resource("axxon://alarms/audit-log")
    def read_alarms_audit_log() -> dict[str, Any]:
        """Read the in-memory audit log for this alarm-mutator session."""
        return {"entries": mutator.audit_log()}


def register_view_objects_tools(server: Any, view_objects: Any) -> None:
    @server.tool(name="view_objects_connect_axxon_profile")
    def view_objects_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the view-objects layer to an Axxon profile (read-only, env-backed)."""
        return view_objects.connect_axxon_profile(profile)

    @server.tool(name="list_layouts")
    def list_layouts(view: str = "meta", limit: int = 50) -> dict[str, Any]:
        """List layout metadata or full layout bodies."""
        return view_objects.list_layouts(view=view, limit=limit)

    @server.tool(name="get_layout")
    def get_layout(layout_id: str, etag: str | None = None) -> dict[str, Any]:
        """Return one layout by id."""
        return view_objects.get_layout(layout_id, etag=etag)

    @server.tool(name="layouts_on_view")
    def layouts_on_view(layouts: list[dict[str, str]]) -> dict[str, Any]:
        """Push a layout list to the current view context."""
        return view_objects.layouts_on_view(layouts)

    @server.tool(name="list_layout_images")
    def list_layout_images(layout_id: str) -> dict[str, Any]:
        """List image metadata for one layout."""
        return view_objects.list_layout_images(layout_id)

    @server.tool(name="download_layout_image")
    def download_layout_image(layout_id: str, image_id: str, max_bytes: int = 4_194_304) -> dict[str, Any]:
        """Return layout image metadata only (etag/size/chunks), capped by byte budget."""
        return view_objects.download_layout_image(layout_id, image_id, max_bytes=max_bytes)

    @server.tool(name="list_maps")
    def list_maps(limit: int = 50) -> dict[str, Any]:
        """List maps with normalized metadata."""
        return view_objects.list_maps(limit=limit)

    @server.tool(name="get_map")
    def get_map(map_id: str) -> dict[str, Any]:
        """Return one map by id."""
        return view_objects.get_map(map_id)

    @server.tool(name="get_map_image")
    def get_map_image(map_id: str, max_bytes: int = 4_194_304) -> dict[str, Any]:
        """Return map image metadata only, capped by byte budget."""
        return view_objects.get_map_image(map_id, max_bytes=max_bytes)

    @server.tool(name="get_markers")
    def get_markers(map_id: str) -> dict[str, Any]:
        """List normalized map markers."""
        return view_objects.get_markers(map_id)

    @server.tool(name="list_map_providers")
    def list_map_providers() -> dict[str, Any]:
        """List configured map providers."""
        return view_objects.list_map_providers()

    @server.tool(name="list_walls")
    def list_walls(limit: int = 50) -> dict[str, Any]:
        """List videowalls from the paginated wall stream."""
        return view_objects.list_walls(limit=limit)


def register_generator_tools(server: Any, generator: Any) -> None:
    import os
    from dataclasses import asdict

    from axxon_mcp_generator import (
        GenerationRequest,
        GeneratedBundle,
        GenerationRefusal,
        Verifier,
        allow_in_repo_write,
    )

    verifier = Verifier()

    def _serialize(result: Any) -> dict[str, Any]:
        if isinstance(result, GenerationRefusal):
            return {"status": "refused", **asdict(result)}
        if isinstance(result, GeneratedBundle):
            return {"status": "ok", **asdict(result)}
        return {"status": "unknown"}

    @server.tool(name="list_integration_templates")
    def list_integration_templates() -> dict[str, Any]:
        """List integration templates the generator can produce."""
        return {"templates": generator.list_templates()}

    @server.tool(name="plan_integration")
    def plan_integration(
        template: str,
        params: dict[str, Any] | None = None,
        allow_mutation: bool = False,
        allow_large: bool = False,
    ) -> dict[str, Any]:
        """Build a generation plan without writing files."""
        req = GenerationRequest(
            template=template,
            params=params or {},
            allow_mutation=allow_mutation,
            allow_large=allow_large,
        )
        return _serialize(generator.plan(req))

    @server.tool(name="generate_integration")
    def generate_integration(
        template: str,
        output_dir: str,
        params: dict[str, Any] | None = None,
        allow_mutation: bool = False,
        allow_large: bool = False,
    ) -> dict[str, Any]:
        """Generate an integration bundle to a chosen directory."""
        target = Path(output_dir).expanduser().resolve()
        allow_in_repo = os.environ.get("AXXON_GENERATOR_ALLOW_IN_REPO") == "1"
        if not allow_in_repo_write(target, allow=allow_in_repo):
            return {
                "status": "refused",
                "reason": "in_repo_write_blocked",
                "detail": f"{target} is inside the repo; set AXXON_GENERATOR_ALLOW_IN_REPO=1 to override",
            }
        req = GenerationRequest(
            template=template,
            params=params or {},
            allow_mutation=allow_mutation,
            allow_large=allow_large,
        )
        result = generator.generate(req)
        if isinstance(result, GenerationRefusal):
            return _serialize(result)
        target.mkdir(parents=True, exist_ok=True)
        for name, content in result.files.items():
            (target / name).write_text(content, encoding="utf-8")
        return {"status": "ok", "output_dir": str(target), **asdict(result)}

    @server.tool(name="verify_integration")
    def verify_integration(output_dir: str) -> dict[str, Any]:
        """Statically verify a generated bundle."""
        result = verifier.verify_dir(Path(output_dir).expanduser().resolve())
        return {"ok": result.ok, "errors": result.errors}


def register_metadata_tools(server: Any, metadata: Any) -> None:
    @server.tool(name="metadata_connect_axxon_profile")
    def metadata_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the read-only metadata/VMDA layer to the env profile."""
        return metadata.connect_axxon_profile(profile)

    @server.tool(name="list_vmda_sources")
    def list_vmda_sources(limit: int = 64) -> dict[str, Any]:
        """List the stand's VMDA-capable endpoints (*/SourceEndpoint.vmda)."""
        return metadata.list_vmda_sources(limit)

    @server.tool(name="live_track_sample")
    def live_track_sample(access_point: str, seconds: float = 5.0, limit: int = 40) -> dict[str, Any]:
        """Stream bounded live object tracklets from a VMDA endpoint (id/state/behavior/bbox)."""
        return metadata.live_track_sample(access_point, seconds, limit)

    @server.tool(name="vmda_query")
    def vmda_query(
        camera_id: str,
        query_type: str = "motion_in_area",
        database: str | None = None,
        hours: int = 24,
        max_intervals: int = 500,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Archived VMDA forensic search via ExecuteQueryTyped typed motion-in-area.

        camera_id is a detector VMDA source (e.g. hosts/Server/AVDetector.1/SourceEndpoint.vmda);
        database (*/VMDA_DB.N/Database) is discovered when omitted.
        """
        return metadata.vmda_query(camera_id, query_type=query_type, database=database, hours=hours, max_intervals=max_intervals, timeout=timeout)


def register_audit_tools(server: Any, audit: Any) -> None:
    @server.tool(name="audit_connect_axxon_profile")
    def audit_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the write-only AuditEventInjector layer to the env profile."""
        return audit.audit_connect_axxon_profile(profile)

    @server.tool(name="list_audit_event_kinds")
    def list_audit_event_kinds() -> dict[str, Any]:
        """List supported audit-event kinds and their required params."""
        return audit.list_audit_event_kinds()

    @server.tool(name="audit_inject")
    def audit_inject(kind: str, params: dict[str, Any] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Inject an audit-trail event (compliance). Approval-gated, irreversible.

        Requires AXXON_AUDIT_INJECT_APPROVE=1 and confirmation=CONFIRM-audit-inject.
        kind is one of list_audit_event_kinds(); params supplies that kind's fields.
        """
        return audit.audit_inject(kind, params, confirmation)


def register_discovery_tools(server: Any, discovery: Any) -> None:
    @server.tool(name="discovery_connect_axxon_profile")
    def discovery_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the read-only device-discovery layer to the env profile."""
        return discovery.discovery_connect_axxon_profile(profile)

    @server.tool(name="discover_devices")
    def discover_devices(max_devices: int = 200, max_seconds: float = 20.0) -> dict[str, Any]:
        """Scan the network for IP cameras to add (driver/vendor/model/mac/ip). Bounded by caps."""
        return discovery.discover_devices(max_devices, max_seconds)

    @server.tool(name="discover_node_devices")
    def discover_node_devices(node: str = "", max_devices: int = 200, max_seconds: float = 20.0) -> dict[str, Any]:
        """Scan one node for IP cameras via DiscoverNode (empty node = current). Bounded by caps."""
        return discovery.discover_node_devices(node, max_devices, max_seconds)


def register_gdpr_cleanup_tools(server: Any, gdpr_cleanup: Any) -> None:
    @server.tool(name="gdpr_cleanup_connect_axxon_profile")
    def gdpr_cleanup_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the GDPR cleanup layer to the env profile (writes need AXXON_GDPR_APPROVE=1)."""
        return gdpr_cleanup.gdpr_cleanup_connect_axxon_profile(profile)

    @server.tool(name="layout_user_data_cleanup")
    def layout_user_data_cleanup(user_ids: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Remove a user's stored layouts via LayoutManager.UserDataCleanup (gated)."""
        return gdpr_cleanup.layout_user_data_cleanup(user_ids=user_ids, confirmation=confirmation)

    @server.tool(name="map_user_data_cleanup")
    def map_user_data_cleanup(user_ids: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Remove a user's stored maps via MapService.UserDataCleanup (gated)."""
        return gdpr_cleanup.map_user_data_cleanup(user_ids=user_ids, confirmation=confirmation)


def register_control_tools(server: Any, control: Any) -> None:
    @server.tool(name="control_connect_axxon_profile")
    def control_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the ACFA/VMDA control layer to the env profile (writes need AXXON_CONTROL_APPROVE=1)."""
        return control.control_connect_axxon_profile(profile)

    @server.tool(name="list_unit_actions")
    def list_unit_actions(uids: list[str] | None = None) -> dict[str, Any]:
        """List the actions each ACFA unit accepts (read; uid = unit access_point)."""
        return control.list_unit_actions(uids=uids)

    @server.tool(name="list_unit_visualizations")
    def list_unit_visualizations(uids: list[str] | None = None) -> dict[str, Any]:
        """List each ACFA unit's visualizations and their icon image data_ids (read)."""
        return control.list_unit_visualizations(uids=uids)

    @server.tool(name="download_unit_data")
    def download_unit_data(uid: str = "", data_ids: list[str] | None = None) -> dict[str, Any]:
        """Download referenced ACFA data files (icon images) and return size metadata only (read)."""
        return control.download_unit_data(uid=uid, data_ids=data_ids)

    @server.tool(name="perform_unit_action")
    def perform_unit_action(uid: str = "", action_id: str = "", properties: list[dict[str, str]] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Perform an action on an ACFA unit via AcfaService.PerformAction (gated)."""
        return control.perform_unit_action(uid=uid, action_id=action_id, properties=properties, confirmation=confirmation)

    @server.tool(name="vmda_cleanup")
    def vmda_cleanup(camera_id: str = "", schema_id: str = "vmda_schema", database: str = "", confirmation: str = "") -> dict[str, Any]:
        """Wipe a camera's VMDA analytics for a schema via VMDAService.Cleanup (gated)."""
        return control.vmda_cleanup(camera_id=camera_id, schema_id=schema_id, database=database, confirmation=confirmation)


def register_map_providers_tools(server: Any, map_providers: Any) -> None:
    @server.tool(name="map_providers_connect_axxon_profile")
    def map_providers_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the map-providers layer to the env profile (writes need AXXON_MAP_APPROVE=1)."""
        return map_providers.map_providers_connect_axxon_profile(profile)

    @server.tool(name="configure_map_providers")
    def configure_map_providers(changed: list[dict[str, str]] | None = None, removed: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Create/update or remove map providers via MapService.ConfigureMapProviders (gated)."""
        return map_providers.configure_map_providers(changed=changed, removed=removed, confirmation=confirmation)

    @server.tool(name="get_map_provider")
    def get_map_provider(provider_id: str = "") -> dict[str, Any]:
        """Read a single map provider by id via MapService.GetMapProvider."""
        return map_providers.get_map_provider(provider_id=provider_id)


def register_logic_alerts_tools(server: Any, logic_alerts: Any) -> None:
    @server.tool(name="logic_alerts_connect_axxon_profile")
    def logic_alerts_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the LogicService batch-alert layer (reviews need AXXON_LOGIC_ALERTS_APPROVE=1)."""
        return logic_alerts.logic_alerts_connect_axxon_profile(profile)

    @server.tool(name="batch_get_active_alerts")
    def batch_get_active_alerts(nodes: list[str] | None = None) -> dict[str, Any]:
        """Read active alerts across nodes via LogicService.BatchGetActiveAlerts."""
        return logic_alerts.batch_get_active_alerts(nodes=nodes)

    @server.tool(name="batch_filter_active_alerts")
    def batch_filter_active_alerts(nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None) -> dict[str, Any]:
        """Read active alerts across nodes filtered by groups/parents via BatchFilterActiveAlerts."""
        return logic_alerts.batch_filter_active_alerts(nodes=nodes, groups=groups, parents=parents)

    @server.tool(name="batch_begin_alerts_review")
    def batch_begin_alerts_review(nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Begin review on node+filter-scoped active alerts via BatchBeginAlertsReview (gated)."""
        return logic_alerts.batch_begin_alerts_review(nodes=nodes, groups=groups, parents=parents, confirmation=confirmation)

    @server.tool(name="batch_continue_alerts_review")
    def batch_continue_alerts_review(nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Continue review on node+filter-scoped alerts via BatchContinueAlertsRewiew (gated)."""
        return logic_alerts.batch_continue_alerts_review(nodes=nodes, groups=groups, parents=parents, confirmation=confirmation)

    @server.tool(name="batch_cancel_alerts_review")
    def batch_cancel_alerts_review(nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Cancel review on node+filter-scoped alerts via BatchCancelAlertsReview (gated)."""
        return logic_alerts.batch_cancel_alerts_review(nodes=nodes, groups=groups, parents=parents, confirmation=confirmation)

    @server.tool(name="batch_complete_alerts_review")
    def batch_complete_alerts_review(nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, severity: int = 0, confirmation: str = "") -> dict[str, Any]:
        """Complete review on node+filter-scoped alerts via BatchCompleteAlertsReview (gated)."""
        return logic_alerts.batch_complete_alerts_review(nodes=nodes, groups=groups, parents=parents, severity=severity, confirmation=confirmation)

    @server.tool(name="batch_escalate_alerts")
    def batch_escalate_alerts(nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, comment: str = "", confirmation: str = "") -> dict[str, Any]:
        """Escalate node+filter-scoped alerts via BatchEscalateAlerts (gated)."""
        return logic_alerts.batch_escalate_alerts(nodes=nodes, groups=groups, parents=parents, comment=comment, confirmation=confirmation)


def register_config_change_tools(server: Any, config_change: Any) -> None:
    @server.tool(name="config_change_connect_axxon_profile")
    def config_change_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the ConfigurationService change layer (writes need AXXON_CONFIG_CHANGE_APPROVE=1)."""
        return config_change.config_change_connect_axxon_profile(profile)

    @server.tool(name="list_similar_units")
    def list_similar_units(uid: str = "", node_name: str = "Server", page_size: int = 50, page_token: str = "", by_unit_type: bool = False) -> dict[str, Any]:
        """List units similar to a given unit via ConfigurationService.ListSimilarUnits."""
        return config_change.list_similar_units(uid=uid, node_name=node_name, page_size=page_size, page_token=page_token, by_unit_type=by_unit_type)

    @server.tool(name="batch_get_factories")
    def batch_get_factories(unit_types: list[str] | None = None, parent_uid: str = "", ignore_possible_limits: bool = True) -> dict[str, Any]:
        """Query creatable-unit factory descriptors via ConfigurationService.BatchGetFactories."""
        return config_change.batch_get_factories(unit_types=unit_types, parent_uid=parent_uid, ignore_possible_limits=ignore_possible_limits)

    @server.tool(name="change_unit_property")
    def change_unit_property(uid: str = "", unit_type: str = "", property_id: str = "", value_string: str = "", confirmation: str = "") -> dict[str, Any]:
        """Change a single unit string property via ConfigurationService.ChangeConfig (gated)."""
        return config_change.change_unit_property(uid=uid, unit_type=unit_type, property_id=property_id, value_string=value_string, confirmation=confirmation)

    @server.tool(name="change_unit_property_stream")
    def change_unit_property_stream(uid: str = "", unit_type: str = "", property_id: str = "", value_string: str = "", confirmation: str = "") -> dict[str, Any]:
        """Change a single unit string property via ConfigurationService.ChangeConfigStream (gated)."""
        return config_change.change_unit_property_stream(uid=uid, unit_type=unit_type, property_id=property_id, value_string=value_string, confirmation=confirmation)


def register_archive_volume_tools(server: Any, archive_volume: Any) -> None:
    @server.tool(name="archive_volume_connect_axxon_profile")
    def archive_volume_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the ArchiveService volume layer (resize needs AXXON_ARCHIVE_VOLUME_APPROVE=1)."""
        return archive_volume.archive_volume_connect_axxon_profile(profile)

    @server.tool(name="list_volume_states")
    def list_volume_states(access_point: str = "") -> dict[str, Any]:
        """List archive storage volume states via ArchiveService.GetVolumesState."""
        return archive_volume.list_volume_states(access_point=access_point)

    @server.tool(name="resize_volume")
    def resize_volume(access_point: str = "", volume_id: str = "", new_size: int = 0, confirmation: str = "") -> dict[str, Any]:
        """Resize a storage volume to new_size bytes via ArchiveService.Resize (gated)."""
        return archive_volume.resize_volume(access_point=access_point, volume_id=volume_id, new_size=new_size, confirmation=confirmation)


def register_bookmark_extras_tools(server: Any, bookmark_extras: Any) -> None:
    @server.tool(name="bookmark_extras_connect_axxon_profile")
    def bookmark_extras_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the BookmarkService extras layer (writes need AXXON_BOOKMARK_EXTRAS_APPROVE=1)."""
        return bookmark_extras.bookmark_extras_connect_axxon_profile(profile)

    @server.tool(name="update_bookmark")
    def update_bookmark(bookmark_id: str = "", message: str = "", confirmation: str = "") -> dict[str, Any]:
        """Update an existing bookmark's message via BookmarkService.UpdateBookmark (gated)."""
        return bookmark_extras.update_bookmark(bookmark_id=bookmark_id, message=message, confirmation=confirmation)

    @server.tool(name="set_bookmark_exported_time")
    def set_bookmark_exported_time(bookmark_id: str = "", exported_time: str = "", confirmation: str = "") -> dict[str, Any]:
        """Set a bookmark's exported time via BookmarkService.SetExportedTime (gated)."""
        return bookmark_extras.set_bookmark_exported_time(bookmark_id=bookmark_id, exported_time=exported_time, confirmation=confirmation)

    @server.tool(name="render_bookmark_track")
    def render_bookmark_track(bookmark_id: str = "") -> dict[str, Any]:
        """Render a bookmark's track via BookmarkService.RenderTrack."""
        return bookmark_extras.render_bookmark_track(bookmark_id=bookmark_id)


def register_security_credentials_tools(server: Any, security_credentials: Any) -> None:
    @server.tool(name="security_credentials_connect_axxon_profile")
    def security_credentials_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the SecurityService credential layer (changes need AXXON_SECURITY_CREDENTIALS_APPROVE=1)."""
        return security_credentials.security_credentials_connect_axxon_profile(profile)

    @server.tool(name="check_password")
    def check_password(user_id: str = "", password: str = "") -> dict[str, Any]:
        """Pre-check a password's uniqueness/policy for a user via SecurityService.CheckPassword."""
        return security_credentials.check_password(user_id=user_id, password=password)

    @server.tool(name="change_my_password")
    def change_my_password(password: str = "", confirmation: str = "") -> dict[str, Any]:
        """Change the connected session user's own password via SecurityService.ChangePassword (gated)."""
        return security_credentials.change_my_password(password=password, confirmation=confirmation)

    @server.tool(name="change_my_login")
    def change_my_login(login: str = "", confirmation: str = "") -> dict[str, Any]:
        """Change the connected session user's own login via SecurityService.ChangeLogin (gated)."""
        return security_credentials.change_my_login(login=login, confirmation=confirmation)


def register_auth_sessions_tools(server: Any, auth_sessions: Any) -> None:
    @server.tool(name="auth_sessions_connect_axxon_profile")
    def auth_sessions_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the AuthenticationService session layer (close needs AXXON_AUTH_SESSIONS_APPROVE=1)."""
        return auth_sessions.auth_sessions_connect_axxon_profile(profile)

    @server.tool(name="authenticate")
    def authenticate(user_name: str = "", password: str = "", variant: str = "Authenticate") -> dict[str, Any]:
        """Mint a session token via AuthenticationService.Authenticate/Authenticate2/AuthenticateEx (no token returned)."""
        return auth_sessions.authenticate(user_name=user_name, password=password, variant=variant)

    @server.tool(name="renew_session")
    def renew_session(variant: str = "RenewSession") -> dict[str, Any]:
        """Renew the connected session via AuthenticationService.RenewSession/RenewSession2 (no token returned)."""
        return auth_sessions.renew_session(variant=variant)

    @server.tool(name="close_session")
    def close_session(confirmation: str = "") -> dict[str, Any]:
        """Close the connected session via AuthenticationService.CloseSession (gated)."""
        return auth_sessions.close_session(confirmation=confirmation)


def register_layout_manager_tools(server: Any, layout_manager: Any) -> None:
    @server.tool(name="layout_manager_connect_axxon_profile")
    def layout_manager_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the LayoutManager layer (rename needs AXXON_LAYOUT_MANAGER_APPROVE=1)."""
        return layout_manager.layout_manager_connect_axxon_profile(profile)

    @server.tool(name="batch_get_layouts")
    def batch_get_layouts(layout_id: str = "", etag: str = "") -> dict[str, Any]:
        """Read a layout by id (etag-conditional) via LayoutManager.BatchGetLayouts."""
        return layout_manager.batch_get_layouts(layout_id=layout_id, etag=etag)

    @server.tool(name="layout_manager_layouts_on_view")
    def layout_manager_layouts_on_view(layout_id: str = "", display_name: str = "") -> dict[str, Any]:
        """Push a single layout to the view via LayoutManager.LayoutsOnView (by layout_id)."""
        return layout_manager.layouts_on_view(layout_id=layout_id, display_name=display_name)

    @server.tool(name="update_layout_name")
    def update_layout_name(layout_id: str = "", display_name: str = "", confirmation: str = "") -> dict[str, Any]:
        """Rename a layout via LayoutManager.Update (gated)."""
        return layout_manager.update_layout_name(layout_id=layout_id, display_name=display_name, confirmation=confirmation)


def register_license_reads_tools(server: Any, license_reads: Any) -> None:
    @server.tool(name="license_reads_connect_axxon_profile")
    def license_reads_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the LicenseService read layer (read-only license key + restrictions)."""
        return license_reads.license_reads_connect_axxon_profile(profile)

    @server.tool(name="get_license_key")
    def get_license_key() -> dict[str, Any]:
        """Report license key presence/length via LicenseService.LicenseKey (never returns the key)."""
        return license_reads.get_license_key()

    @server.tool(name="get_restrictions")
    def get_restrictions() -> dict[str, Any]:
        """Read license restrictions via LicenseService.Restrictions."""
        return license_reads.get_restrictions()


def register_misc_reads_tools(server: Any, misc_reads: Any) -> None:
    @server.tool(name="misc_reads_connect_axxon_profile")
    def misc_reads_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the cross-service misc layer (settings writes need AXXON_MISC_WRITE_APPROVE=1)."""
        return misc_reads.misc_reads_connect_axxon_profile(profile)

    @server.tool(name="acquire_dynamic_parameters")
    def acquire_dynamic_parameters(uid: str = "") -> dict[str, Any]:
        """Acquire a unit's dynamic parameters via DynamicParametersService.AcquireDynamicParameters."""
        return misc_reads.acquire_dynamic_parameters(uid=uid)

    @server.tool(name="acquire_device_additional_data")
    def acquire_device_additional_data(uid: str = "") -> dict[str, Any]:
        """Acquire a device's additional data via DynamicParametersService.AcquireDeviceAdditionalData."""
        return misc_reads.acquire_device_additional_data(uid=uid)

    @server.tool(name="probe_volume")
    def probe_volume(volume_type: str = "", node_name: str = "Server", connection_params: dict[str, str] | None = None) -> dict[str, Any]:
        """Probe an archive volume via ArchiveVolumeService.ProbeVolume."""
        return misc_reads.probe_volume(volume_type=volume_type, node_name=node_name, connection_params=connection_params)

    @server.tool(name="ping_node")
    def ping_node(timeout_ms: int = 1000) -> dict[str, Any]:
        """Ping a node via NodeNotifier.Ping."""
        return misc_reads.ping_node(timeout_ms=timeout_ms)

    @server.tool(name="get_generic_settings")
    def get_generic_settings(context: str = "") -> dict[str, Any]:
        """Read a generic-settings context via GenericSettingsService.GetSettings."""
        return misc_reads.get_generic_settings(context=context)

    @server.tool(name="save_generic_settings")
    def save_generic_settings(context: str = "", values: dict[str, str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Save a generic-settings context via GenericSettingsService.SaveSettings (gated)."""
        return misc_reads.save_generic_settings(context=context, values=values, confirmation=confirmation)

    @server.tool(name="remove_generic_settings")
    def remove_generic_settings(context: str = "", revision: str = "", confirmation: str = "") -> dict[str, Any]:
        """Remove a generic-settings context via GenericSettingsService.RemoveSettings (gated)."""
        return misc_reads.remove_generic_settings(context=context, revision=revision, confirmation=confirmation)


def register_heatmap_tools(server: Any, heatmap: Any) -> None:
    @server.tool(name="heatmap_connect_axxon_profile")
    def heatmap_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the HeatMapService read layer (object/event density maps from VMDA metadata)."""
        return heatmap.heatmap_connect_axxon_profile(profile)

    @server.tool(name="build_heatmap")
    def build_heatmap(camera_id: str = "", start_time: str = "", end_time: str = "", query: str = "",
                      builder_access_point: str = "", mask: int = 16, image_width: int = 320, image_height: int = 240) -> dict[str, Any]:
        """Build an object-density heatmap image for one camera over a window via HeatMapService.BuildHeatmap."""
        kwargs = {"camera_id": camera_id, "start_time": start_time, "end_time": end_time, "query": query, "mask": mask, "image_width": image_width, "image_height": image_height}
        if builder_access_point:
            kwargs["builder_access_point"] = builder_access_point
        return heatmap.build_heatmap(**kwargs)

    @server.tool(name="build_events_heatmap")
    def build_events_heatmap(start_time: str = "", end_time: str = "", builder_access_point: str = "",
                             mask: int = 16, image_width: int = 320, image_height: int = 240) -> dict[str, Any]:
        """Build a server-wide event-density heatmap image via HeatMapService.BuildEventsHeatmap."""
        kwargs = {"start_time": start_time, "end_time": end_time, "mask": mask, "image_width": image_width, "image_height": image_height}
        if builder_access_point:
            kwargs["builder_access_point"] = builder_access_point
        return heatmap.build_events_heatmap(**kwargs)

    @server.tool(name="build_floor_heatmap")
    def build_floor_heatmap(camera_id: str = "", start_time: str = "", end_time: str = "", query: str = "",
                            map_guid: str = "", builder_access_point: str = "", mask: int = 16, image_width: int = 320, image_height: int = 240) -> dict[str, Any]:
        """Build a floor-projected heatmap from a camera's VMDA data source via HeatMapService.BuildFloorHeatmap."""
        kwargs = {"camera_id": camera_id, "start_time": start_time, "end_time": end_time, "query": query, "map_guid": map_guid, "mask": mask, "image_width": image_width, "image_height": image_height}
        if builder_access_point:
            kwargs["builder_access_point"] = builder_access_point
        return heatmap.build_floor_heatmap(**kwargs)

    @server.tool(name="execute_heatmap_query")
    def execute_heatmap_query(camera_id: str = "", start_time: str = "", end_time: str = "", query: str = "", max_responses: int = 8) -> dict[str, Any]:
        """Stream raw heatmap intervals for a camera's VMDA query via HeatMapService.ExecuteHeatmapQuery."""
        return heatmap.execute_heatmap_query(camera_id=camera_id, start_time=start_time, end_time=end_time, query=query, max_responses=max_responses)

    @server.tool(name="execute_heatmap_query_typed")
    def execute_heatmap_query_typed(camera_id: str = "", start_time: str = "", end_time: str = "", max_responses: int = 8) -> dict[str, Any]:
        """Stream raw heatmap intervals via a typed motion-in-area query (HeatMapService.ExecuteHeatmapQueryTyped)."""
        return heatmap.execute_heatmap_query_typed(camera_id=camera_id, start_time=start_time, end_time=end_time, max_responses=max_responses)


def register_media_tools(server: Any, media: Any) -> None:
    @server.tool(name="media_connect_axxon_profile")
    def media_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the MediaService transport-probe layer (connection/QoS/tunnel/stream probes)."""
        return media.media_connect_axxon_profile(profile)

    @server.tool(name="request_connection")
    def request_connection(endpoint: str = "", pid: int = 0, host_id: str = "Server") -> dict[str, Any]:
        """Request a transport cookie + connection info for a media endpoint via MediaService.RequestConnection."""
        return media.request_connection(endpoint=endpoint, pid=pid, host_id=host_id)

    @server.tool(name="request_qos")
    def request_qos(endpoint: str = "", fps: float = 5.0) -> dict[str, Any]:
        """Apply a frame-rate QoS hint to a media connection via MediaService.RequestQoS."""
        return media.request_qos(endpoint=endpoint, fps=fps)

    @server.tool(name="request_tunnel")
    def request_tunnel(node: str = "Server", name: str = "") -> dict[str, Any]:
        """Open an RPC tunnel to a node and report its transport config via MediaService.RequestTunnel."""
        return media.request_tunnel(node=node, name=name)

    @server.tool(name="stream_probe")
    def stream_probe(endpoint: str = "", max_samples: int = 4, channel_idle_ms: int = 5000) -> dict[str, Any]:
        """Open the pull stream for a media endpoint and tally sample types via MediaService.Stream."""
        return media.stream_probe(endpoint=endpoint, max_samples=max_samples, channel_idle_ms=channel_idle_ms)

    @server.tool(name="connect_endpoint")
    def connect_endpoint(source_endpoint: str = "", sink_endpoint: str = "", priority: int = 1) -> dict[str, Any]:
        """Connect a media producer (mic) to a consumer (speaker) and report status via MediaService.ConnectEndpoint."""
        return media.connect_endpoint(source_endpoint=source_endpoint, sink_endpoint=sink_endpoint, priority=priority)


def register_web_api_tools(server: Any, web_api: Any) -> None:
    @server.tool(name="web_api_connect_axxon_profile")
    def web_api_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the Web server / embeddable-component / WebSocket-event helper layer (read-only)."""
        return web_api.web_api_connect_axxon_profile(profile)

    @server.tool(name="embeddable_component_url")
    def embeddable_component_url(camera_origin: str = "", mode: str = "live", time: str = "", archive_pane: bool | None = None) -> dict[str, Any]:
        """Build the /embedded.html iframe src + snippet for the embeddable video component (no credentials)."""
        return web_api.embeddable_component_url(camera_origin=camera_origin, mode=mode, time=time, archive_pane=archive_pane)

    @server.tool(name="embeddable_component_commands")
    def embeddable_component_commands() -> dict[str, Any]:
        """Return the typed postMessage command catalog for the embeddable video component (knowledge only)."""
        return web_api.embeddable_component_commands()

    @server.tool(name="web_events_probe")
    def web_events_probe(path: str = "/events") -> dict[str, Any]:
        """Perform one bounded WebSocket handshake against a known event path; report 101/upgrade metadata only."""
        return web_api.web_events_probe(path=path)

    @server.tool(name="web_events_sample")
    def web_events_sample(path: str = "/events", max_frames: int = 8) -> dict[str, Any]:
        """Open one bounded WS connection and report frame count + opcode/size tallies (no raw payload bytes)."""
        return web_api.web_events_sample(path=path, max_frames=max_frames)

    @server.tool(name="web_client_parity_report")
    def web_client_parity_report() -> dict[str, Any]:
        """Map the Web client surface to existing MCP groups, highlighting browser-only pieces (offline)."""
        return web_api.web_client_parity_report()


def register_client_api_tools(server: Any, client_api: Any) -> None:
    @server.tool(name="client_api_connect_axxon_profile")
    def client_api_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the Client HTTP API preflight layer to the env profile (read-only)."""
        return client_api.client_api_connect_axxon_profile(profile)

    @server.tool(name="client_api_preflight")
    def client_api_preflight(client_http_port: int = 8888) -> dict[str, Any]:
        """Socket-probe the Client HTTP API port locally and on the configured host; report reachability (no mutation)."""
        return client_api.client_api_preflight(client_http_port=client_http_port)

    @server.tool(name="list_client_api_operations")
    def list_client_api_operations() -> dict[str, Any]:
        """Catalog Client HTTP API operations (SwitchLayout/AddCameraToDisplay/...), each marked fixture-needed."""
        return client_api.list_client_api_operations()


def register_export_tools(server: Any, export: Any) -> None:
    @server.tool(name="export_connect_axxon_profile")
    def export_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the ExportService layer to the env profile; responses are metadata-only."""
        return export.export_connect_axxon_profile(profile)

    @server.tool(name="export_plan_snapshot")
    def export_plan_snapshot(
        camera_access_point: str = "",
        archive_access_point: str = "",
        timestamp: str = "",
        max_file_size: int = 1_048_576,
        max_download_bytes: int = 262_144,
        max_chunks: int = 16,
        chunk_size_kb: int = 64,
        timeout_s: float = 10.0,
        filename_stem: str = "",
    ) -> dict[str, Any]:
        """Plan a short archived JPEG snapshot export without starting a session."""
        return export.export_plan_snapshot(
            camera_access_point=camera_access_point,
            archive_access_point=archive_access_point,
            timestamp=timestamp,
            max_file_size=max_file_size,
            max_download_bytes=max_download_bytes,
            max_chunks=max_chunks,
            chunk_size_kb=chunk_size_kb,
            timeout_s=timeout_s,
            filename_stem=filename_stem,
        )

    @server.tool(name="export_start_snapshot")
    def export_start_snapshot(
        camera_access_point: str = "",
        archive_access_point: str = "",
        timestamp: str = "",
        confirmation: str = "",
        max_file_size: int = 1_048_576,
        max_download_bytes: int = 262_144,
        max_chunks: int = 16,
        chunk_size_kb: int = 64,
        timeout_s: float = 10.0,
        filename_stem: str = "",
    ) -> dict[str, Any]:
        """Start an owned snapshot export. Requires AXXON_EXPORT_APPROVE=1 and CONFIRM-export."""
        return export.export_start_snapshot(
            camera_access_point=camera_access_point,
            archive_access_point=archive_access_point,
            timestamp=timestamp,
            confirmation=confirmation,
            max_file_size=max_file_size,
            max_download_bytes=max_download_bytes,
            max_chunks=max_chunks,
            chunk_size_kb=chunk_size_kb,
            timeout_s=timeout_s,
            filename_stem=filename_stem,
        )

    @server.tool(name="export_status")
    def export_status(session_id: str = "") -> dict[str, Any]:
        """Read bounded ExportService state for an owned session."""
        return export.export_status(session_id=session_id)

    @server.tool(name="export_download")
    def export_download(
        session_id: str = "",
        file_path: str = "",
        confirmation: str = "",
        destination_name: str = "",
        max_bytes: int = 262_144,
        max_chunks: int = 16,
        chunk_size_kb: int = 64,
        timeout_s: float = 10.0,
        save: bool = True,
    ) -> dict[str, Any]:
        """Download an owned export file under caps, optionally saving under the module artifact root."""
        return export.export_download(
            session_id=session_id,
            file_path=file_path,
            confirmation=confirmation,
            destination_name=destination_name,
            max_bytes=max_bytes,
            max_chunks=max_chunks,
            chunk_size_kb=chunk_size_kb,
            timeout_s=timeout_s,
            save=save,
        )

    @server.tool(name="export_stop")
    def export_stop(session_id: str = "", confirmation: str = "") -> dict[str, Any]:
        """Stop an owned export session. Requires AXXON_EXPORT_APPROVE=1 and CONFIRM-export."""
        return export.export_stop(session_id=session_id, confirmation=confirmation)

    @server.tool(name="export_destroy")
    def export_destroy(session_id: str = "", confirmation: str = "") -> dict[str, Any]:
        """Destroy an owned export session. Requires AXXON_EXPORT_APPROVE=1 and CONFIRM-export."""
        return export.export_destroy(session_id=session_id, confirmation=confirmation)

    @server.tool(name="export_cleanup_owned")
    def export_cleanup_owned(confirmation: str = "", stop_running: bool = True, destroy: bool = True) -> dict[str, Any]:
        """Stop/destroy only sessions owned by this export tool and report cleanup counts."""
        return export.export_cleanup_owned(confirmation=confirmation, stop_running=stop_running, destroy=destroy)


def register_recognizer_tools(server: Any, recognizer: Any) -> None:
    @server.tool(name="recognizer_connect_axxon_profile")
    def recognizer_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the read-only face/LPR watchlist layer to the env profile."""
        return recognizer.recognizer_connect_axxon_profile(profile)

    @server.tool(name="list_recognizer_lists")
    def list_recognizer_lists(list_type: str = "any") -> dict[str, Any]:
        """List face/LPR recognition watchlists (id, name, type, item count). list_type: any/face/lpr/food."""
        return recognizer.list_recognizer_lists(list_type)

    @server.tool(name="get_recognizer_list")
    def get_recognizer_list(list_id: str) -> dict[str, Any]:
        """Get one watchlist descriptor via GetListStream."""
        return recognizer.get_recognizer_list(list_id)

    @server.tool(name="list_recognizer_items")
    def list_recognizer_items(limit: int = 200) -> dict[str, Any]:
        """List enrolled items (people/plates) node-wide as privacy-safe metadata: no images, no biometric vectors."""
        return recognizer.list_recognizer_items(limit)


def register_recognizer_write_tools(server: Any, recognizer_write: Any) -> None:
    @server.tool(name="recognizer_write_connect_axxon_profile")
    def recognizer_write_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the approval-gated watchlist write layer to the env profile."""
        return recognizer_write.recognizer_write_connect_axxon_profile(profile)

    @server.tool(name="recognizer_change_lists")
    def recognizer_change_lists(
        added: list[dict[str, Any]] | None = None,
        changed: list[dict[str, Any]] | None = None,
        removed_ids: list[str] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Add/change/remove watchlists via ChangeLists. Gated by approval env + confirmation token."""
        return recognizer_write.recognizer_change_lists(added, changed, removed_ids, confirmation)

    @server.tool(name="recognizer_change_lists_stream")
    def recognizer_change_lists_stream(
        added: list[dict[str, Any]] | None = None,
        changed: list[dict[str, Any]] | None = None,
        removed_ids: list[str] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Add/change/remove watchlists via the streaming ChangeListsStream (proto-preferred). Gated."""
        return recognizer_write.recognizer_change_lists_stream(added, changed, removed_ids, confirmation)

    @server.tool(name="recognizer_change_items")
    def recognizer_change_items(
        list_id: str = "",
        added: list[dict[str, Any]] | None = None,
        removed_item_ids: list[str] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Add/remove LPR items via ChangeItems (string plates only, no biometric payloads). Gated."""
        return recognizer_write.recognizer_change_items(list_id, added, removed_item_ids, confirmation)

    @server.tool(name="recognizer_clear")
    def recognizer_clear(node_name: str = "", confirmation: str = "", clear_ack: str = "") -> dict[str, Any]:
        """Wipe ALL lists/items on a node via Clear. Irreversible: needs confirmation + clear_ack tokens."""
        return recognizer_write.recognizer_clear(node_name, confirmation, clear_ack)


def register_logic_control_tools(server: Any, logic_control: Any) -> None:
    @server.tool(name="logic_control_connect_axxon_profile")
    def logic_control_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the approval-gated LogicService control layer to the env profile."""
        return logic_control.logic_control_connect_axxon_profile(profile)

    @server.tool(name="list_launchable_macros")
    def list_launchable_macros() -> dict[str, Any]:
        """List macros via ListMacros, flagging which are manually launchable (vs detector autorules)."""
        return logic_control.list_launchable_macros()

    @server.tool(name="launch_macro")
    def launch_macro(macro_id: str = "", confirmation: str = "") -> dict[str, Any]:
        """Run a configured macro by id via LaunchMacro. Gated by approval env + confirmation token."""
        return logic_control.launch_macro(macro_id, confirmation)

    @server.tool(name="change_arm_state")
    def change_arm_state(camera_ap: str = "", state: str = "", timeout_s: int = 0, confirmation: str = "") -> dict[str, Any]:
        """Arm/disarm a camera (disarm/arm/arm_private) for a bounded, auto-reverting window via ChangeArmState."""
        return logic_control.change_arm_state(camera_ap, state, timeout_s, confirmation)

    @server.tool(name="change_config")
    def change_config(overrides: dict[str, int] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Override LogicService alert/event TTL fields via ChangeConfig (round-trippable). Gated by approval env + confirmation."""
        return logic_control.change_config(overrides, confirmation)

    @server.tool(name="change_counters")
    def change_counters(add: dict[str, str] | None = None, remove_guid: str = "", confirmation: str = "") -> dict[str, Any]:
        """Add a counter (add={guid,name}) or remove one (remove_guid) via ChangeCounters. Gated by approval env + confirmation."""
        return logic_control.change_counters(add, remove_guid, confirmation)

    @server.tool(name="counter_action")
    def counter_action(counter: str = "", operation: str = "start", confirmation: str = "") -> dict[str, Any]:
        """Run START/STOP/CLEANUP on a counter guid via CounterAction. Gated by approval env + confirmation."""
        return logic_control.counter_action(counter, operation, confirmation)


def register_videowall_tools(server: Any, videowall: Any) -> None:
    @server.tool(name="videowall_connect_axxon_profile")
    def videowall_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the approval-gated VideowallService control layer to the env profile."""
        return videowall.videowall_connect_axxon_profile(profile)

    @server.tool(name="videowall_list_walls")
    def videowall_list_walls() -> dict[str, Any]:
        """List registered videowall coordinators via VideowallService.ListWalls."""
        return videowall.list_walls()

    @server.tool(name="register_wall")
    def register_wall(name: str = "", display_name: str = "", host_name: str = "axxon-mcp", confirmation: str = "") -> dict[str, Any]:
        """Register a videowall via RegisterWall; returns cookie_present + wall_id (no raw cookie). Gated by approval env + confirmation."""
        return videowall.register_wall(name, display_name, host_name, confirmation)

    @server.tool(name="change_wall")
    def change_wall(wall_id: str = "", seq_number: int = 0, data: bytes = b"", confirmation: str = "") -> dict[str, Any]:
        """Update a registered wall payload via ChangeWall (by wall_id). Gated by approval env + confirmation."""
        return videowall.change_wall(wall_id, seq_number, data, confirmation)

    @server.tool(name="set_control_data")
    def set_control_data(wall_id: str = "", seq_number: int = 0, data: bytes = b"", confirmation: str = "") -> dict[str, Any]:
        """Push control data to a wall via SetControlData (by wall_id + seq_number). Gated by approval env + confirmation."""
        return videowall.set_control_data(wall_id, seq_number, data, confirmation)

    @server.tool(name="unregister_wall")
    def unregister_wall(wall_id: str = "", confirmation: str = "") -> dict[str, Any]:
        """Unregister a videowall via UnregisterWall (by wall_id), reversing register_wall. Gated by approval env + confirmation."""
        return videowall.unregister_wall(wall_id, confirmation)


def register_settings_tools(server: Any, settings: Any) -> None:
    @server.tool(name="settings_connect_axxon_profile")
    def settings_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the data-storage settings layer to the env profile."""
        return settings.settings_connect_axxon_profile(profile)

    @server.tool(name="get_data_storage_settings")
    def get_data_storage_settings() -> dict[str, Any]:
        """Read data-storage settings (system-logs + VMDA retention/cleanup, seconds) and etag."""
        return settings.get_data_storage_settings()

    @server.tool(name="update_data_storage_settings")
    def update_data_storage_settings(
        system_logs_retention_s: int | None = None,
        system_logs_cleanup_s: int | None = None,
        vmda_retention_s: int | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Update only the provided data-storage durations (field-masked, etag-managed). Gated."""
        return settings.update_data_storage_settings(system_logs_retention_s, system_logs_cleanup_s, vmda_retention_s, confirmation)

    @server.tool(name="get_bookmark_settings")
    def get_bookmark_settings() -> dict[str, Any]:
        """Read bookmark settings (mandatory_protection, max duration, retention period) + etag."""
        return settings.get_bookmark_settings()

    @server.tool(name="update_bookmark_settings")
    def update_bookmark_settings(
        mandatory_protection: bool | None = None,
        bookmark_max_duration_s: int | None = None,
        retention_period_s: int | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Update only the provided bookmark settings (field-masked, etag-managed). Gated."""
        return settings.update_bookmark_settings(mandatory_protection, bookmark_max_duration_s, retention_period_s, confirmation)

    @server.tool(name="get_gdpr_settings")
    def get_gdpr_settings() -> dict[str, Any]:
        """Read GDPR privacy-mask setting (unspecified/mosaic/black) + etag."""
        return settings.get_gdpr_settings()

    @server.tool(name="update_gdpr_settings")
    def update_gdpr_settings(privacy_mask_type: str = "", confirmation: str = "") -> dict[str, Any]:
        """Set the GDPR privacy-mask type (unspecified/mosaic/black), field-masked + etag-managed. Gated."""
        return settings.update_gdpr_settings(privacy_mask_type, confirmation)


def register_timezone_tools(server: Any, timezone: Any) -> None:
    @server.tool(name="timezone_connect_axxon_profile")
    def timezone_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the timezone/NTP layer to the env profile."""
        return timezone.timezone_connect_axxon_profile(profile)

    @server.tool(name="list_timezones")
    def list_timezones(full: bool = False) -> dict[str, Any]:
        """List the timezone database entries (full=True includes intervals)."""
        return timezone.list_timezones(full)

    @server.tool(name="get_timezone")
    def get_timezone() -> dict[str, Any]:
        """Read the current OS timezone, DST mode, and available timezones."""
        return timezone.get_timezone()

    @server.tool(name="get_ntp")
    def get_ntp() -> dict[str, Any]:
        """Read the NTP sync settings (url, sync_ip_devices, refresh rate seconds)."""
        return timezone.get_ntp()

    @server.tool(name="set_timezone")
    def set_timezone(timezone_id: str = "", daylight_saving_mode_off: bool | None = None, confirmation: str = "") -> dict[str, Any]:
        """Set the OS timezone (and optional DST-off), then read it back. Gated."""
        return timezone.set_timezone(timezone_id, daylight_saving_mode_off, confirmation)

    @server.tool(name="set_ntp")
    def set_ntp(ntp_url: str = "", sync_ip_devices: bool = False, refresh_rate_s: int | None = None, confirmation: str = "") -> dict[str, Any]:
        """Set the NTP server (url, device sync, optional refresh seconds). Gated."""
        return timezone.set_ntp(ntp_url, sync_ip_devices, refresh_rate_s, confirmation)

    @server.tool(name="change_timezones")
    def change_timezones(
        removed_zones: list[str] | None = None,
        added_zones: list[dict[str, str]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Edit the timezone database: remove zone ids and/or add {id,name} zones. Gated."""
        return timezone.change_timezones(removed_zones, added_zones, confirmation)


def register_server_settings_tools(server: Any, server_settings: Any) -> None:
    @server.tool(name="server_connect_axxon_profile")
    def server_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the ServerSettings layer to the env profile."""
        return server_settings.server_connect_axxon_profile(profile)

    @server.tool(name="get_log_level")
    def get_log_level(nodes: list[str] | None = None) -> dict[str, Any]:
        """Read the per-node server log level (empty nodes = current node)."""
        return server_settings.get_log_level(nodes)

    @server.tool(name="set_log_level")
    def set_log_level(level: str = "", nodes: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Set the server log level (e.g. LOG_LEVEL_INFO), then read it back. Gated."""
        return server_settings.set_log_level(level, nodes, confirmation)

    @server.tool(name="drop_logs")
    def drop_logs(nodes: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        """Permanently delete server log history for the given nodes. Gated, irreversible."""
        return server_settings.drop_logs(nodes, confirmation)


def register_statistics_tools(server: Any, statistics: Any) -> None:
    @server.tool(name="statistics_connect_axxon_profile")
    def statistics_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the StatisticService layer to the env profile."""
        return statistics.statistics_connect_axxon_profile(profile)

    @server.tool(name="get_statistics")
    def get_statistics(keys: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Read server/stream statistics (CPU/disk/FPS/bitrate health); empty keys = all points."""
        return statistics.get_statistics(keys)


def register_event_taxonomy_tools(server: Any, event_taxonomy: Any) -> None:
    @server.tool(name="event_taxonomy_connect_axxon_profile")
    def event_taxonomy_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the EventDescription layer to the env profile."""
        return event_taxonomy.event_taxonomy_connect_axxon_profile(profile)

    @server.tool(name="get_event_grouping_tags")
    def get_event_grouping_tags() -> dict[str, Any]:
        """Read event grouping tags (field descriptors used to group/filter events)."""
        return event_taxonomy.get_event_grouping_tags()


def register_scene_description_tools(server: Any, scene_description: Any) -> None:
    @server.tool(name="scene_description_connect_axxon_profile")
    def scene_description_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the NgpNodeService layer to the env profile."""
        return scene_description.scene_description_connect_axxon_profile(profile)

    @server.tool(name="list_scene_description")
    def list_scene_description(page_token: str = "", page_size: int = 0) -> dict[str, Any]:
        """List per-camera scene descriptions (one page); page_size=0 lets the server choose."""
        return scene_description.list_scene_description(page_token, page_size)


def register_package_availability_tools(server: Any, package_availability: Any) -> None:
    @server.tool(name="package_availability_connect_axxon_profile")
    def package_availability_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the InstallationPackageProvider layer to the env profile."""
        return package_availability.package_availability_connect_axxon_profile(profile)

    @server.tool(name="check_package_availability")
    def check_package_availability(system: str = "Linux", machine: str = "") -> dict[str, Any]:
        """Check installer-package availability for an OS ("Windows"|"Linux") and optional machine."""
        return package_availability.check_package_availability(system, machine)


def register_domain_topology_tools(server: Any, domain_topology: Any) -> None:
    @server.tool(name="domain_topology_connect_axxon_profile")
    def domain_topology_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the DomainManager layer to the env profile."""
        return domain_topology.domain_topology_connect_axxon_profile(profile)

    @server.tool(name="enumerate_nodes")
    def enumerate_nodes() -> dict[str, Any]:
        """Enumerate the domain and its member / free / other nodes (read-only)."""
        return domain_topology.enumerate_nodes()


def register_config_revisions_tools(server: Any, config_revisions: Any) -> None:
    @server.tool(name="config_revisions_connect_axxon_profile")
    def config_revisions_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the ConfigurationManager layer to the env profile."""
        return config_revisions.config_revisions_connect_axxon_profile(profile)

    @server.tool(name="get_revision_info")
    def get_revision_info(config_type: str = "LOCAL_CONFIG", nodes: list[str] | None = None) -> dict[str, Any]:
        """Read config revision history per node ("LOCAL_CONFIG"|"SHARED_CONFIG")."""
        return config_revisions.get_revision_info(config_type, nodes)

    @server.tool(name="collect_backup_probe")
    def collect_backup_probe(
        types: list[str] | None = None,
        node: str = "",
        max_chunks: int | None = None,
        max_bytes: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Probe backup collectibility and tally size (chunk/byte/time capped); blob never returned."""
        return config_revisions.collect_backup_probe(types, node, max_chunks, max_bytes, timeout)


def register_filesystem_browser_tools(server: Any, filesystem_browser: Any) -> None:
    @server.tool(name="filesystem_browser_connect_axxon_profile")
    def filesystem_browser_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the FileSystemBrowser layer to the env profile."""
        return filesystem_browser.filesystem_browser_connect_axxon_profile(profile)

    @server.tool(name="list_directory")
    def list_directory(path: str = "", node_name: str = "", type: str = "", name_pattern: str = "", page_size: int | None = None, page_token: str = "") -> dict[str, Any]:
        """List a server-side directory (entry-capped); empty path lists the root."""
        return filesystem_browser.list_directory(path, node_name, type, name_pattern, page_size, page_token)

    @server.tool(name="get_file_info")
    def get_file_info(path: str = "", node_name: str = "") -> dict[str, Any]:
        """Read info for one file or directory (path, type, perms, size, parent path)."""
        return filesystem_browser.get_file_info(path, node_name)

    @server.tool(name="get_space")
    def get_space(path: str = "", node_name: str = "") -> dict[str, Any]:
        """Read filesystem capacity and free space for a path."""
        return filesystem_browser.get_space(path, node_name)


def register_devices_catalog_tools(server: Any, devices_catalog: Any) -> None:
    @server.tool(name="devices_catalog_connect_axxon_profile")
    def devices_catalog_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the DevicesCatalog layer to the env profile."""
        return devices_catalog.devices_catalog_connect_axxon_profile(profile)

    @server.tool(name="list_vendors")
    def list_vendors(category: str = "", filter: str = "", node_name: str = "") -> dict[str, Any]:
        """List supported device vendors, optionally filtered by category and text."""
        return devices_catalog.list_vendors(category, filter, node_name)

    @server.tool(name="list_vendors_v2")
    def list_vendors_v2(category: str = "", filter: str = "", node_name: str = "", max_pages: int | None = None) -> dict[str, Any]:
        """Stream supported device vendors (page-capped), de-duplicated across pages."""
        return devices_catalog.list_vendors_v2(category, filter, node_name, max_pages)

    @server.tool(name="list_devices")
    def list_devices(category: str = "", vendor: str = "", filter: str = "", node_name: str = "") -> dict[str, Any]:
        """List supported device models, optionally filtered by category/vendor/text."""
        return devices_catalog.list_devices(category, vendor, filter, node_name)

    @server.tool(name="list_devices_v2")
    def list_devices_v2(category: str = "", vendor: str = "", filter: str = "", node_name: str = "", max_pages: int | None = None) -> dict[str, Any]:
        """Stream supported device models (page-capped)."""
        return devices_catalog.list_devices_v2(category, vendor, filter, node_name, max_pages)

    @server.tool(name="get_device")
    def get_device(vendor: str = "", model: str = "", node_name: str = "") -> dict[str, Any]:
        """Read one supported model's traits; both vendor and model are required."""
        return devices_catalog.get_device(vendor, model, node_name)


def register_global_tracker_tools(server: Any, global_tracker: Any) -> None:
    @server.tool(name="global_tracker_connect_axxon_profile")
    def global_tracker_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the GlobalTrackerService layer to the env profile."""
        return global_tracker.global_tracker_connect_axxon_profile(profile)

    @server.tool(name="get_profile")
    def get_profile(profile_id: str = "", max_items: int | None = None) -> dict[str, Any]:
        """Read a global-tracker profile by id (metadata only; images never loaded/returned)."""
        return global_tracker.get_profile(profile_id, max_items)


def register_shared_kv_tools(server: Any, shared_kv: Any) -> None:
    @server.tool(name="shared_kv_connect_axxon_profile")
    def shared_kv_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the SharedKVStorageService layer to the env profile."""
        return shared_kv.shared_kv_connect_axxon_profile(profile)

    @server.tool(name="list_records")
    def list_records(prefix: str = "", view: str = "") -> dict[str, Any]:
        """List shared-KV records under a key prefix (reads are ungated)."""
        return shared_kv.list_records(prefix, view)

    @server.tool(name="get_records")
    def get_records(keys: list[str] | None = None, prefix: str = "", view: str = "") -> dict[str, Any]:
        """Batch-read specific shared-KV records by key (optionally under a prefix)."""
        return shared_kv.get_records(keys, prefix, view)

    @server.tool(name="get_records_stream")
    def get_records_stream(prefix: str = "", view: str = "", max_chunks: int | None = None) -> dict[str, Any]:
        """Stream shared-KV record chunks under a prefix (chunk-capped); values not returned."""
        return shared_kv.get_records_stream(prefix, view, max_chunks)

    @server.tool(name="commit_record")
    def commit_record(
        prefix: str = "",
        set_records: list[dict[str, Any]] | None = None,
        removed: list[dict[str, Any]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Commit shared-KV records (set/remove); gated by AXXON_SHARED_KV_APPROVE=1 + confirmation token."""
        return shared_kv.commit_record(prefix, set_records, removed, confirmation)


def register_state_control_tools(server: Any, state_control: Any) -> None:
    @server.tool(name="state_control_connect_axxon_profile")
    def state_control_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the StateControlService layer to the env profile."""
        return state_control.state_control_connect_axxon_profile(profile)

    @server.tool(name="get_current_state")
    def get_current_state(access_point: str = "") -> dict[str, Any]:
        """Read the current state directive result for a state-controllable access point."""
        return state_control.get_current_state(access_point)

    @server.tool(name="get_default_state")
    def get_default_state(access_point: str = "") -> dict[str, Any]:
        """Read the default state directive result for a state-controllable access point."""
        return state_control.get_default_state(access_point)

    @server.tool(name="set_state")
    def set_state(access_point: str = "", directive: str = "STATE_DIRECTIVE_NEUTRAL", priority: str = "PRIORITY_USER", confirmation: str = "") -> dict[str, Any]:
        """Set a device state directive (reversible). Gated by AXXON_STATE_CONTROL_APPROVE=1 + confirmation."""
        return state_control.set_state(access_point, directive, priority, confirmation)


def register_site_graph_tools(server: Any, site_graph: Any) -> None:
    @server.tool(name="site_graph_connect_axxon_profile")
    def site_graph_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the read-only site graph layer to the env profile."""
        return site_graph.site_graph_connect_axxon_profile(profile)

    @server.tool(name="build_site_graph")
    def build_site_graph(
        include_layouts: bool = True,
        include_maps: bool = True,
        include_permissions: bool = True,
        include_health: bool = True,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Build a unified read-only graph of cameras, archives, detectors, maps, permissions, and health."""
        return site_graph.build_site_graph(include_layouts, include_maps, include_permissions, include_health, limit)


def register_groups_tools(server: Any, groups: Any) -> None:
    @server.tool(name="groups_connect_axxon_profile")
    def groups_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the GroupManager layer to the env profile."""
        return groups.groups_connect_axxon_profile(profile)

    @server.tool(name="list_groups")
    def list_groups(tree: bool = False) -> dict[str, Any]:
        """List object groups ({group_id,name,parent,description}); tree=True for tree view."""
        return groups.list_groups(tree)

    @server.tool(name="change_groups")
    def change_groups(
        removed_groups: list[str] | None = None,
        added_groups: list[dict[str, str]] | None = None,
        changed_groups: list[dict[str, str]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Edit the group tree: remove ids and/or add/change {group_id,name,parent,description} groups. Gated."""
        return groups.change_groups(removed_groups, added_groups, changed_groups, confirmation)

    @server.tool(name="set_objects_membership")
    def set_objects_membership(
        added: list[dict[str, str]] | None = None,
        removed: list[dict[str, str]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Add/remove object membership in groups via {group_id,object} pairs. Gated."""
        return groups.set_objects_membership(added, removed, confirmation)


def register_partner_tools(server: Any, kit: Any) -> None:
    import os

    from axxon_mcp_generator import allow_in_repo_write

    @server.tool(name="scaffold_plugin")
    def scaffold_plugin(name: str, output_dir: str, language: str = "python") -> dict[str, Any]:
        """Generate a runnable partner plugin repo to a chosen directory."""
        target = Path(output_dir).expanduser().resolve()
        allow_in_repo = os.environ.get("AXXON_GENERATOR_ALLOW_IN_REPO") == "1"
        if not allow_in_repo_write(target, allow=allow_in_repo):
            return {
                "status": "refused",
                "reason": "in_repo_write_blocked",
                "detail": f"{target} is inside the repo; set AXXON_GENERATOR_ALLOW_IN_REPO=1 to override",
            }
        result = kit.scaffold_plugin(name, language)
        if result["status"] != "ok":
            return result
        target.mkdir(parents=True, exist_ok=True)
        for rel, content in result["files"].items():
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        return {"status": "ok", "output_dir": str(target), "name": name, "language": language, "files": sorted(result["files"])}

    @server.tool(name="plugin_lint")
    def plugin_lint(path: str) -> dict[str, Any]:
        """Lint a plugin repo: static verifier plus env-example/test/README-safety checks."""
        return kit.plugin_lint(path)

    @server.tool(name="plugin_package")
    def plugin_package(path: str, output: str, fmt: str = "zip", version: str = "0.0.0") -> dict[str, Any]:
        """Package a clean plugin repo into a versioned archive with an embedded SHA-256 manifest."""
        return kit.plugin_package(path, fmt, output, version)


def register_operator_tools(server: Any, operator: Any) -> None:
    @server.tool(name="list_operator_workflows")
    def list_operator_workflows() -> dict[str, Any]:
        """List operator workflows supported by this MCP server."""
        return {"workflows": operator.known_workflows()}

    @server.tool(name="execute_operator_workflow")
    def execute_operator_workflow(workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Compatibility planner that never applies mutations.

        Review the returned plan, then call apply_operator_plan explicitly with its plan_id
        and confirmation token. This boundary is the same for reversible and irreversible
        workflows.
        """
        return operator.execute(workflow, params or {})

    @server.tool(name="plan_operator_workflow")
    def plan_operator_workflow(workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build a typed mutation plan without calling the server."""
        return operator.plan(workflow, params or {})

    @server.tool(name="apply_operator_plan")
    def apply_operator_plan(plan_id: str, confirmation: str) -> dict[str, Any]:
        """Execute a previously planned workflow when confirmation matches and mutations are enabled."""
        return operator.apply(plan_id, confirmation)

    @server.tool(name="verify_operator_plan")
    def verify_operator_plan(plan_id: str) -> dict[str, Any]:
        """Report current presence of objects created by an applied plan."""
        return operator.verify(plan_id)

    @server.tool(name="rollback_operator_plan")
    def rollback_operator_plan(plan_id: str, confirmation: str) -> dict[str, Any]:
        """Remove every object created by an applied plan when confirmation matches."""
        return operator.rollback(plan_id, confirmation)

    @server.resource("axxon://operator/audit-log")
    def read_audit_log() -> dict[str, Any]:
        """Read the in-memory audit log for this operator session."""
        return {"entries": operator.audit_log()}


def register_live_tools(server: Any, live: Any) -> None:
    @server.tool(name="connect_axxon_profile")
    def connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect to an Axxon profile from environment-backed settings."""
        return live.connect_axxon_profile(profile)

    @server.tool(name="list_cameras")
    def list_cameras(filter_text: str | None = None, limit: int = 100) -> dict[str, Any]:
        """List cameras from the connected Axxon server using read-only APIs."""
        return live.list_cameras(filter_text, limit)

    @server.tool(name="list_archives")
    def list_archives(filter_text: str | None = None, limit: int = 100) -> dict[str, Any]:
        """List archives from the connected Axxon server using read-only APIs."""
        return live.list_archives(filter_text, limit)

    @server.tool(name="list_config_units")
    def list_config_units(filter_text: str | None = None, limit: int = 100) -> dict[str, Any]:
        """List summarized configuration units from the connected Axxon server."""
        return live.list_config_units(filter_text, limit)

    @server.tool(name="list_detectors")
    def list_detectors(camera_or_host: str | None = None, limit: int = 100) -> dict[str, Any]:
        """List AVDetector tracker units and components from the connected server."""
        return live.list_detectors(camera_or_host, limit)

    @server.tool(name="list_appdata_detectors")
    def list_appdata_detectors(camera_or_host: str | None = None, limit: int = 100) -> dict[str, Any]:
        """List AppDataDetector semantic detector units and components."""
        return live.list_appdata_detectors(camera_or_host, limit)

    @server.tool(name="find_event_suppliers")
    def find_event_suppliers(camera_or_detector: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Find detector event supplier access points."""
        return live.find_event_suppliers(camera_or_detector, limit)

    @server.tool(name="find_metadata_endpoints")
    def find_metadata_endpoints(camera_or_detector: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Find VMDA or metadata source endpoints."""
        return live.find_metadata_endpoints(camera_or_detector, limit)

    @server.tool(name="get_archive_intervals")
    def get_archive_intervals(
        camera: str,
        hours: float = 1.0,
        max_count: int = 32,
        min_gap_ms: int = 1000,
    ) -> dict[str, Any]:
        """Return bounded archive intervals for a camera access point via ArchiveService.GetHistory2."""
        return live.get_archive_intervals(camera, hours=hours, max_count=max_count, min_gap_ms=min_gap_ms)

    @server.tool(name="subscribe_events_bounded")
    def subscribe_events_bounded(
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout: float = 5.0,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Bounded DomainNotifier.PullEvents subscription with hard timeout and event-count caps."""
        return live.subscribe_events_bounded(subjects=subjects, event_types=event_types, timeout=timeout, limit=limit)

    @server.tool(name="preflight_task")
    def preflight_task(task: str) -> dict[str, Any]:
        """Check whether fixtures exist before proposing a workflow."""
        return live.preflight_task(task)

    @server.tool(name="list_event_types")
    def list_event_types() -> dict[str, Any]:
        """Return the full EEventType enum (name + numeric value) from the live proto."""
        return live.list_event_types()

    @server.tool(name="list_detector_kinds")
    def list_detector_kinds() -> dict[str, Any]:
        """Discover detector kinds from live AVDetector / AppDataDetector descriptors."""
        return live.list_detector_kinds()

    @server.tool(name="search_events")
    def search_events(
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        hours: float = 1.0,
        limit: int = 100,
        descending: bool = True,
    ) -> dict[str, Any]:
        """Search persisted events via EventHistoryService.ReadEvents with bounded ranges."""
        return live.search_events(
            subjects=subjects, event_types=event_types, hours=hours, limit=limit, descending=descending
        )

    @server.tool(name="pull_metadata_bounded")
    def pull_metadata_bounded(
        access_point: str,
        timeout: float = 5.0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Bounded MetadataService.PullMetadata stream against a vmda/metadata source endpoint."""
        return live.pull_metadata_bounded(access_point=access_point, timeout=timeout, limit=limit)


def register_translator_tools(server: Any, translator: Any) -> None:
    from axxon_mcp_translator import register_translator_tools as _register
    _register(server, translator)


def register_bulk_onboarding_tools(server: Any, bulk_onboarding: Any) -> None:
    @server.tool(name="bulk_onboarding_connect_axxon_profile")
    def bulk_onboarding_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        """Connect the bulk onboarding layer to the env profile without applying changes."""
        return bulk_onboarding.bulk_onboarding_connect_axxon_profile(profile)

    @server.tool(name="bulk_onboarding_schema")
    def bulk_onboarding_schema() -> dict[str, Any]:
        """Return accepted bulk onboarding manifest fields, source rules, gates, and redaction policy."""
        return bulk_onboarding.bulk_onboarding_schema()

    @server.tool(name="bulk_onboarding_validate_manifest")
    def bulk_onboarding_validate_manifest(
        rows: list[dict[str, Any]] | None = None,
        csv_text: str = "",
        json_text: str = "",
        options: dict[str, Any] | None = None,
        path: str = "",
        file: str = "",
        filename: str = "",
        manifest_path: str = "",
    ) -> dict[str, Any]:
        """Validate inline CSV/JSON/row manifests against catalog, discovery, site graph, templates, and archives."""
        return bulk_onboarding.bulk_onboarding_validate_manifest(
            rows,
            csv_text,
            json_text,
            options,
            path,
            file,
            filename,
            manifest_path,
        )

    @server.tool(name="bulk_onboarding_plan")
    def bulk_onboarding_plan(
        rows: list[dict[str, Any]] | None = None,
        csv_text: str = "",
        json_text: str = "",
        options: dict[str, Any] | None = None,
        path: str = "",
        file: str = "",
        filename: str = "",
        manifest_path: str = "",
    ) -> dict[str, Any]:
        """Build a deterministic rollbackable per-camera and batch-level onboarding plan."""
        return bulk_onboarding.bulk_onboarding_plan(
            rows,
            csv_text,
            json_text,
            options,
            path,
            file,
            filename,
            manifest_path,
        )

    @server.tool(name="bulk_onboarding_apply_plan")
    def bulk_onboarding_apply_plan(batch_plan_id: str, confirmation: str) -> dict[str, Any]:
        """Apply a stored bulk onboarding plan when approval env and confirmation gates pass."""
        return bulk_onboarding.bulk_onboarding_apply_plan(batch_plan_id, confirmation)

    @server.tool(name="bulk_onboarding_verify_plan")
    def bulk_onboarding_verify_plan(batch_plan_id: str) -> dict[str, Any]:
        """Verify planned/applied/rolled-back bulk onboarding state with injectable readers."""
        return bulk_onboarding.bulk_onboarding_verify_plan(batch_plan_id)

    @server.tool(name="bulk_onboarding_rollback_plan")
    def bulk_onboarding_rollback_plan(batch_plan_id: str, confirmation: str) -> dict[str, Any]:
        """Roll back only recorded applied bulk onboarding steps in reverse order."""
        return bulk_onboarding.bulk_onboarding_rollback_plan(batch_plan_id, confirmation)

    @server.tool(name="bulk_onboarding_audit_log")
    def bulk_onboarding_audit_log() -> dict[str, Any]:
        """Return the sanitized in-memory bulk onboarding audit trail."""
        return bulk_onboarding.bulk_onboarding_audit_log()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Axxon One MCP server. No capability flag starts the knowledge-only server. "
            "--enable-all registers all groups but does not authorize mutations. --read-only "
            "registers the broad surface and authoritatively disables mutation execution."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--enable-live", action="store_true", help="Enable read-only live tools backed by env config.")
    parser.add_argument(
        "--enable-operator",
        action="store_true",
        help="Enable controlled operator mutation tools (plan/apply/verify/rollback). Requires AXXON_OPERATOR_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-generator",
        action="store_true",
        help="Enable integration generator tools (list/plan/generate/verify_integration).",
    )
    parser.add_argument(
        "--enable-partner",
        action="store_true",
        help="Enable partner SDK tools (scaffold_plugin/plugin_lint/plugin_package).",
    )
    parser.add_argument(
        "--enable-metadata",
        action="store_true",
        help="Enable read-only metadata/VMDA search tools (list_vmda_sources/live_track_sample/vmda_query).",
    )
    parser.add_argument(
        "--enable-view",
        action="store_true",
        help="Enable Phase 5A live/archive viewing tools (URL-only, byte/time/fps caps).",
    )
    parser.add_argument(
        "--enable-alarms",
        action="store_true",
        help="Enable Phase 5C alarm read tools (list/filter/history/subscribe).",
    )
    parser.add_argument(
        "--enable-alarms-mutation",
        action="store_true",
        help="Enable Phase 5C alarm lifecycle mutations. Requires AXXON_ALARMS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-view-objects",
        action="store_true",
        help="Enable Phase 5D read tools for layouts, maps, and videowalls.",
    )
    parser.add_argument(
        "--enable-detector-archive",
        action="store_true",
        help="Enable Phase 5E read tools for detectors, metadata, and archive policies.",
    )
    parser.add_argument(
        "--enable-detector-playbooks",
        action="store_true",
        help="Enable Phase 4 detector playbook planner/orchestrator. Apply/rollback need AXXON_DETECTOR_PLAYBOOKS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-admin",
        action="store_true",
        help="Enable Phase 5F-A read-only admin tools for security, health, notifiers, and schedule descriptors.",
    )
    parser.add_argument(
        "--enable-admin-mutations",
        action="store_true",
        help="Enable Phase 5F-B approval-gated admin mutation tools. Requires AXXON_ADMIN_MUTATION_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-bookmarks",
        action="store_true",
        help="Enable Phase 5G read-only BookmarkService tools backed by env config.",
    )
    parser.add_argument(
        "--enable-bookmark-mutations",
        action="store_true",
        help="Enable Phase 5G approval-gated bookmark lifecycle tools. Requires AXXON_BOOKMARK_MUTATION_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-translator",
        action="store_true",
        help="Enable Phase 7 NL-to-plan translator tools (assemble_recipe/validate_recipe/explain_recipe).",
    )
    parser.add_argument(
        "--enable-ptz",
        action="store_true",
        help="Enable PTZ/telemetry control tools (TelemetryService: sessions, move/zoom/focus/iris, presets).",
    )
    parser.add_argument(
        "--enable-audit",
        action="store_true",
        help="Enable Phase 10 AuditEventInjector tools. Injection needs AXXON_AUDIT_INJECT_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-recognizer",
        action="store_true",
        help="Enable Phase 11 read-only RealtimeRecognizerService watchlist tools (face/LPR lists).",
    )
    parser.add_argument(
        "--enable-recognizer-write",
        action="store_true",
        help="Enable Phase 14 RealtimeRecognizer watchlist write tools. Writes need AXXON_RECOGNIZER_WRITE_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-logic-control",
        action="store_true",
        help="Enable Phase 16 LogicService control tools (launch_macro, change_arm_state). Mutations need AXXON_LOGIC_CONTROL_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-settings",
        action="store_true",
        help="Enable Phase 17 DomainSettings data-storage tools. Updates need AXXON_SETTINGS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-timezone",
        action="store_true",
        help="Enable Phase 19 TimeZoneManager tools (set_timezone, set_ntp, change_timezones). Writes need AXXON_TIMEZONE_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-server",
        action="store_true",
        help="Enable Phase 20 ServerSettings tools (set_log_level, drop_logs). Writes need AXXON_SERVER_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-statistics",
        action="store_true",
        help="Enable StatisticService reads (get_statistics: CPU/disk/FPS/bitrate health). Read-only.",
    )
    parser.add_argument(
        "--enable-event-taxonomy",
        action="store_true",
        help="Enable EventDescription reads (get_event_grouping_tags). Read-only.",
    )
    parser.add_argument(
        "--enable-scene-description",
        action="store_true",
        help="Enable NgpNodeService reads (list_scene_description: per-camera scene geometry). Read-only.",
    )
    parser.add_argument(
        "--enable-package-availability",
        action="store_true",
        help="Enable InstallationPackageProvider reads (check_package_availability). Read-only.",
    )
    parser.add_argument(
        "--enable-domain-topology",
        action="store_true",
        help="Enable DomainManager reads (enumerate_nodes: domain + node topology). Read-only.",
    )
    parser.add_argument(
        "--enable-config-revisions",
        action="store_true",
        help="Enable ConfigurationManager reads (get_revision_info, collect_backup_probe). Read-only, capped.",
    )
    parser.add_argument(
        "--enable-filesystem-browser",
        action="store_true",
        help="Enable FileSystemBrowser reads (list_directory, get_file_info, get_space). Read-only.",
    )
    parser.add_argument(
        "--enable-devices-catalog",
        action="store_true",
        help="Enable DevicesCatalog reads (list_vendors, list_devices, get_device) for adding cameras. Read-only.",
    )
    parser.add_argument(
        "--enable-global-tracker",
        action="store_true",
        help="Enable GlobalTrackerService get_profile (cross-camera profile metadata, no images). Read-only.",
    )
    parser.add_argument(
        "--enable-shared-kv",
        action="store_true",
        help="Enable SharedKVStorageService reads + gated commit_record (writes need AXXON_SHARED_KV_APPROVE=1).",
    )
    parser.add_argument(
        "--enable-state-control",
        action="store_true",
        help="Enable StateControlService state reads + gated set_state (writes need AXXON_STATE_CONTROL_APPROVE=1).",
    )
    parser.add_argument(
        "--enable-site-graph",
        action="store_true",
        help="Enable read-only unified site graph tools for planners and integration generators.",
    )
    parser.add_argument(
        "--enable-bulk-onboarding",
        action="store_true",
        help="Enable bulk CSV/JSON camera onboarding planner/orchestrator. Apply/rollback need AXXON_BULK_ONBOARDING_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-groups",
        action="store_true",
        help="Enable Phase 21 GroupManager tools (change_groups, set_objects_membership). Writes need AXXON_GROUPS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-gdpr-cleanup",
        action="store_true",
        help="Enable Phase 30 GDPR cleanup tools (layout/map UserDataCleanup). Writes need AXXON_GDPR_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-control",
        action="store_true",
        help="Enable Phase 31 ACFA/VMDA control tools (perform_unit_action, vmda_cleanup). Writes need AXXON_CONTROL_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-map-providers",
        action="store_true",
        help="Enable Phase 34 MapService provider tools (configure_map_providers, get_map_provider). Writes need AXXON_MAP_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-logic-alerts",
        action="store_true",
        help="Enable Phase 35 LogicService batch alert tools (batch read + gated batch review). Reviews need AXXON_LOGIC_ALERTS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-config-change",
        action="store_true",
        help="Enable Phase 36 ConfigurationService tools (list_similar_units, batch_get_factories + gated unit property changes). Writes need AXXON_CONFIG_CHANGE_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-archive-volume",
        action="store_true",
        help="Enable Phase 37 ArchiveService volume tools (list_volume_states + gated resize_volume). Resize needs AXXON_ARCHIVE_VOLUME_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-bookmark-extras",
        action="store_true",
        help="Enable Phase 38 BookmarkService extras (render_bookmark_track + gated update_bookmark, set_bookmark_exported_time). Writes need AXXON_BOOKMARK_EXTRAS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-security-credentials",
        action="store_true",
        help="Enable Phase 39 SecurityService credential tools (check_password + gated change_my_password, change_my_login). Changes need AXXON_SECURITY_CREDENTIALS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-auth-sessions",
        action="store_true",
        help="Enable Phase 40 AuthenticationService session tools (authenticate, renew_session + gated close_session). Close needs AXXON_AUTH_SESSIONS_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-layout-manager",
        action="store_true",
        help="Enable Phase 41 LayoutManager tools (batch_get_layouts, layouts_on_view + gated update_layout_name). Rename needs AXXON_LAYOUT_MANAGER_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-license-reads",
        action="store_true",
        help="Enable Phase 42 LicenseService read tools (get_license_key metadata-only, get_restrictions).",
    )
    parser.add_argument(
        "--enable-misc-reads",
        action="store_true",
        help="Enable Phase 43 cross-service tools (acquire dynamic params, probe_volume, ping_node, generic settings get + gated save/remove). Settings writes need AXXON_MISC_WRITE_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-heatmap",
        action="store_true",
        help="Enable Phase 44 HeatMapService read tools (build/events/floor heatmap images + streaming heatmap queries; metadata-only).",
    )
    parser.add_argument(
        "--enable-media",
        action="store_true",
        help="Enable Phase 44 MediaService transport-probe tools (request_connection, request_qos, request_tunnel, stream_probe; metadata-only).",
    )
    parser.add_argument(
        "--enable-export",
        action="store_true",
        help="Enable ExportService snapshot/export tools (plan/start/status/download/stop/destroy/cleanup). Export actions need AXXON_EXPORT_APPROVE=1.",
    )
    parser.add_argument(
        "--enable-videowall",
        action="store_true",
        help="Enable Phase 46 VideowallService control tools (register/change/set-control-data/unregister; approval-gated, reversible).",
    )
    parser.add_argument(
        "--enable-web-api",
        action="store_true",
        help="Enable Phase 5 read-only Web server helpers (embeddable-component URL/commands, bounded WebSocket-event probe/sample).",
    )
    parser.add_argument(
        "--enable-client-api",
        action="store_true",
        help="Enable Phase 5 read-only Client HTTP API preflight + fixture-needed operation catalog.",
    )
    parser.add_argument(
        "--enable-discovery",
        action="store_true",
        help="Enable Phase 12 read-only DiscoveryService network device-discovery tool.",
    )
    parser.add_argument(
        "--enable-all",
        action="store_true",
        help="Register every capability group; mutation approval still must be supplied separately.",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Register the broad capability surface and authoritatively disable every mutation gate.",
    )
    return parser


def apply_enable_all(args: argparse.Namespace) -> argparse.Namespace:
    """Force every ``enable_*`` flag True when ``--enable-all`` was passed."""
    if getattr(args, "enable_all", False):
        for name in vars(args):
            if name.startswith("enable_"):
                setattr(args, name, True)
    return args


# Per-group mutation approval env vars. Registration does not authorize mutation: each module
# independently requires its exact external approval value plus its per-call confirmation token.
PTZ_APPROVE_ENV = "AXXON_PTZ_APPROVE"

APPROVE_ENV_VARS = (
    "AXXON_OPERATOR_APPROVE", PTZ_APPROVE_ENV, "AXXON_ALARMS_APPROVE", "AXXON_LOGIC_CONTROL_APPROVE",
    "AXXON_VIDEOWALL_APPROVE", "AXXON_ADMIN_MUTATION_APPROVE", "AXXON_BOOKMARK_MUTATION_APPROVE",
    "AXXON_TIMEZONE_APPROVE", "AXXON_SETTINGS_APPROVE", "AXXON_GROUPS_APPROVE", "AXXON_MAP_APPROVE",
    "AXXON_LOGIC_ALERTS_APPROVE", "AXXON_CONFIG_CHANGE_APPROVE", "AXXON_ARCHIVE_VOLUME_APPROVE",
    "AXXON_BOOKMARK_EXTRAS_APPROVE", "AXXON_SECURITY_CREDENTIALS_APPROVE", "AXXON_AUTH_SESSIONS_APPROVE",
    "AXXON_LAYOUT_MANAGER_APPROVE", "AXXON_AUDIT_INJECT_APPROVE", "AXXON_CONTROL_APPROVE",
    "AXXON_RECOGNIZER_WRITE_APPROVE", "AXXON_SERVER_APPROVE", "AXXON_GDPR_APPROVE",
    "AXXON_MISC_WRITE_APPROVE", "AXXON_ARCHIVE_MAINTENANCE_APPROVE", "AXXON_SHARED_KV_APPROVE",
    "AXXON_STATE_CONTROL_APPROVE", "AXXON_EXPORT_APPROVE", "AXXON_BULK_ONBOARDING_APPROVE",
    "AXXON_DETECTOR_PLAYBOOKS_APPROVE",
)


def resolve_runtime_profile(
    args: argparse.Namespace,
    environ: dict[str, str] | None = None,
) -> argparse.Namespace:
    """Resolve registration flags without changing the supplied or process environment."""
    del environ
    if getattr(args, "enable_all", False) or getattr(args, "read_only", False):
        for name in vars(args):
            if name.startswith("enable_"):
                setattr(args, name, True)
    return args


def approval_enabled(
    variable: str,
    *,
    args: argparse.Namespace,
    environ: dict[str, str] | None = None,
) -> bool:
    """Return whether one exact external approval is active for the resolved profile."""
    env = os.environ if environ is None else environ
    return not bool(getattr(args, "read_only", False)) and env.get(variable) == "1"


def main() -> int:
    args = build_parser().parse_args()
    args = apply_enable_all(args)
    args = resolve_runtime_profile(args)
    live = None
    if args.enable_live:
        from axxon_mcp_live import AxxonMcpLive

        live = AxxonMcpLive()
    operator = None
    if args.enable_operator:
        from axxon_api_client import AxxonApiClient, AxxonClientConfig
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

        config = AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])
        # Build the live client lazily: the server must boot with no credentials, and
        # AxxonApiClient requires a password. Constructing it inside the factory defers that
        # until an operator tool is actually called (and the gate already needs approval+token).
        operator = OperatorRegistry(
            client_factory=lambda: AxxonOperatorClient(AxxonApiClient(config)),
            host=f"hosts/{config.tls_cn}",
            enabled=approval_enabled("AXXON_OPERATOR_APPROVE", args=args),
        )
    generator = None
    if args.enable_generator:
        from axxon_mcp_generator import Generator

        generator = Generator(corpus_dir=args.corpus_dir)
    partner = None
    if args.enable_partner:
        from axxon_mcp_generator import Generator
        from axxon_mcp_partner import PartnerKit

        partner = PartnerKit(generator=Generator(corpus_dir=args.corpus_dir))
    metadata = None
    if args.enable_metadata:
        from axxon_mcp_metadata import AxxonMcpMetadata

        metadata = AxxonMcpMetadata()
    view = None
    if args.enable_view:
        from axxon_mcp_view import AxxonMcpView

        view = AxxonMcpView()
    alarms = None
    if args.enable_alarms:
        from axxon_mcp_alarms import AxxonMcpAlarms

        alarms = AxxonMcpAlarms()
    alarm_mutator = None
    if args.enable_alarms_mutation:
        from axxon_mcp_alarms import AxxonAlarmMutator

        alarm_mutator = AxxonAlarmMutator(
            env_getter=lambda variable: "1" if approval_enabled(variable, args=args) else None,
        )
    view_objects = None
    if args.enable_view_objects:
        from axxon_mcp_view_objects import AxxonMcpViewObjects

        view_objects = AxxonMcpViewObjects()
    detector_archive = None
    if args.enable_detector_archive:
        from axxon_mcp_detector_archive import AxxonMcpDetectorArchive

        detector_archive = AxxonMcpDetectorArchive()
    detector_playbooks = None
    if args.enable_detector_playbooks:
        from axxon_api_client import AxxonApiClient, AxxonClientConfig
        from axxon_mcp_detector_archive import AxxonMcpDetectorArchive
        from axxon_mcp_detector_playbooks import APPROVAL_ENV, AxxonMcpDetectorPlaybooks
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

        config = AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])
        detector_playbooks = AxxonMcpDetectorPlaybooks(
            detector_archive=AxxonMcpDetectorArchive(),
            environ={APPROVAL_ENV: "1"} if approval_enabled(APPROVAL_ENV, args=args) else {},
            operator=OperatorRegistry(
                client_factory=lambda: AxxonOperatorClient(AxxonApiClient(config)),
                host=f"hosts/{config.tls_cn}",
                enabled=approval_enabled(APPROVAL_ENV, args=args),
            ),
        )
    admin = None
    if args.enable_admin:
        from axxon_mcp_admin import AxxonMcpAdmin

        admin = AxxonMcpAdmin()
    admin_mutator = None
    if args.enable_admin_mutations:
        from axxon_mcp_admin_mutations import ADMIN_MUTATION_APPROVE_ENV, AxxonAdminMutationRegistry

        admin_mutator = AxxonAdminMutationRegistry(
            enabled=approval_enabled(ADMIN_MUTATION_APPROVE_ENV, args=args),
        )
    bookmarks = None
    if args.enable_bookmarks:
        from axxon_mcp_bookmarks import AxxonMcpBookmarks

        bookmarks = AxxonMcpBookmarks()
    bookmark_mutator = None
    if args.enable_bookmark_mutations:
        from axxon_mcp_bookmark_mutations import BOOKMARK_MUTATION_APPROVE_ENV, AxxonBookmarkMutationRegistry

        bookmark_mutator = AxxonBookmarkMutationRegistry(
            enabled=approval_enabled(BOOKMARK_MUTATION_APPROVE_ENV, args=args),
        )
    translator = None
    if args.enable_translator:
        from axxon_api_client import AxxonApiClient, AxxonClientConfig
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry
        from axxon_mcp_translator import AxxonMcpTranslator

        config = AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])

        def _make_operator() -> OperatorRegistry:
            # Lazy client (see operator group): boot must not require credentials.
            return OperatorRegistry(
                client_factory=lambda: AxxonOperatorClient(AxxonApiClient(config)),
                host=f"hosts/{config.tls_cn}",
                enabled=False,
            )

        def _make_devices() -> Any:
            from axxon_mcp_devices_catalog import AxxonMcpDevicesCatalog

            return AxxonMcpDevicesCatalog()

        translator = AxxonMcpTranslator(operator_factory=_make_operator, devices_factory=_make_devices)
    ptz = None
    if args.enable_ptz:
        from axxon_mcp_ptz import AxxonMcpPtz

        ptz = AxxonMcpPtz()
        ptz.enabled = approval_enabled(PTZ_APPROVE_ENV, args=args)
    audit = None
    if args.enable_audit:
        from axxon_mcp_audit import AUDIT_INJECT_APPROVE_ENV, AxxonMcpAudit

        audit = AxxonMcpAudit(enabled=approval_enabled(AUDIT_INJECT_APPROVE_ENV, args=args))
    recognizer = None
    if args.enable_recognizer:
        from axxon_mcp_recognizer import AxxonMcpRecognizer

        recognizer = AxxonMcpRecognizer()
    recognizer_write = None
    if args.enable_recognizer_write:
        from axxon_mcp_recognizer_write import WRITE_APPROVE_ENV, AxxonMcpRecognizerWrite

        recognizer_write = AxxonMcpRecognizerWrite(enabled=approval_enabled(WRITE_APPROVE_ENV, args=args))
    logic_control = None
    if args.enable_logic_control:
        from axxon_mcp_logic_control import LOGIC_CONTROL_APPROVE_ENV, AxxonMcpLogicControl

        logic_control = AxxonMcpLogicControl(enabled=approval_enabled(LOGIC_CONTROL_APPROVE_ENV, args=args))
    settings = None
    if args.enable_settings:
        from axxon_mcp_settings import SETTINGS_APPROVE_ENV, AxxonMcpSettings

        settings = AxxonMcpSettings(enabled=approval_enabled(SETTINGS_APPROVE_ENV, args=args))
    timezone = None
    if args.enable_timezone:
        from axxon_mcp_timezone import TIMEZONE_APPROVE_ENV, AxxonMcpTimezone

        timezone = AxxonMcpTimezone(enabled=approval_enabled(TIMEZONE_APPROVE_ENV, args=args))
    server_settings = None
    if args.enable_server:
        from axxon_mcp_server_settings import SERVER_APPROVE_ENV, AxxonMcpServerSettings

        server_settings = AxxonMcpServerSettings(enabled=approval_enabled(SERVER_APPROVE_ENV, args=args))
    statistics = None
    if args.enable_statistics:
        from axxon_mcp_statistics import AxxonMcpStatistics

        statistics = AxxonMcpStatistics()
    event_taxonomy = None
    if args.enable_event_taxonomy:
        from axxon_mcp_event_taxonomy import AxxonMcpEventTaxonomy

        event_taxonomy = AxxonMcpEventTaxonomy()
    scene_description = None
    if args.enable_scene_description:
        from axxon_mcp_scene_description import AxxonMcpSceneDescription

        scene_description = AxxonMcpSceneDescription()
    package_availability = None
    if args.enable_package_availability:
        from axxon_mcp_package_availability import AxxonMcpPackageAvailability

        package_availability = AxxonMcpPackageAvailability()
    domain_topology = None
    if args.enable_domain_topology:
        from axxon_mcp_domain_topology import AxxonMcpDomainTopology

        domain_topology = AxxonMcpDomainTopology()
    config_revisions = None
    if args.enable_config_revisions:
        from axxon_mcp_config_revisions import AxxonMcpConfigRevisions

        config_revisions = AxxonMcpConfigRevisions()
    filesystem_browser = None
    if args.enable_filesystem_browser:
        from axxon_mcp_filesystem_browser import AxxonMcpFilesystemBrowser

        filesystem_browser = AxxonMcpFilesystemBrowser()
    devices_catalog = None
    if args.enable_devices_catalog:
        from axxon_mcp_devices_catalog import AxxonMcpDevicesCatalog

        devices_catalog = AxxonMcpDevicesCatalog()
    global_tracker = None
    if args.enable_global_tracker:
        from axxon_mcp_global_tracker import AxxonMcpGlobalTracker

        global_tracker = AxxonMcpGlobalTracker()
    shared_kv = None
    if args.enable_shared_kv:
        from axxon_mcp_shared_kv import SHARED_KV_APPROVE_ENV, AxxonMcpSharedKv

        shared_kv = AxxonMcpSharedKv(enabled=approval_enabled(SHARED_KV_APPROVE_ENV, args=args))
    state_control = None
    if args.enable_state_control:
        from axxon_mcp_state_control import STATE_CONTROL_APPROVE_ENV, AxxonMcpStateControl

        state_control = AxxonMcpStateControl(enabled=approval_enabled(STATE_CONTROL_APPROVE_ENV, args=args))
    site_graph = None
    if args.enable_site_graph:
        from axxon_mcp_site_graph import AxxonMcpSiteGraph

        site_graph = AxxonMcpSiteGraph()
    bulk_onboarding = None
    if args.enable_bulk_onboarding:
        from axxon_mcp_bulk_onboarding import BULK_ONBOARDING_APPROVE_ENV, AxxonMcpBulkOnboarding

        bulk_onboarding = AxxonMcpBulkOnboarding(
            environ=(
                {BULK_ONBOARDING_APPROVE_ENV: "1"}
                if approval_enabled(BULK_ONBOARDING_APPROVE_ENV, args=args)
                else {}
            )
        )
    groups = None
    if args.enable_groups:
        from axxon_mcp_groups import GROUPS_APPROVE_ENV, AxxonMcpGroups

        groups = AxxonMcpGroups(enabled=approval_enabled(GROUPS_APPROVE_ENV, args=args))
    discovery = None
    if args.enable_discovery:
        from axxon_mcp_discovery import AxxonMcpDiscovery

        discovery = AxxonMcpDiscovery()
    gdpr_cleanup = None
    if args.enable_gdpr_cleanup:
        from axxon_mcp_gdpr_cleanup import GDPR_APPROVE_ENV, AxxonMcpGdprCleanup

        gdpr_cleanup = AxxonMcpGdprCleanup(enabled=approval_enabled(GDPR_APPROVE_ENV, args=args))
    control = None
    if args.enable_control:
        from axxon_mcp_acfa_vmda_control import CONTROL_APPROVE_ENV, AxxonMcpAcfaVmdaControl

        control = AxxonMcpAcfaVmdaControl(enabled=approval_enabled(CONTROL_APPROVE_ENV, args=args))
    map_providers = None
    if args.enable_map_providers:
        from axxon_mcp_map_providers import MAP_APPROVE_ENV, AxxonMcpMapProviders

        map_providers = AxxonMcpMapProviders(enabled=approval_enabled(MAP_APPROVE_ENV, args=args))
    logic_alerts = None
    if args.enable_logic_alerts:
        from axxon_mcp_logic_alerts import LOGIC_ALERTS_APPROVE_ENV, AxxonMcpLogicAlerts

        logic_alerts = AxxonMcpLogicAlerts(enabled=approval_enabled(LOGIC_ALERTS_APPROVE_ENV, args=args))
    config_change = None
    if args.enable_config_change:
        from axxon_mcp_config_change import CONFIG_CHANGE_APPROVE_ENV, AxxonMcpConfigChange

        config_change = AxxonMcpConfigChange(enabled=approval_enabled(CONFIG_CHANGE_APPROVE_ENV, args=args))
    archive_volume = None
    if args.enable_archive_volume:
        from axxon_mcp_archive_volume import ARCHIVE_VOLUME_APPROVE_ENV, AxxonMcpArchiveVolume

        archive_volume = AxxonMcpArchiveVolume(enabled=approval_enabled(ARCHIVE_VOLUME_APPROVE_ENV, args=args))
    bookmark_extras = None
    if args.enable_bookmark_extras:
        from axxon_mcp_bookmark_extras import BOOKMARK_EXTRAS_APPROVE_ENV, AxxonMcpBookmarkExtras

        bookmark_extras = AxxonMcpBookmarkExtras(enabled=approval_enabled(BOOKMARK_EXTRAS_APPROVE_ENV, args=args))
    security_credentials = None
    if args.enable_security_credentials:
        from axxon_mcp_security_credentials import SECURITY_CREDENTIALS_APPROVE_ENV, AxxonMcpSecurityCredentials

        security_credentials = AxxonMcpSecurityCredentials(
            enabled=approval_enabled(SECURITY_CREDENTIALS_APPROVE_ENV, args=args)
        )
    auth_sessions = None
    if args.enable_auth_sessions:
        from axxon_mcp_auth_sessions import AUTH_SESSIONS_APPROVE_ENV, AxxonMcpAuthSessions

        auth_sessions = AxxonMcpAuthSessions(enabled=approval_enabled(AUTH_SESSIONS_APPROVE_ENV, args=args))
    layout_manager = None
    if args.enable_layout_manager:
        from axxon_mcp_layout_manager import LAYOUT_MANAGER_APPROVE_ENV, AxxonMcpLayoutManager

        layout_manager = AxxonMcpLayoutManager(enabled=approval_enabled(LAYOUT_MANAGER_APPROVE_ENV, args=args))
    license_reads = None
    if args.enable_license_reads:
        from axxon_mcp_license_reads import AxxonMcpLicenseReads

        license_reads = AxxonMcpLicenseReads()
    misc_reads = None
    if args.enable_misc_reads:
        from axxon_mcp_misc_reads import MISC_WRITE_APPROVE_ENV, AxxonMcpMiscReads

        misc_reads = AxxonMcpMiscReads(enabled=approval_enabled(MISC_WRITE_APPROVE_ENV, args=args))
    heatmap = None
    if args.enable_heatmap:
        from axxon_mcp_heatmap import AxxonMcpHeatmap

        heatmap = AxxonMcpHeatmap()
    media = None
    if args.enable_media:
        from axxon_mcp_media import AxxonMcpMedia

        media = AxxonMcpMedia()
    export = None
    if args.enable_export:
        from axxon_mcp_export import EXPORT_APPROVE_ENV, AxxonMcpExport

        export = AxxonMcpExport(enabled=approval_enabled(EXPORT_APPROVE_ENV, args=args))
    videowall = None
    if args.enable_videowall:
        from axxon_mcp_videowall import VIDEOWALL_APPROVE_ENV, AxxonMcpVideowall

        videowall = AxxonMcpVideowall(enabled=approval_enabled(VIDEOWALL_APPROVE_ENV, args=args))
    web_api = None
    if args.enable_web_api:
        from axxon_mcp_web_api import AxxonMcpWebApi

        web_api = AxxonMcpWebApi()
    client_api = None
    if args.enable_client_api:
        from axxon_mcp_client_api import AxxonMcpClientApi

        client_api = AxxonMcpClientApi()
    server = create_server(
        corpus_dir=args.corpus_dir,
        live=live,
        operator=operator,
        generator=generator,
        partner=partner,
        metadata=metadata,
        view=view,
        alarms=alarms,
        alarm_mutator=alarm_mutator,
        view_objects=view_objects,
        detector_archive=detector_archive,
        detector_playbooks=detector_playbooks,
        admin=admin,
        admin_mutator=admin_mutator,
        bookmarks=bookmarks,
        bookmark_mutator=bookmark_mutator,
        translator=translator,
        ptz=ptz,
        audit=audit,
        recognizer=recognizer,
        recognizer_write=recognizer_write,
        logic_control=logic_control,
        settings=settings,
        timezone=timezone,
        server_settings=server_settings,
        statistics=statistics,
        event_taxonomy=event_taxonomy,
        scene_description=scene_description,
        package_availability=package_availability,
        domain_topology=domain_topology,
        config_revisions=config_revisions,
        filesystem_browser=filesystem_browser,
        devices_catalog=devices_catalog,
        global_tracker=global_tracker,
        shared_kv=shared_kv,
        state_control=state_control,
        site_graph=site_graph,
        bulk_onboarding=bulk_onboarding,
        groups=groups,
        discovery=discovery,
        gdpr_cleanup=gdpr_cleanup,
        control=control,
        map_providers=map_providers,
        logic_alerts=logic_alerts,
        config_change=config_change,
        archive_volume=archive_volume,
        bookmark_extras=bookmark_extras,
        security_credentials=security_credentials,
        auth_sessions=auth_sessions,
        layout_manager=layout_manager,
        license_reads=license_reads,
        misc_reads=misc_reads,
        heatmap=heatmap,
        media=media,
        export=export,
        videowall=videowall,
        web_api=web_api,
        client_api=client_api,
    )
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
