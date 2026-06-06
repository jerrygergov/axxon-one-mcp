#!/usr/bin/env python3
"""Read-only DiscoveryService device-discovery tool for Axxon One MCP (Phase 12).

Scan the network for IP cameras to add (the desktop "search for devices" feature).
`discover_devices` starts a scan via `Discover`, then consumes the server-streaming
`GetDiscoveryProgress`, aggregating found devices until the scan finishes or the
device/time caps are hit. Adding a discovered device stays in the create_camera
operator workflow; this tool only reads.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import grpc

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

DISCOVERY_PROTO = "axxonsoft/bl/discovery/Discovery.proto"
DISCOVERY_PB2 = "axxonsoft.bl.discovery.Discovery_pb2"
EMPTY_PB2 = "google.protobuf.empty_pb2"
DEVICE_CAP = 1000
SECONDS_CAP = 120
FINISHED_STATES = {"PROGRESS_STATE_FINISHED", "PROGRESS_STATE_CANCELED", "PROGRESS_STATE_FAILED"}
_DEVICE_FIELDS = ("driver", "driver_version", "vendor", "model", "mac_address", "ip_address",
                  "ip_port", "firmware_version", "categories", "support_mode")

DISCOVERY_TOOL_NAMES = (
    "discovery_connect_axxon_profile",
    "discover_devices",
    "discover_node_devices",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _summarize_device(device: dict[str, Any]) -> dict[str, Any]:
    return {key: device[key] for key in _DEVICE_FIELDS if key in device}


@dataclass
class AxxonMcpDiscovery:
    """Phase 12 read-only network device-discovery tool."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def discovery_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read-only"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.discovery_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.discovery_connect_axxon_profile("env")
        return self.client

    def _drain_progress(self, client: Any, stream: Any, max_devices: int, max_seconds: float) -> tuple[list[dict[str, Any]], str, int, bool]:
        """Aggregate devices from a progress stream until a cap or finished state.

        A progress-stream DEADLINE_EXCEEDED (the scan has not produced results yet)
        is tolerated: draining stops and `timed_out` is True, keeping whatever
        devices were gathered. Other RpcErrors propagate.
        """
        devices: dict[str, dict[str, Any]] = {}
        state = "PROGRESS_STATE_RUNNING"
        promille = 0
        timed_out = False
        deadline = time.monotonic() + max_seconds
        try:
            for page in stream:
                data = client.message_to_dict(page)
                state = data.get("state", state)
                promille = data.get("promille", promille)
                for device in data.get("device_description", []):
                    key = device.get("mac_address") or device.get("ip_address") or repr(device)
                    if key not in devices:
                        devices[key] = _summarize_device(device)
                if len(devices) >= max_devices or state in FINISHED_STATES or time.monotonic() >= deadline:
                    break
        except grpc.RpcError as error:
            if error.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                raise
            timed_out = True
        finally:
            cancel = getattr(stream, "cancel", None)
            if callable(cancel):
                cancel()
        return list(devices.values())[:max_devices], state, promille, timed_out

    def discover_devices(self, max_devices: int = 200, max_seconds: float = 20.0) -> dict[str, Any]:
        max_devices = min(max(int(max_devices), 1), DEVICE_CAP)
        max_seconds = min(max(float(max_seconds), 1.0), SECONDS_CAP)
        client = self.ensure_client()
        client.authenticate_grpc()
        stub = client.stub_from_proto(DISCOVERY_PROTO, "DiscoveryService")
        empty = client.import_module(EMPTY_PB2)

        stub.Discover(empty.Empty(), timeout=client.config.timeout)
        stream = stub.GetDiscoveryProgress(empty.Empty(), timeout=client.config.timeout)
        device_list, state, promille, _ = self._drain_progress(client, stream, max_devices, max_seconds)
        return {
            "status": "ok",
            "discover_started": True,
            "state": state,
            "promille": promille,
            "count": len(device_list),
            "devices": device_list,
            "caps": {"max_devices": max_devices, "max_seconds": max_seconds},
        }

    def discover_node_devices(self, node: str = "", max_devices: int = 200, max_seconds: float = 20.0) -> dict[str, Any]:
        max_devices = min(max(int(max_devices), 1), DEVICE_CAP)
        max_seconds = min(max(float(max_seconds), 1.0), SECONDS_CAP)
        client = self.ensure_client()
        client.authenticate_grpc()
        stub = client.stub_from_proto(DISCOVERY_PROTO, "DiscoveryService")
        pb2 = client.import_module(DISCOVERY_PB2)

        stub.DiscoverNode(pb2.DiscoveryRequest(node=node), timeout=client.config.timeout)
        stream = stub.GetNodeDiscoveryProgress(pb2.DiscoveryRequest(node=node), timeout=client.config.timeout)
        device_list, state, promille, timed_out = self._drain_progress(client, stream, max_devices, max_seconds)
        return {
            "status": "ok",
            "discover_started": True,
            "node": node,
            "state": state,
            "promille": promille,
            "count": len(device_list),
            "devices": device_list,
            "progress_timed_out": timed_out,
            "caps": {"max_devices": max_devices, "max_seconds": max_seconds},
        }
