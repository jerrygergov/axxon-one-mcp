#!/usr/bin/env python3
"""Example: search recent events and print a compact summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import add_common_args
from axxon_event_search import AxxonEventSearch, print_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--node", default="")
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--begin")
    parser.add_argument("--end")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--ascending", action="store_true")
    parser.add_argument("--category", action="append", default=["detector"])
    parser.add_argument("--event-type", action="append", default=[])
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--camera", action="append", default=[])
    parser.add_argument("--camera-ap", action="append", default=[])
    parser.add_argument("--detector-ap", action="append", default=[])
    parser.add_argument("--value", action="append", default=[])
    parser.add_argument("--text", action="append", default=[])
    parser.add_argument("--alerts", action="store_true")
    parser.add_argument("--lpr", action="store_true")
    parser.add_argument("--plate", action="append", default=[])
    parser.add_argument("--predicate", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--save", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = AxxonEventSearch(args).run()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result, raw=args.raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

