#!/usr/bin/env python3
"""Example: combine camera inventory with archive health/status."""

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
    archive_pb2 = client.import_module("axxonsoft.bl.archive.ArchiveSupport_pb2")
    archive = client.common_stubs()["archive"]
    archive_ap = client.archive_access_point()

    traits = archive.GetArchiveTraits(
        archive_pb2.GetArchiveTraitsRequest(access_point=archive_ap),
        timeout=client.config.timeout,
    )
    state = archive.GetVolumesState(
        archive_pb2.GetVolumesStateRequest(access_point=archive_ap),
        timeout=client.config.timeout,
    )
    volume_id = client.archive_volume_id()
    disk = archive.GetDiskSpace(
        archive_pb2.GetDiskSpaceRequest(storage_access_point=archive_ap, volume_id=volume_id),
        timeout=client.config.timeout,
    )

    result = {
        "camera_count": len(inventory.get("cameras", [])),
        "cameras": [
            {
                "display_id": item.get("display_id"),
                "display_name": item.get("display_name"),
                "access_point": item.get("access_point"),
                "enabled": item.get("enabled"),
            }
            for item in inventory.get("cameras", [])
        ],
        "archive": {
            "access_point": archive_ap,
            "source_access_point": client.archive_source_access_point(),
            "volume_id": volume_id,
            "traits_shape": client.shape_protobuf(traits),
            "volumes_shape": client.shape_protobuf(state),
            "disk_shape": client.shape_protobuf(disk),
        },
    }
    print(json.dumps(client.sanitize(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

