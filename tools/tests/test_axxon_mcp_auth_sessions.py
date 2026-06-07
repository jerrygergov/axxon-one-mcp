from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_auth_sessions as module


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


class _AuthResp:
    def __init__(self, token="tok-SECRET", expires_in=3600, user_id="u1", error_code=0):
        self.token_value = token
        self.expires_in = expires_in
        self.user_id = user_id
        self.error_code = error_code


class _CloseResp:
    class EErrorCode:
        @staticmethod
        def Name(code):
            return {0: "OK", 1: "GENERAL_ERROR"}.get(code, str(code))

    def __init__(self, error_code=0):
        self.error_code = error_code


class _AuthReq:
    def __init__(self, user_name="", password=""):
        self.user_name = user_name
        self.password = password


class _Empty:
    def __init__(self):
        pass


class _Pb2:
    AuthenticateRequest = _AuthReq
    RenewSessionRequest = _Empty
    CloseSessionRequest = _Empty
    CloseSessionResponse = _CloseResp


class _Stub:
    def __init__(self, rec, authed):
        self._rec = rec
        self._authed = authed

    def Authenticate(self, request, timeout=None):
        self._rec.append(("Authenticate", request.user_name))
        return _AuthResp()

    def Authenticate2(self, request, timeout=None):
        self._rec.append(("Authenticate2", request.user_name))
        return _AuthResp()

    def AuthenticateEx(self, request, timeout=None):
        self._rec.append(("AuthenticateEx", request.user_name))
        return _AuthResp()

    def RenewSession(self, request, timeout=None):
        self._rec.append(("RenewSession",))
        return _AuthResp()

    def RenewSession2(self, request, timeout=None):
        self._rec.append(("RenewSession2",))
        return _AuthResp()

    def CloseSession(self, request, timeout=None):
        self._rec.append(("CloseSession",))
        return _CloseResp(0)


class _StubFactory:
    def __init__(self, rec):
        self._rec = rec

    def AuthenticationServiceStub(self, channel):
        return _Stub(self._rec, channel == "authed")


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []
        self.grpc_channel = "authed"
        self.pb = {"auth_grpc": _StubFactory(self.calls), "auth_pb2": _Pb2()}

    def authenticate_grpc(self):
        return None

    def prepare_grpc(self):
        return None

    def connect_grpc(self):
        return "unauthed"

    def import_module(self, name):
        return _Pb2()


def _inst(**overrides):
    inst = module.AxxonMcpAuthSessions(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.auth_sessions_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_authenticate_ok_no_token_value(self) -> None:
        out = _inst().authenticate(user_name="root", password="x", variant="Authenticate")
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["token_present"])
        self.assertNotIn("tok-SECRET", str(out))

    def test_authenticate_variant2(self) -> None:
        inst = _inst()
        out = inst.authenticate(user_name="root", password="x", variant="Authenticate2")
        self.assertEqual(out["variant"], "Authenticate2")
        self.assertEqual(inst.client.calls[0][0], "Authenticate2")

    def test_authenticate_empty_creds_no_wire(self) -> None:
        inst = _inst()
        out = inst.authenticate(user_name="", password="x")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_authenticate_bad_variant_no_wire(self) -> None:
        inst = _inst()
        out = inst.authenticate(user_name="root", password="x", variant="Nope")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_renew_session_ok(self) -> None:
        out = _inst().renew_session(variant="RenewSession2")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["error_code"], 0)
        self.assertTrue(out["token_present"])

    def test_renew_bad_variant_no_wire(self) -> None:
        inst = _inst()
        out = inst.renew_session(variant="Nope")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class GateTests(unittest.TestCase):
    def test_close_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.close_session(confirmation=module.AUTH_SESSIONS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_close_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.close_session(confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])


class WriteTests(unittest.TestCase):
    def test_close_applied_ok(self) -> None:
        inst = _inst(enabled=True)
        out = inst.close_session(confirmation=module.AUTH_SESSIONS_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["error_name"], "OK")
        self.assertEqual(inst.client.calls[0][0], "CloseSession")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.close_session(confirmation=module.AUTH_SESSIONS_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
