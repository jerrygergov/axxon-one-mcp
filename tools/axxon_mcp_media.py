#!/usr/bin/env python3
"""MediaService transport-probe tools for the Axxon One MCP server (Phase 44).

Wraps the unary endpoints of `axxonsoft.bl.media.MediaService` plus a bounded liveness probe of
the bidirectional `Stream` RPC. These establish or query transport for a media endpoint; they do
not change configuration, so there is no write gate.

Tools:
- request_connection: ask the server for a transport cookie + connection info for a media endpoint
- request_qos: apply a quality-of-service hint (frame rate) to an established connection
- request_tunnel: open an RPC tunnel to a node and return its transport config
- stream_probe: open the pull stream, send one MediaRequest, read up to N samples, report sample
  oneof types only

Every result is metadata only: cookie presence (never the raw cookie or token), transport name,
port/byte counts, and sample-type tallies. Raw media bytes are never returned.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

MEDIA_SERVICE_PROTO = "axxonsoft/bl/media/MediaService.proto"
MEDIA_SERVICE_PB2 = "axxonsoft.bl.media.MediaService_pb2"
MEDIA_PB2 = "axxonsoft.bl.media.Media_pb2"

TRANSPORT_TCP = "NETWORK_TRANSPORT_TCP"
MAX_STREAM_SAMPLES = 4

MEDIA_TOOL_NAMES = (
    "media_connect_axxon_profile",
    "request_connection",
    "request_qos",
    "request_tunnel",
    "stream_probe",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpMedia:
    """MediaService transport-probe tools (Phase 44). Metadata-only, no write gate."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def media_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.media_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.media_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        stub = client.stub_from_proto(MEDIA_SERVICE_PROTO, "MediaService")
        return stub, client.import_module(MEDIA_SERVICE_PB2), client.import_module(MEDIA_PB2)

    def _timeout(self) -> Any:
        return self.ensure_client().config.timeout

    def request_connection(self, endpoint: str = "", pid: int = 0, host_id: str = "Server") -> dict[str, Any]:
        """Request a transport cookie + connection info for a media endpoint (e.g. .../SourceEndpoint.video:0:0)."""
        if not endpoint:
            return {"status": "error", "tool": "request_connection", "message": "provide a media endpoint access point"}
        stub, service_pb2, media_pb2 = self._stub_and_pb2()
        request = service_pb2.RequestConnectionRequest(
            endpoint=media_pb2.EndpointRef(access_point=endpoint),
            data=service_pb2.RequestConnectionData(pid=int(pid), host_id=host_id, transport_preferences=[media_pb2.NETWORK_TRANSPORT_TCP]))
        response = stub.RequestConnection(request, timeout=self._timeout())
        info = response.connection_info
        return {"status": "ok", "tool": "request_connection", "endpoint": endpoint,
                "cookie_present": bool(response.cookie), "transport": media_pb2.ENetworkTransport.Name(info.transport)}

    def request_qos(self, endpoint: str = "", fps: float = 5.0) -> dict[str, Any]:
        """Apply a frame-rate QoS hint to a freshly established connection for a media endpoint."""
        if not endpoint:
            return {"status": "error", "tool": "request_qos", "message": "provide a media endpoint access point"}
        stub, service_pb2, media_pb2 = self._stub_and_pb2()
        ref = media_pb2.EndpointRef(access_point=endpoint)
        connection = stub.RequestConnection(service_pb2.RequestConnectionRequest(
            endpoint=ref, data=service_pb2.RequestConnectionData(pid=0, host_id="Server", transport_preferences=[media_pb2.NETWORK_TRANSPORT_TCP])),
            timeout=self._timeout())
        qos = media_pb2.QualityOfServiceRequest(frameRate=media_pb2.QualityOfServiceRequest.FrameRate(fps=float(fps)))
        stub.RequestQoS(service_pb2.RequestQoSRequest(endpoint=ref, cookie=connection.cookie, qos=[qos]), timeout=self._timeout())
        return {"status": "ok", "tool": "request_qos", "endpoint": endpoint, "fps": float(fps)}

    def request_tunnel(self, node: str = "Server", name: str = "") -> dict[str, Any]:
        """Open an RPC tunnel to a node and report its transport config (tcp port presence + cookie presence)."""
        stub, service_pb2, media_pb2 = self._stub_and_pb2()
        tunnel_name = name or uuid.uuid4().hex
        response = stub.RequestTunnel(service_pb2.TunnelRequest(node=node, name=tunnel_name, proto=media_pb2.NETWORK_TRANSPORT_TCP), timeout=self._timeout())
        config = response.config
        return {"status": "ok", "tool": "request_tunnel", "node": node, "proto": config.WhichOneof("proto"),
                "cookie_present": bool(config.cookie), "endpoint_present": bool(config.endpoint)}

    def stream_probe(self, endpoint: str = "", max_samples: int = MAX_STREAM_SAMPLES, channel_idle_ms: int = 5000) -> dict[str, Any]:
        """Open the pull stream for a media endpoint, send one request, and tally up to N sample types."""
        if not endpoint:
            return {"status": "error", "tool": "stream_probe", "message": "provide a media endpoint access point"}
        stub, service_pb2, media_pb2 = self._stub_and_pb2()
        ref = media_pb2.EndpointRef(access_point=endpoint)
        cap = max(1, min(int(max_samples), MAX_STREAM_SAMPLES))

        def requests():
            yield service_pb2.MediaRequest(count=cap, endpoint=ref, proposed_channel_idle_ms=int(channel_idle_ms))

        counts: dict[str, int] = {}
        seen = 0
        for sample in stub.Stream(requests(), timeout=self._timeout()):
            which = sample.WhichOneof("data") or "unknown"
            counts[which] = counts.get(which, 0) + 1
            seen += 1
            if seen >= cap:
                break
        return {"status": "ok", "tool": "stream_probe", "endpoint": endpoint, "samples": seen, "sample_types": counts}
