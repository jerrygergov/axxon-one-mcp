from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_security_credentials as module


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


class _EResult:
    def __init__(self, mapping):
        self._m = mapping

    def Name(self, code):
        return self._m.get(code, str(code))


_CHECK = _EResult({0: "OK", 1: "NOT_UNIQUE", 2: "INVALID"})
_PWD = _EResult({0: "OK", 1: "NOT_UNIQUE_PASSWORD", 2: "WEAK_PASSWORD"})
_LOGIN = _EResult({0: "OK", 1: "NOT_UNIQUE_LOGIN", 2: "WEAK_LOGIN"})


class _Resp:
    def __init__(self, result):
        self.result = result


class _CheckReq:
    def __init__(self, user_id="", password=""):
        self.user_id = user_id
        self.password = password


class _PwdReq:
    def __init__(self, password=""):
        self.password = password


class _LoginReq:
    def __init__(self, login=""):
        self.login = login


class _CheckResp:
    EResult = _CHECK


class _PwdResp:
    EResult = _PWD


class _LoginResp:
    EResult = _LOGIN


class _Pb2:
    CheckPasswordRequest = _CheckReq
    ChangePasswordRequest = _PwdReq
    ChangeLoginRequest = _LoginReq
    CheckPasswordResponse = _CheckResp
    ChangePasswordResponse = _PwdResp
    ChangeLoginResponse = _LoginResp


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def CheckPassword(self, request, timeout=None):
        self._rec.append(("CheckPassword", request.user_id))
        return _Resp(1 if request.password == "current" else 0)

    def ChangePassword(self, request, timeout=None):
        self._rec.append(("ChangePassword",))
        return _Resp(0)

    def ChangeLogin(self, request, timeout=None):
        self._rec.append(("ChangeLogin", request.login))
        return _Resp(0)


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _Pb2()


def _inst(**overrides):
    inst = module.AxxonMcpSecurityCredentials(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.security_credentials_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_check_password_current_not_unique(self) -> None:
        out = _inst().check_password(user_id="u1", password="current")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["result_name"], "NOT_UNIQUE")

    def test_check_password_unused_ok(self) -> None:
        out = _inst().check_password(user_id="u1", password="fresh")
        self.assertEqual(out["result_name"], "OK")

    def test_check_password_empty_no_wire(self) -> None:
        inst = _inst()
        out = inst.check_password(user_id="", password="x")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class GateTests(unittest.TestCase):
    def test_password_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.change_my_password(password="x", confirmation=module.SECURITY_CREDENTIALS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_password_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_my_password(password="x", confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_password_error_on_empty_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_my_password(password="", confirmation=module.SECURITY_CREDENTIALS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_login_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.change_my_login(login="x", confirmation=module.SECURITY_CREDENTIALS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_login_error_on_empty_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_my_login(login="", confirmation=module.SECURITY_CREDENTIALS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class WriteTests(unittest.TestCase):
    def test_change_password_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_my_password(password="new", confirmation=module.SECURITY_CREDENTIALS_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["result_name"], "OK")
        self.assertEqual(inst.client.calls[0][0], "ChangePassword")

    def test_change_login_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_my_login(login="newlogin", confirmation=module.SECURITY_CREDENTIALS_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(inst.client.calls[0][0], "ChangeLogin")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_my_password(password="x", confirmation=module.SECURITY_CREDENTIALS_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
