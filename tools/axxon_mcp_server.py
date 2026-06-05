#!/usr/bin/env python3
"""Docs-only FastMCP server for the Axxon One API corpus."""

from __future__ import annotations

import argparse
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


def default_fastmcp_factory(name: str, **kwargs: Any) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "The MCP Python SDK is not installed. Install the docs-only MCP dependency with "
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
    admin: Any | None = None,
    admin_mutator: Any | None = None,
    bookmarks: Any | None = None,
    bookmark_mutator: Any | None = None,
    translator: Any | None = None,
    ptz: Any | None = None,
    audit: Any | None = None,
    recognizer: Any | None = None,
    discovery: Any | None = None,
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    fastmcp_factory: Callable[..., Any] = default_fastmcp_factory,
) -> Any:
    docs = docs or AxxonMcpDocs.from_corpus_dir(corpus_dir)
    server = fastmcp_factory("Axxon One API Docs", json_response=True)

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

    if discovery is not None:
        register_discovery_tools(server, discovery)

    return server


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
        return ptz.acquire_session(access_point, host_name)

    @server.tool(name="ptz_keepalive_session")
    def ptz_keepalive_session(access_point: str, session_id: int) -> dict[str, Any]:
        """Extend a telemetry control session."""
        return ptz.keepalive_session(access_point, session_id)

    @server.tool(name="ptz_release_session")
    def ptz_release_session(access_point: str, session_id: int) -> dict[str, Any]:
        """Release a telemetry control session."""
        return ptz.release_session(access_point, session_id)

    @server.tool(name="ptz_get_position")
    def ptz_get_position(access_point: str) -> dict[str, Any]:
        """Read the absolute pan/tilt/zoom position of a PTZ source."""
        return ptz.get_position(access_point)

    @server.tool(name="ptz_move")
    def ptz_move(access_point: str, session_id: int, pan: float, tilt: float, mode: str = "continuous") -> dict[str, Any]:
        """Pan/tilt the camera (mode: continuous, relative, or absolute)."""
        return ptz.move(access_point, session_id, pan, tilt, mode)

    @server.tool(name="ptz_zoom")
    def ptz_zoom(access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Zoom the camera (mode: continuous, relative, or absolute)."""
        return ptz.zoom(access_point, session_id, value, mode)

    @server.tool(name="ptz_focus")
    def ptz_focus(access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Adjust focus (mode: continuous, relative, or absolute)."""
        return ptz.focus(access_point, session_id, value, mode)

    @server.tool(name="ptz_iris")
    def ptz_iris(access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Adjust iris (mode: continuous, relative, or absolute)."""
        return ptz.iris(access_point, session_id, value, mode)

    @server.tool(name="ptz_absolute_move")
    def ptz_absolute_move(access_point: str, session_id: int, pan: int, tilt: int, zoom: int, mask: int = 7) -> dict[str, Any]:
        """Move to an absolute pan/tilt/zoom position (mask selects axes; 7 = all)."""
        return ptz.absolute_move(access_point, session_id, pan, tilt, zoom, mask)

    @server.tool(name="ptz_list_presets")
    def ptz_list_presets(access_point: str) -> dict[str, Any]:
        """List telemetry presets for a PTZ source."""
        return ptz.list_presets(access_point)

    @server.tool(name="ptz_set_preset")
    def ptz_set_preset(access_point: str, session_id: int, position: int, label: str = "") -> dict[str, Any]:
        """Save the current position as a preset at the given slot."""
        return ptz.set_preset(access_point, session_id, position, label)

    @server.tool(name="ptz_go_preset")
    def ptz_go_preset(access_point: str, session_id: int, position: int, speed: float = 1.0) -> dict[str, Any]:
        """Move the camera to a saved preset."""
        return ptz.go_preset(access_point, session_id, position, speed)

    @server.tool(name="ptz_remove_preset")
    def ptz_remove_preset(access_point: str, session_id: int, position: int) -> dict[str, Any]:
        """Delete a saved preset."""
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
        """Archived VMDA forensic search via ExecuteQuery MomentQuest motion-in-area.

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
    def list_recognizer_items(list_ids: list[str] | None = None, limit: int = 200) -> dict[str, Any]:
        """List enrolled items (people/plates) as privacy-safe metadata: no images, no biometric vectors."""
        return recognizer.list_recognizer_items(list_ids, limit)


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
    def plugin_package(path: str, output: str, fmt: str = "zip") -> dict[str, Any]:
        """Package a clean plugin repo into an archive with a SHA-256 manifest."""
        return kit.plugin_package(path, fmt, output)


def register_operator_tools(server: Any, operator: Any) -> None:
    @server.tool(name="list_operator_workflows")
    def list_operator_workflows() -> dict[str, Any]:
        """List operator workflows supported by this MCP server."""
        return {"workflows": operator.known_workflows()}

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the docs-only Axxon One MCP server.")
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
        "--enable-discovery",
        action="store_true",
        help="Enable Phase 12 read-only DiscoveryService network device-discovery tool.",
    )
    return parser


def main() -> int:
    import os

    args = build_parser().parse_args()
    live = None
    if args.enable_live:
        from axxon_mcp_live import AxxonMcpLive

        live = AxxonMcpLive()
    operator = None
    if args.enable_operator:
        from axxon_api_client import AxxonApiClient, AxxonClientConfig
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

        explicit = os.environ.get("AXXON_OPERATOR_APPROVE") == "1"
        config = AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])
        api_client = AxxonApiClient(config)
        operator = OperatorRegistry(
            client_factory=lambda: AxxonOperatorClient(api_client),
            host=f"hosts/{config.tls_cn}",
            enabled=explicit,
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

        alarm_mutator = AxxonAlarmMutator()
    view_objects = None
    if args.enable_view_objects:
        from axxon_mcp_view_objects import AxxonMcpViewObjects

        view_objects = AxxonMcpViewObjects()
    detector_archive = None
    if args.enable_detector_archive:
        from axxon_mcp_detector_archive import AxxonMcpDetectorArchive

        detector_archive = AxxonMcpDetectorArchive()
    admin = None
    if args.enable_admin:
        from axxon_mcp_admin import AxxonMcpAdmin

        admin = AxxonMcpAdmin()
    admin_mutator = None
    if args.enable_admin_mutations:
        from axxon_mcp_admin_mutations import AxxonAdminMutationRegistry

        admin_mutator = AxxonAdminMutationRegistry(
            enabled=os.environ.get("AXXON_ADMIN_MUTATION_APPROVE") == "1",
        )
    bookmarks = None
    if args.enable_bookmarks:
        from axxon_mcp_bookmarks import AxxonMcpBookmarks

        bookmarks = AxxonMcpBookmarks()
    bookmark_mutator = None
    if args.enable_bookmark_mutations:
        from axxon_mcp_bookmark_mutations import AxxonBookmarkMutationRegistry

        bookmark_mutator = AxxonBookmarkMutationRegistry(
            enabled=os.environ.get("AXXON_BOOKMARK_MUTATION_APPROVE") == "1",
        )
    translator = None
    if args.enable_translator:
        from axxon_api_client import AxxonApiClient, AxxonClientConfig
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry
        from axxon_mcp_translator import AxxonMcpTranslator

        config = AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])
        api_client = AxxonApiClient(config)

        def _make_operator() -> OperatorRegistry:
            return OperatorRegistry(
                client_factory=lambda: AxxonOperatorClient(api_client),
                host=f"hosts/{config.tls_cn}",
                enabled=False,
            )

        translator = AxxonMcpTranslator(operator_factory=_make_operator)
    ptz = None
    if args.enable_ptz:
        from axxon_mcp_ptz import AxxonMcpPtz

        ptz = AxxonMcpPtz()
    audit = None
    if args.enable_audit:
        from axxon_mcp_audit import AxxonMcpAudit

        audit = AxxonMcpAudit()
    recognizer = None
    if args.enable_recognizer:
        from axxon_mcp_recognizer import AxxonMcpRecognizer

        recognizer = AxxonMcpRecognizer()
    discovery = None
    if args.enable_discovery:
        from axxon_mcp_discovery import AxxonMcpDiscovery

        discovery = AxxonMcpDiscovery()
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
        admin=admin,
        admin_mutator=admin_mutator,
        bookmarks=bookmarks,
        bookmark_mutator=bookmark_mutator,
        translator=translator,
        ptz=ptz,
        audit=audit,
        recognizer=recognizer,
        discovery=discovery,
    )
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
