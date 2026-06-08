from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_media as module


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_PASSWORD_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class _ConnInfo:
    def __init__(self):
        self.transport = 2


class _ConnResp:
    def __init__(self):
        self.cookie = "SECRET-COOKIE-not-returned"
        self.connection_info = _ConnInfo()


class _TunnelConfig:
    cookie = "SECRET-TUNNEL-COOKIE"
    endpoint = "tunnel-endpoint"

    def WhichOneof(self, field):
        return "tcp"


class _TunnelResp:
    def __init__(self):
        self.config = _TunnelConfig()


class _Sample:
    def __init__(self, which):
        self._which = which

    def WhichOneof(self, field):
        return self._which


class _ConnectResp:
    def __init__(self, status=0, keepalive_ms=3000):
        self.status = status
        self.keepalive_ms = keepalive_ms


class _EndpointRef:
    def __init__(self, access_point=""):
        self.access_point = access_point


class _ENetworkTransport:
    NETWORK_TRANSPORT_TCP = 2

    @staticmethod
    def Name(code):
        return {2: "NETWORK_TRANSPORT_TCP"}.get(code, str(code))


class _FrameRate:
    def __init__(self, fps=0.0):
        self.fps = fps


class _QoS:
    FrameRate = _FrameRate

    def __init__(self, frameRate=None):
        self.frameRate = frameRate


class _MediaPb2:
    EndpointRef = _EndpointRef
    NETWORK_TRANSPORT_TCP = 2
    ENetworkTransport = _ENetworkTransport
    QualityOfServiceRequest = _QoS


class _RequestConnectionData:
    def __init__(self, **kw):
        self.kw = kw


class _RequestConnectionRequest:
    def __init__(self, **kw):
        self.kw = kw


class _RequestQoSRequest:
    def __init__(self, **kw):
        self.kw = kw


class _TunnelRequest:
    def __init__(self, **kw):
        self.kw = kw


class _MediaRequest:
    def __init__(self, **kw):
        self.kw = kw


class _EStatus:
    @staticmethod
    def Name(code):
        return {0: "DONE", 1: "BUSY", 2: "LOST", 3: "FAIL"}.get(code, str(code))


class _ConnectEndpointResponse:
    EStatus = _EStatus


class _ConnectEndpointRequest:
    class Context:
        def __init__(self, **kw):
            self.kw = kw

    def __init__(self, **kw):
        self.kw = kw


class _ServicePb2:
    RequestConnectionData = _RequestConnectionData
    RequestConnectionRequest = _RequestConnectionRequest
    RequestQoSRequest = _RequestQoSRequest
    TunnelRequest = _TunnelRequest
    MediaRequest = _MediaRequest
    ConnectEndpointRequest = _ConnectEndpointRequest
    ConnectEndpointResponse = _ConnectEndpointResponse


_PB2_BY_NAME = {
    module.MEDIA_SERVICE_PB2: _ServicePb2,
    module.MEDIA_PB2: _MediaPb2,
}


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def RequestConnection(self, request, timeout=None):
        self._rec.append(("RequestConnection",))
        return _ConnResp()

    def RequestQoS(self, request, timeout=None):
        self._rec.append(("RequestQoS",))
        return object()

    def RequestTunnel(self, request, timeout=None):
        self._rec.append(("RequestTunnel",))
        return _TunnelResp()

    def Stream(self, requests, timeout=None):
        list(requests)
        self._rec.append(("Stream",))
        return iter([_Sample("config_update"), _Sample("body"), _Sample("body")])

    def ConnectEndpoint(self, requests, timeout=None):
        list(requests)
        self._rec.append(("ConnectEndpoint",))
        return iter([_ConnectResp(status=0, keepalive_ms=3332)])


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _PB2_BY_NAME[name]


def _inst():
    inst = module.AxxonMcpMedia(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    inst.media_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_request_connection_cookie_not_leaked(self) -> None:
        out = _inst().request_connection(endpoint="cam/SourceEndpoint.video:0:0")
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["cookie_present"])
        self.assertEqual(out["transport"], "NETWORK_TRANSPORT_TCP")
        self.assertNotIn("SECRET-COOKIE", str(out))

    def test_request_connection_empty_no_wire(self) -> None:
        inst = _inst()
        out = inst.request_connection(endpoint="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_request_qos_ok(self) -> None:
        inst = _inst()
        out = inst.request_qos(endpoint="cam/SourceEndpoint.video:0:0", fps=10.0)
        self.assertEqual(out["status"], "ok")
        self.assertEqual([c[0] for c in inst.client.calls], ["RequestConnection", "RequestQoS"])

    def test_request_qos_empty_no_wire(self) -> None:
        inst = _inst()
        out = inst.request_qos(endpoint="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_request_tunnel_metadata_only(self) -> None:
        out = _inst().request_tunnel(node="Server")
        self.assertEqual(out["proto"], "tcp")
        self.assertTrue(out["cookie_present"])
        self.assertNotIn("SECRET-TUNNEL", str(out))

    def test_stream_probe_bounded_types(self) -> None:
        out = _inst().stream_probe(endpoint="cam/SourceEndpoint.video:0:0", max_samples=2)
        self.assertEqual(out["samples"], 2)
        self.assertIn("config_update", out["sample_types"])

    def test_stream_probe_empty_no_wire(self) -> None:
        inst = _inst()
        out = inst.stream_probe(endpoint="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_connect_endpoint_done(self) -> None:
        module.CONNECT_HOLD_SECONDS = 0
        out = _inst().connect_endpoint(source_endpoint="cam50/SourceEndpoint.audio:0", sink_endpoint="cam54/SinkEndpoint.0")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["connection_status"], "DONE")
        self.assertTrue(out["connected"])
        self.assertEqual(out["keepalive_ms"], 3332)

    def test_connect_endpoint_missing_args_no_wire(self) -> None:
        inst = _inst()
        out = inst.connect_endpoint(source_endpoint="cam50/SourceEndpoint.audio:0", sink_endpoint="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


if __name__ == "__main__":
    unittest.main()
