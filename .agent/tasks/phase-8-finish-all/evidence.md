# Evidence: phase-8-finish-all (last three gaps closed)

## Summary
All three previously-open items are resolved. Two were FALSE gaps (same pattern as VMDA/archived-events:
a wrong/narrow read led to "impossible"); one is a genuine hard API limit, now proven.

## PTZ (ptz_controller) — CLOSED, live-verified
- False negative: "0 telemetry endpoints / no PTZ device" came from reading only the filtered inventory
  (200 components). The full config graph (DomainService.ListComponents, 501 components) has 3 real PTZ
  endpoints on `DeviceIpint.53` (TelemetryControl.0/1/2).
- New `tools/axxon_mcp_ptz.py` (`--enable-ptz`, 17 tools): discover sources from the full graph, session
  acquire/keepalive/release, get position, move/zoom/focus/iris (continuous/relative/absolute), absolute move,
  presets list/set/go/remove, auxiliary operations. No-PTZ cameras return a structured gap, not a crash.
- Live (AC4): acquire session -> read pos (pan 675/tilt 279) -> AbsoluteMove(120,60,8) -> read pos
  (pan 120/tilt 60, the device physically moved) -> restore to 675/279. The DeviceIpint.53 emulator driver
  rejects continuous Move/Zoom/GoPreset/Release with "error: 1" (driver capability limit, not a tool defect);
  the tool surfaces those as structured results. Raw: `raw/ptz-live-verify.json`.
- AC1/AC2/AC3: 8 unit tests (happy path + no-endpoint gap + bad-mode refusal). Server wiring: 1 test.

## 5F-B2 remainder — CLOSED, live-verified
- Added `security_user_credential_lifecycle` to `tools/axxon_mcp_admin_mutations.py`: create an ephemeral
  codex user (+temp role), change its login and password via SecurityService.ChangeConfig, verify the new
  login, then remove the user+role. Same approval gate (`AXXON_ADMIN_MUTATION_APPROVE=1`) and confirmation
  tokens as 5F-B1; only ever targets generated codex-* objects.
- Live (AC8): applied (login -> *_renamed, password changed), verified (login_changed=true), rolled-back
  (user_removed + role_removed). Post-check: stand has 35 users / 4 roles, ZERO codex leftovers. No password
  value leaked in any result. Raw: `raw/security-live-verify.json`.
- AC5/AC6/AC7: 2 new unit tests (full lifecycle + disabled-gate refusal); smoke fake-run now PASS=7.
- Out of scope, documented (not reversible / can brick the disposable stand): license_apply/license_drop,
  time_set_timezone/time_set_ntp, LDAP sync against a real directory.

## Schedules (schedule_descriptor_get) — CLOSED as a hard API limitation
- Proven impossible across every surface: 0 PDF pages mention schedule/calendar/weekly; no Create/Set schedule
  RPC or message in any proto (the only calendar surface, ArchiveSupport.GetCalendar, is read-only
  days-with-recordings); no schedule trigger in LogicService/Macro; 0 schedule objects in the 501-component
  config graph; no schedule unit type in ConfigurationService.ListUnits. Axxon schedules are desktop-client
  authored with no API representation. Raw: `raw/schedule-impossibility.json`.

## Tests (AC10)
```
python3.12 -m unittest discover -s tools/tests
Ran 682 tests, OK   (was 671)
```

## Files changed
- tools/axxon_mcp_ptz.py (new)
- tools/axxon_mcp_server.py (register_ptz_tools + --enable-ptz wiring)
- tools/axxon_mcp_admin_mutations.py (security_user_credential_lifecycle)
- tools/axxon_admin_mutation_smoke.py (new workflow in WORKFLOWS)
- tools/tests/test_axxon_mcp_ptz.py (new)
- tools/tests/test_axxon_mcp_server.py (PTZ registration test + StubPtz)
- tools/tests/test_axxon_mcp_admin_mutations.py (credential lifecycle tests + modified_users fake)
- tools/tests/test_axxon_admin_mutation_smoke.py (PASS count 6 -> 7)
