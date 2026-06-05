from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_timezone as module


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


class _Bool:
    def __init__(self, value=False):
        self.value = value

    def CopyFrom(self, other):
        self.value = other.value


class _Dur:
    def __init__(self, seconds=0):
        self.seconds = seconds

    def CopyFrom(self, other):
        self.seconds = other.seconds


class _CurTZ:
    def __init__(self, timezone_id="Arabian Standard Time", timezone_name="UTC+04:00"):
        self.timezone_id = timezone_id
        self.timezone_name = timezone_name


class _GetTZResp:
    def __init__(self, current=None, dst_off=False, available=None):
        self.current_timezone = current or _CurTZ()
        self.daylight_saving_mode_off = _Bool(dst_off)
        self.available_timezones = available or [_CurTZ("UTC", "UTC+00:00")]


class _TimeZone:
    def __init__(self, id="", name="", intervals=None):
        self.id = id
        self.name = name
        self.intervals = intervals or []


class _ListTZResp:
    def __init__(self, items=None):
        self.items = items or [_TimeZone("zone-1", "default")]


class _ListReq:
    VIEW_MODE_STRIPPED, VIEW_MODE_FULL = 0, 1

    def __init__(self, view=0):
        self.view = view


class _NTP:
    def __init__(self, ntp_url="", sync_ip_devices=False, refresh_rate=None):
        self.ntp_url = ntp_url
        self.sync_ip_devices = sync_ip_devices
        self.refresh_rate = refresh_rate if refresh_rate is not None else _Dur()


class _ListNTPResp:
    def __init__(self, ntp=None):
        self.ntp = ntp or _NTP()


class _SetTZReq:
    def __init__(self, timezone_id=""):
        self.timezone_id = timezone_id
        self.daylight_saving_mode_off = _Bool()


class _SetNTPReq:
    def __init__(self, ntp=None):
        self.ntp = ntp


class _ChangeReq:
    def __init__(self, removed_zones=None):
        self.removed_zones = list(removed_zones or [])
        self.added_zones = []


class _Empty:
    def __init__(self, **kw):
        pass


class _TZPb2:
    ListTimeZonesRequest = _ListReq
    GetTimeZoneRequest = _Empty
    ListNTPRequest = _Empty
    SetTimeZoneRequest = _SetTZReq
    SetNTPRequest = _SetNTPReq
    ChangeTimeZonesRequest = _ChangeReq
    NTP = _NTP
    TimeZone = _TimeZone


class _FakeStub:
    def __init__(self, recorder, get_tz=None, ntp=None, listing=None):
        self._rec = recorder
        self._get_tz = get_tz or _GetTZResp()
        self._ntp = ntp or _ListNTPResp()
        self._listing = listing or _ListTZResp()

    def ListTimeZones(self, request, timeout=None):
        self._rec.append(("ListTimeZones", request, timeout))
        return self._listing

    def GetTimeZone(self, request, timeout=None):
        self._rec.append(("GetTimeZone", request, timeout))
        return self._get_tz

    def GetNTP(self, request, timeout=None):
        self._rec.append(("GetNTP", request, timeout))
        return self._ntp

    def SetTimeZone(self, request, timeout=None):
        self._rec.append(("SetTimeZone", request, timeout))
        return _Empty()

    def SetNTP(self, request, timeout=None):
        self._rec.append(("SetNTP", request, timeout))
        return _Empty()

    def ChangeTimeZones(self, request, timeout=None):
        self._rec.append(("ChangeTimeZones", request, timeout))
        return _Empty()


class FakeTzClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "TimeZoneManager"
        return _FakeStub(self.calls)

    def import_module(self, name):
        return _TZPb2()


