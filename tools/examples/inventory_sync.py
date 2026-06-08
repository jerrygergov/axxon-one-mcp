#!/usr/bin/env python3
"""Example: load Axxon One inventory through direct gRPC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = AxxonApiClient(config_from_args(args))
    inventory = client.load_inventory()
    cameras = inventory.get("cameras", [])
    archives = inventory.get("archives", [])
    components = inventory.get("components", [])
    result = {
        "version": inventory.get("version", {}),
        "node_count": len(inventory.get("nodes", [])),
        "camera_count": len(cameras),
        "archive_count": len(archives),
        "component_count": len(components),
        "cameras": [
            {
                "access_point": item.get("access_point"),
                "display_id": item.get("display_id"),
                "display_name": item.get("display_name"),
                "enabled": item.get("enabled"),
            }
            for item in cameras
        ],
        "archives": [
            {
                "access_point": item.get("access_point"),
                "display_name": item.get("display_name"),
                "enabled": item.get("enabled"),
            }
            for item in archives
        ],
    }
    print(json.dumps(client.sanitize(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

