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
            "`/tmp/axxon-grpc-venv/bin/python -m pip install -r arm64-docker/tools/requirements-mcp.txt`."
        ) from exc
    return FastMCP(name, **kwargs)


def create_server(
    *,
    docs: AxxonMcpDocs | Any | None = None,
    live: Any | None = None,
    operator: Any | None = None,
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

    return server


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
    server = create_server(corpus_dir=args.corpus_dir, live=live, operator=operator)
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
