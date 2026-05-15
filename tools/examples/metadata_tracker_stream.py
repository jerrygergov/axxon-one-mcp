#!/usr/bin/env python3
"""Example: read object-tracker metadata samples from a VMDA endpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--endpoint", help="VMDA endpoint access point. Defaults to the first AVDetector VMDA endpoint.")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--idle-ms", type=int, default=15000)
    parser.add_argument("--try-candidates", action="store_true", help="Try VMDA endpoints and use the first one with a sample.")
    parser.add_argument("--candidate-timeout", type=float, default=5.0)
    parser.add_argument("--preferred-camera", help="Prefer VMDA endpoints mapped to a camera display name substring.")
    return parser.parse_args()


def vmda_candidates(client: AxxonApiClient) -> list[str]:
    inventory = client.load_inventory()
    return [
        item.get("access_point", "")
        for item in inventory.get("components", [])
        if str(item.get("access_point", "")).endswith("/SourceEndpoint.vmda")
    ]


def cameras_by_component(client: AxxonApiClient, endpoint: str) -> list[dict[str, Any]]:
    domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")
    domain = client.common_stubs()["domain"]
    request = domain_pb2.GetCamerasByComponentsRequest(
        items=[domain_pb2.ResourceLocator(access_point=endpoint)]
    )
    cameras: list[dict[str, Any]] = []
    for page in domain.GetCamerasByComponents(request, timeout=client.config.timeout):
        cameras.extend(client.message_to_dict(page).get("items", []))
    return cameras


def candidate_sort_key(client: AxxonApiClient, endpoint: str, preferred_camera: str | None) -> tuple[int, int, str]:
    if not preferred_camera:
        return (0, 0 if "AVDetector" in endpoint else 1, endpoint)
    try:
        cameras = cameras_by_component(client, endpoint)
    except Exception:
        cameras = []
    preferred = preferred_camera.casefold()
    mapped_names = " ".join(str(camera.get("display_name", "")) for camera in cameras).casefold()
    return (0 if preferred in mapped_names else 1, 0 if "AVDetector" in endpoint else 1, endpoint)


def try_pull_metadata_sample(
    client: AxxonApiClient,
    endpoint: str,
    *,
    samples: int = 1,
    idle_ms: int = 5000,
    timeout: float = 5.0,
) -> dict[str, Any]:
    metadata_pb2 = client.import_module("axxonsoft.bl.metadata.MetadataService_pb2")
    metadata = client.stub_from_proto("axxonsoft/bl/metadata/MetadataService.proto", "MetadataService")
    media_pb2 = client.import_module("axxonsoft.bl.media.Media_pb2")

    def requests() -> Any:
        yield metadata_pb2.PullMetadataRequest(
            count=max(1, samples),
            endpoint=media_pb2.EndpointRef(access_point=endpoint),
            proposed_channel_idle_ms=idle_ms,
        )
        while True:
            time.sleep(0.25)
            yield metadata_pb2.PullMetadataRequest(count=1)

    result: dict[str, Any] = {
        "endpoint": endpoint,
        "samples": 0,
        "tracklets_seen": 0,
        "config_updates": 0,
        "heartbeats": 0,
    }
    for response in metadata.PullMetadata(requests(), timeout=timeout):
        data = client.message_to_dict(response)
        if "sample" in data:
            sample = data["sample"]
            result["samples"] += 1
            result["tracklets_seen"] += len(sample.get("tracklets", {}).get("tracklets", []))
            result["first_timestamp"] = result.get("first_timestamp") or sample.get("timestamp")
            if result["samples"] >= samples:
                break
        elif "config_update" in data:
            result["config_updates"] += 1
        elif "heartbeat" in data:
            result["heartbeats"] += 1
    return result


def choose_vmda_endpoint(
    client: AxxonApiClient,
    explicit: str | None,
    *,
    try_candidates: bool = False,
    candidate_timeout: float = 5.0,
    preferred_camera: str | None = None,
) -> str:
    if explicit:
        return explicit
    candidates = vmda_candidates(client)
    candidates = sorted(candidates, key=lambda item: candidate_sort_key(client, item, preferred_camera))
    if try_candidates:
        failures = []
        for endpoint in candidates:
            try:
                sample = try_pull_metadata_sample(
                    client,
                    endpoint,
                    samples=1,
                    idle_ms=5000,
                    timeout=candidate_timeout,
                )
                if sample.get("samples", 0) > 0:
                    return endpoint
                failures.append({"endpoint": endpoint, "reason": "no sample"})
            except Exception as exc:
                failures.append({"endpoint": endpoint, "reason": exc.__class__.__name__})
        if failures:
            print(json.dumps({"candidate_results": failures}, indent=2, ensure_ascii=True), file=sys.stderr)
    preferred = next((item for item in candidates if "AVDetector" in item), candidates[0] if candidates else "")
    if not preferred:
        raise RuntimeError("no VMDA endpoint found")
    return preferred


def main() -> int:
    args = parse_args()
    client = AxxonApiClient(config_from_args(args))
    client.authenticate_grpc()
    endpoint = choose_vmda_endpoint(
        client,
        args.endpoint,
        try_candidates=args.try_candidates,
        candidate_timeout=args.candidate_timeout,
        preferred_camera=args.preferred_camera,
    )
    metadata_pb2 = client.import_module("axxonsoft.bl.metadata.MetadataService_pb2")
    metadata = client.stub_from_proto("axxonsoft/bl/metadata/MetadataService.proto", "MetadataService")
    media_pb2 = client.import_module("axxonsoft.bl.media.Media_pb2")

    def requests() -> Any:
        yield metadata_pb2.PullMetadataRequest(
            count=max(1, args.samples),
            endpoint=media_pb2.EndpointRef(access_point=endpoint),
            proposed_channel_idle_ms=args.idle_ms,
        )
        while True:
            time.sleep(0.5)
            yield metadata_pb2.PullMetadataRequest(count=1)

    samples: list[dict[str, Any]] = []
    config_updates = 0
    heartbeats = 0
    for response in metadata.PullMetadata(requests(), timeout=client.config.timeout):
        data = client.message_to_dict(response)
        if "sample" in data:
            sample = data["sample"]
            samples.append(
                {
                    "timestamp": sample.get("timestamp"),
                    "tracklet_count": len(sample.get("tracklets", {}).get("tracklets", [])),
                    "shape": client.shape(sample),
                }
            )
            if len(samples) >= args.samples:
                break
        elif "config_update" in data:
            config_updates += 1
        elif "heartbeat" in data:
            heartbeats += 1

    result = {
        "endpoint": endpoint,
        "samples": len(samples),
        "config_updates": config_updates,
        "heartbeats": heartbeats,
        "items": samples,
    }
    print(json.dumps(client.sanitize(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
