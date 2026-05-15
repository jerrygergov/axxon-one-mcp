#!/usr/bin/env python3
"""Example: compare one direct gRPC call with the HTTP /grpc wrapper."""

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
    client.authenticate_grpc()

    domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")
    domain = client.common_stubs()["domain"]
    grpc_response = domain.GetVersion(domain_pb2.GetVersionRequest(), timeout=client.config.timeout)
    grpc_body = client.message_to_dict(grpc_response)

    http_response = client.http_grpc("axxonsoft.bl.domain.DomainService.GetVersion", {})
    result = {
        "direct_grpc": {
            "shape": client.shape(grpc_body),
            "body": grpc_body,
        },
        "http_grpc": {
            "status": http_response["status"],
            "content_type": http_response["content_type"],
            "shape": client.shape(http_response.get("body")),
            "body": http_response.get("body"),
        },
        "same_version": grpc_body.get("Version") == (http_response.get("body") or {}).get("Version"),
    }
    print(json.dumps(client.sanitize(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

