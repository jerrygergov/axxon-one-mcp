#!/usr/bin/env python3
"""Verify clean-checkout MCP startup profiles over the real stdio protocol."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from axxon_mcp_server import APPROVE_ENV_VARS as SERVER_APPROVAL_ENV_VARS


TOOLS_DIR = Path(__file__).resolve().parent
SERVER_SCRIPT = TOOLS_DIR / "axxon_mcp_server.py"
REQUEST_TIMEOUT_SECONDS = 60
MINIMUM_BROAD_TOOL_COUNT = 300


@dataclass(frozen=True)
class StartupCase:
    name: str
    args: tuple[str, ...]


CASES = (
    StartupCase("knowledge", ()),
    StartupCase("live-import", ("--enable-live",)),
    StartupCase("all-read-only", ("--enable-all", "--read-only")),
)

KNOWLEDGE_TOOLS = {
    "search_api_docs",
    "get_api_method",
    "get_http_endpoint",
    "get_verified_example",
    "explain_task_recipe",
    "list_remaining_gaps",
    "list_capabilities",
}

OPERATOR_TOOLS = {
    "list_operator_workflows",
    "plan_operator_workflow",
    "execute_operator_workflow",
    "apply_operator_plan",
    "verify_operator_plan",
    "rollback_operator_plan",
    "operator_audit_log",
}

APPROVAL_ENV_VARS = frozenset(SERVER_APPROVAL_ENV_VARS)


class VerificationError(RuntimeError):
    """Raised when a startup profile violates its release contract."""


def clean_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """Return a copy with every Axxon setting and credential removed."""
    return {key: value for key, value in environ.items() if not key.startswith("AXXON_")}


def environment_for_case(
    case: StartupCase,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the secret-free subprocess environment for one startup case."""
    prepared = clean_environment(os.environ if environ is None else environ)
    if case.name == "all-read-only":
        prepared.update({variable: "1" for variable in APPROVAL_ENV_VARS})
    return prepared


async def _list_all_tools(session: ClientSession) -> set[str]:
    names: set[str] = set()
    cursor: str | None = None
    while True:
        result = await session.list_tools(cursor=cursor)
        names.update(tool.name for tool in result.tools)
        cursor = result.nextCursor
        if cursor is None:
            return names


def _structured_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    for content in getattr(result, "content", ()):
        text = getattr(content, "text", None)
        if isinstance(text, str):
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                return decoded
    raise VerificationError("mutation result did not contain a structured object")


def _verify_tools(case: StartupCase, tool_names: set[str]) -> None:
    if case.name == "knowledge":
        if tool_names != KNOWLEDGE_TOOLS:
            missing = sorted(KNOWLEDGE_TOOLS - tool_names)
            unexpected = sorted(tool_names - KNOWLEDGE_TOOLS)
            raise VerificationError(
                f"knowledge tool mismatch: missing={missing}, unexpected={unexpected}"
            )
        return

    if case.name == "live-import":
        if "list_cameras" not in tool_names:
            raise VerificationError("live-import did not register list_cameras")
        leaked = sorted(tool_names & OPERATOR_TOOLS)
        if leaked:
            raise VerificationError(f"live-import registered operator tools: {leaked}")
        return

    if len(tool_names) < MINIMUM_BROAD_TOOL_COUNT:
        raise VerificationError(
            f"all-read-only surface is unexpectedly narrow: {len(tool_names)} tools"
        )
    required = KNOWLEDGE_TOOLS | {"list_cameras", "launch_macro"}
    missing = sorted(required - tool_names)
    if missing:
        raise VerificationError(f"all-read-only is missing representative tools: {missing}")


async def verify_case(case: StartupCase) -> dict[str, Any]:
    """Initialize one server process, list tools, and verify its profile contract."""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT), "--transport", "stdio", *case.args],
        env=environment_for_case(case),
        cwd=TOOLS_DIR.parent,
    )
    timeout = timedelta(seconds=REQUEST_TIMEOUT_SECONDS)

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timeout,
        ) as session:
            await session.initialize()
            tool_names = await _list_all_tools(session)
            _verify_tools(case, tool_names)

            summary: dict[str, Any] = {
                "name": case.name,
                "tool_count": len(tool_names),
            }
            if case.name == "all-read-only":
                mutation = await session.call_tool(
                    "launch_macro",
                    {
                        "macro_id": "verification-dummy",
                        "confirmation": "CONFIRM-logic-control",
                    },
                    read_timeout_seconds=timeout,
                )
                structured = _structured_result(mutation)
                status = structured.get("status")
                if status != "disabled":
                    raise VerificationError(
                        f"all-read-only mutation gate returned status={status!r}"
                    )
                summary["mutation_status"] = status
            return summary


async def verify_startup() -> list[dict[str, Any]]:
    return [await verify_case(case) for case in CASES]


def main() -> int:
    try:
        cases = asyncio.run(verify_startup())
    except Exception as exc:
        print(
            json.dumps(
                {"error": f"{type(exc).__name__}: {exc}", "status": "failed"},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            {"cases": cases, "status": "ok"},
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