def _tz(**overrides):
    inst = module.AxxonMcpTimezone(
        client_factory=lambda config: FakeTzClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.timezone_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_get_timezone_shape(self) -> None:
        out = _tz().get_timezone()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["current_timezone"]["id"], "Arabian Standard Time")
        self.assertFalse(out["daylight_saving_mode_off"])
        self.assertEqual(out["available_count"], 1)

    def test_list_timezones_shape(self) -> None:
        out = _tz().list_timezones()
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["items"][0]["id"], "zone-1")

    def test_get_ntp_shape(self) -> None:
        out = _tz().get_ntp()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["ntp_url"], "")


class GatingTests(unittest.TestCase):
    def test_set_timezone_disabled(self) -> None:
        inst = _tz(enabled=False)
        out = inst.set_timezone("UTC", confirmation=module.TIMEZONE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_set_timezone_bad_token(self) -> None:
        inst = _tz(enabled=True)
        out = inst.set_timezone("UTC", confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_set_ntp_disabled(self) -> None:
        inst = _tz(enabled=False)
        out = inst.set_ntp("pool.ntp.org", confirmation=module.TIMEZONE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_change_timezones_bad_token(self) -> None:
        inst = _tz(enabled=True)
        out = inst.change_timezones(removed_zones=["x"], confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])


class EmptyInputTests(unittest.TestCase):
    def test_set_timezone_requires_id(self) -> None:
        inst = _tz(enabled=True)
        out = inst.set_timezone("", confirmation=module.TIMEZONE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_change_timezones_no_edit_errors(self) -> None:
        inst = _tz(enabled=True)
        out = inst.change_timezones(confirmation=module.TIMEZONE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class SetTimeZoneTests(unittest.TestCase):
    def test_dst_bool_only_when_provided(self) -> None:
        inst = _tz(enabled=True)
        inst.set_timezone("UTC", confirmation=module.TIMEZONE_CONFIRMATION)
        kinds = [c[0] for c in inst.client.calls]
        self.assertEqual(kinds, ["SetTimeZone", "GetTimeZone"])  # set then readback
        req = inst.client.calls[0][1]
        self.assertEqual(req.timezone_id, "UTC")
        self.assertFalse(req.daylight_saving_mode_off.value)  # untouched default

    def test_dst_bool_set(self) -> None:
        inst = _tz(enabled=True)
        inst.set_timezone("UTC", daylight_saving_mode_off=True, confirmation=module.TIMEZONE_CONFIRMATION)
        req = inst.client.calls[0][1]
        self.assertTrue(req.daylight_saving_mode_off.value)


class SetNTPTests(unittest.TestCase):
    def test_duration_only_when_provided(self) -> None:
        inst = _tz(enabled=True)
        inst.set_ntp("pool.ntp.org", sync_ip_devices=True, confirmation=module.TIMEZONE_CONFIRMATION)
        req = inst.client.calls[0][1]
        self.assertEqual(req.ntp.ntp_url, "pool.ntp.org")
        self.assertTrue(req.ntp.sync_ip_devices)
        self.assertEqual(req.ntp.refresh_rate.seconds, 0)  # not set

    def test_duration_set(self) -> None:
        inst = _tz(enabled=True)
        inst.set_ntp("pool.ntp.org", refresh_rate_s=3600, confirmation=module.TIMEZONE_CONFIRMATION)
        req = inst.client.calls[0][1]
        self.assertEqual(req.ntp.refresh_rate.seconds, 3600)


class ChangeTimeZonesTests(unittest.TestCase):
    def test_add_and_remove_shape(self) -> None:
        inst = _tz(enabled=True)
        out = inst.change_timezones(
            removed_zones=["old-id"],
            added_zones=[{"id": "new-id", "name": "probe"}],
            confirmation=module.TIMEZONE_CONFIRMATION,
        )
        self.assertEqual(out["status"], "applied")
        req = inst.client.calls[0][1]
        self.assertEqual(list(req.removed_zones), ["old-id"])
        self.assertEqual(req.added_zones[0].id, "new-id")
        self.assertEqual(req.added_zones[0].name, "probe")


if __name__ == "__main__":
    unittest.main()
