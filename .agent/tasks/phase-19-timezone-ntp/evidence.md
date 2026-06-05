# Evidence Bundle: phase-19-timezone-ntp

## Summary
- Overall status: PASS (all 6 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — module + gating idiom — PASS
- `tools/axxon_mcp_timezone.py` (`AxxonMcpTimezone`) exposes reads `list_timezones`,
  `get_timezone`, `get_ntp` and gated writes `set_timezone`, `set_ntp`,
  `change_timezones`. `_write_gate` returns `disabled` (env unset) / `gap` (bad
  token) before any wire call. Env `AXXON_TIMEZONE_APPROVE=1` + confirmation
  `CONFIRM-timezone-set`.
- Proof: `GatingTests` (disabled/gap, no calls recorded); live `[gating]` block
  in raw/live-verify.txt.

## AC2 — set_timezone build + readback — PASS
- Sets the BoolValue `daylight_saving_mode_off` only when provided (CopyFrom),
  sends SetTimeZone, reads back current timezone. Empty id -> error, no wire call.
- Proof: `SetTimeZoneTests` (dst bool conditional, set then GetTimeZone order),
  `EmptyInputTests.test_set_timezone_requires_id`; live UTC round-trip.

## AC3 — set_ntp + change_timezones — PASS
- `set_ntp` builds NTP with a Duration only when `refresh_rate_s` is given.
  `change_timezones` supports removed_zones + added_zones[{id,name}]; no edit ->
  error, no wire call.
- Proof: `SetNTPTests` (duration conditional), `ChangeTimeZonesTests`
  (add/remove request shape), `EmptyInputTests.test_change_timezones_no_edit_errors`;
  live NTP + database round-trips.

## AC4 — server registration — PASS
- 6-edit pattern in `tools/axxon_mcp_server.py`: `timezone` param,
  `register_timezone_tools` call, the function (7 tools), `--enable-timezone`
  flag, flag-gated instantiation, passed to `create_server`.
- Proof: raw/test-unit.txt (server import OK).

## AC5 — unit + full suite green — PASS
- 14 new tests. Full suite `Ran 760 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp + coverage doc — PASS
- SetTimeZone, SetNTP, ChangeTimeZones -> tested-pass. Coverage 193 pass-class /
  130 pending / 38 fixture-warn; TimeZoneManager 7/7. raw/live-verify.txt shows
  each reversible round-trip.

## Stand hygiene
- TZ set to UTC then restored to Arabian Standard Time; NTP set then cleared to
  the original empty state; a throwaway zone added then removed. Stand ends
  unchanged. No proto/CA/PDF committed; secrets env-only; no biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`, the throwaway
  zone GUID shown as `<uuid>`.
