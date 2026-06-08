#!/usr/bin/env python3
"""Dry-run mutation playbook runner skeleton.

This module intentionally does not implement mutation calls. It validates that
an operator selected a playbook, supplied fixture environment, and provided
explicit approval before future code is allowed to execute a mutation.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


PLAYBOOKS = {
    "bookmarks": "bookmarks.md",
    "external-events": "external-events.md",
    "export": "export.md",
    "macros": "macros.md",
    "device-templates": "device-templates.md",
    "users-roles-security": "users-roles-security.md",
    "archive-management": "archive-management.md",
    "detector-parameters": "detector-parameters.md",
    "maps-markers": "maps-markers.md",
    "ptz-control": "ptz-control.md",
}

REQUIRED_ENV = ["AXXON_HOST", "AXXON_USERNAME", "AXXON_PASSWORD"]


def playbook_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "docs/api-audit/mutation-playbooks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List available mutation playbooks.")
    parser.add_argument("--playbook", choices=sorted(PLAYBOOKS), help="Playbook to validate.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Validate only; default and currently required.")
    parser.add_argument("--i-understand-this-mutates", action="store_true", help="Required before any future mutation execution.")
    parser.add_argument("--confirm", help="Must equal CONFIRM-<playbook> for non-dry-run execution.")
    return parser


def validate_environment() -> list[str]:
    return [name for name in REQUIRED_ENV if not os.getenv(name)]


def playbook_path(name: str) -> Path:
    return playbook_dir() / PLAYBOOKS[name]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.list:
        print(json.dumps({"playbooks": sorted(PLAYBOOKS)}, indent=2))
        return 0
    if not args.playbook:
        parser.error("--playbook is required unless --list is used")
    missing_env = validate_environment()
    path = playbook_path(args.playbook)
    result = {
        "playbook": args.playbook,
        "path": str(path),
        "path_exists": path.exists(),
        "dry_run": True,
        "missing_env": missing_env,
        "approved": bool(args.i_understand_this_mutates),
        "confirmation_ok": args.confirm == f"CONFIRM-{args.playbook}",
        "will_mutate": False,
    }
    if not result["path_exists"]:
        result["error"] = "playbook file is missing"
    elif missing_env:
        result["error"] = "required fixture environment is missing"
    elif not args.i_understand_this_mutates:
        result["error"] = "explicit mutation approval flag is missing"
    elif not result["confirmation_ok"]:
        result["error"] = "playbook-specific confirmation string is missing"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if "error" not in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
