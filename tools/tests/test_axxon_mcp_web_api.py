from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_web_api as module


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


class FakeClient:
    def __init__(self, config):
        self.config = config

    def sanitize(self, value):
        return value


class _FakeSocket:
    """Minimal duck-typed socket for the WS handshake/sample tests."""

    def __init__(self, handshake: bytes, frames: list[bytes]):
        self._chunks = [handshake, *frames]
        self.sent: list[bytes] = []
        self.timeout = None
        self.closed = False

    def settimeout(self, value):
        self.timeout = value

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, _n):
        if self._chunks:
            return self._chunks.pop(0)
        raise TimeoutError("no more data")

    def close(self):
        self.closed = True


_HANDSHAKE_101 = (
    b"HTTP/1.1 101 Switching Protocols\r\n"
    b"Connection: Upgrade\r\n"
    b"Upgrade: websocket\r\n"
    b"Sec-WebSocket-Accept: SECRET-ACCEPT-KEY\r\n\r\n"
)
_HANDSHAKE_404 = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"
# WS text frame "hi" (FIN+opcode 0x1, len 2) and a close frame (0x88).
_TEXT_FRAME = b"\x81\x02hi"
_CLOSE_FRAME = b"\x88\x02\x03\xef"


def _inst(handshake=_HANDSHAKE_101, frames=None):
    sockets: list[_FakeSocket] = []

    def socket_factory(host, port, timeout):
        sock = _FakeSocket(handshake, list(frames or []))
        sockets.append(sock)
        return sock

    inst = module.AxxonMcpWebApi(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
        socket_factory=socket_factory,
    )
    inst.web_api_connect_axxon_profile("env")
    inst._test_sockets = sockets  # type: ignore[attr-defined]
    return inst


class ConnectTests(unittest.TestCase):
    def test_connect_env_only_lazy_and_redacts_secrets(self) -> None:
        created = []
        inst = module.AxxonMcpWebApi(
            client_factory=lambda config: created.append(config) or FakeClient(config),
            config_factory=lambda: FakeConfig(),
        )
        self.assertIsNone(inst.client)
        rejected = inst.web_api_connect_axxon_profile("prod")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(created, [])

        out = inst.web_api_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))
        self.assertNotIn("password", out["profile"])
        self.assertTrue(out["profile"]["password_present"])


class EmbeddableTests(unittest.TestCase):
    def test_component_url_builds_iframe_src_no_credentials(self) -> None:
        out = _inst().embeddable_component_url(
            camera_origin="Server/DeviceIpint.1/SourceEndpoint.video:0:0", mode="live"
        )
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["url"].startswith("http://example.local/embedded.html"))
        self.assertIn("<iframe", out["iframe_snippet"])
        self.assertIn("/embedded.html", out["iframe_snippet"])
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))
        self.assertNotIn("root:", out["url"])

    def test_component_url_rejects_bad_mode(self) -> None:
        out = _inst().embeddable_component_url(camera_origin="cam/x", mode="bogus")
        self.assertEqual(out["status"], "error")

    def test_component_commands_catalog_matches_doc(self) -> None:
        out = _inst().embeddable_component_commands()
        self.assertEqual(out["status"], "ok")
        types = {c["type"] for c in out["commands"]}
        self.assertTrue({"init", "reInit", "setTime", "setCamera"}.issubset(types))
        self.assertIn("ISO 8601", out["notes"])

    def test_component_commands_offline_no_socket(self) -> None:
        inst = _inst()
        inst.embeddable_component_commands()
        self.assertEqual(inst._test_sockets, [])


class WebEventsTests(unittest.TestCase):
    def test_probe_reports_101_metadata_only(self) -> None:
        inst = _inst(handshake=_HANDSHAKE_101)
        out = inst.web_events_probe(path="/events")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["http_status"], 101)
        self.assertTrue(out["upgraded"])
        self.assertTrue(out["is_known_event_path"])
        self.assertNotIn("SECRET-ACCEPT-KEY", str(out))

    def test_probe_rejects_unknown_path(self) -> None:
        inst = _inst()
        out = inst.web_events_probe(path="/secret-admin")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst._test_sockets, [])

    def test_probe_non_101_handshake(self) -> None:
        out = _inst(handshake=_HANDSHAKE_404).web_events_probe(path="/events")
        self.assertEqual(out["http_status"], 404)
        self.assertFalse(out["upgraded"])

    def test_sample_caps_frames_and_returns_no_raw_bytes(self) -> None:
        frames = [_TEXT_FRAME, _TEXT_FRAME, _TEXT_FRAME, _CLOSE_FRAME]
        inst = _inst(handshake=_HANDSHAKE_101, frames=frames)
        out = inst.web_events_sample(path="/events", max_frames=2)
        self.assertEqual(out["status"], "ok")
        self.assertLessEqual(out["frames"], 2)
        self.assertIn("opcode_tallies", out)
        self.assertNotIn("hi", str(out))
        self.assertNotIn("SECRET-ACCEPT-KEY", str(out))

    def test_sample_hard_cap_overrides_large_request(self) -> None:
        inst = _inst(handshake=_HANDSHAKE_101, frames=[_TEXT_FRAME] * 50)
        out = inst.web_events_sample(path="/events", max_frames=9999)
        self.assertLessEqual(out["frames"], module.MAX_EVENT_FRAMES)

    def test_sample_rejects_unknown_path(self) -> None:
        inst = _inst()
        out = inst.web_events_sample(path="/nope")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst._test_sockets, [])


class ParityTests(unittest.TestCase):
    def test_parity_report_offline(self) -> None:
        inst = _inst()
        out = inst.web_client_parity_report()
        self.assertEqual(out["status"], "ok")
        self.assertIn("surfaces", out)
        self.assertEqual(inst._test_sockets, [])


if __name__ == "__main__":
    unittest.main()
