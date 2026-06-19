#!/usr/bin/env python3
"""Render deterministic API coverage documentation from the MCP corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "docs/api-audit/mcp-corpus/api_methods.json"
OUTPUT = REPO_ROOT / "docs/COVERAGE.md"


def classify_status(live_status: str) -> str:
    """Map a corpus live status to one documented coverage category."""
    if live_status.startswith("tested-pass"):
        return "verified"
    if "fixture" in live_status:
        return "fixture-blocked"
    return "pending"


def aggregate_methods(
    methods: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Counter[str]], Counter[str]]:
    """Aggregate coverage by service and globally."""
    services: defaultdict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    for method in methods:
        service = str(method["service"])
        category = classify_status(str(method.get("live_status", "")))
        services[service][category] += 1
        services[service]["total"] += 1
        totals[category] += 1
        totals["total"] += 1
    return dict(services), totals


def render_coverage(methods: Iterable[Mapping[str, Any]]) -> str:
    """Return the complete deterministic coverage document."""
    services, totals = aggregate_methods(methods)
    rows = sorted(
        services.items(),
        key=lambda item: (
            -item[1]["total"],
            -item[1]["verified"],
            item[0],
        ),
    )

    lines = [
        "# Coverage",
        "",
        "Live status of each Axxon One gRPC RPC exposed by this MCP server, generated from",
        "`docs/api-audit/mcp-corpus/api_methods.json` (the authoritative source).",
        "",
        (
            f"**{totals['verified']} / {totals['total']} RPCs live-verified** across "
            f"{len(services)} services ({totals['pending']} pending, "
            f"{totals['fixture-blocked']} fixture-blocked)."
        ),
        "",
        "- **tested-pass** — exercised end-to-end against a live server and returned a valid response.",
        "- **fixture-blocked** — exercised live, but the stand lacked required hardware, configuration, or infrastructure.",
        "- **pending** — not yet exercised live.",
        "",
        "| Service | Verified | Fixture-blocked | Pending | Total |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(
        (
            f"| {service} | {counts['verified']} | {counts['fixture-blocked']} | "
            f"{counts['pending']} | {counts['total']} |"
        )
        for service, counts in rows
    )
    lines.append(
        f"| **Total** | **{totals['verified']}** | **{totals['fixture-blocked']}** | "
        f"**{totals['pending']}** | **{totals['total']}** |"
    )
    return "\n".join(lines) + "\n"


def load_methods(corpus_path: Path = CORPUS) -> list[dict[str, Any]]:
    """Load the authoritative method list."""
    document = json.loads(corpus_path.read_text(encoding="utf-8"))
    methods = document.get("methods")
    if not isinstance(methods, list):
        raise ValueError(f"{corpus_path} does not contain a methods list")
    return methods


def check_output(output_path: Path, rendered: str) -> int:
    """Compare rendered output without modifying the tracked file."""
    try:
        current = output_path.read_bytes()
    except FileNotFoundError:
        print(f"coverage is stale: {output_path} does not exist; regenerate it")
        return 1
    if current != rendered.encode("utf-8"):
        print(f"coverage is stale: {output_path}; run tools/generate_coverage.py")
        return 1
    print(f"coverage is current: {output_path}")
    return 0


def write_output(output_path: Path, rendered: str) -> None:
    """Write deterministic UTF-8 bytes without platform newline translation."""
    output_path.write_bytes(rendered.encode("utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit nonzero if docs/COVERAGE.md differs; never write",
    )
    args = parser.parse_args(argv)

    rendered = render_coverage(load_methods())
    if args.check:
        return check_output(OUTPUT, rendered)
    write_output(OUTPUT, rendered)
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
