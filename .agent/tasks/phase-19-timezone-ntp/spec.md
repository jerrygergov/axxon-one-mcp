# Spec: phase-19-timezone-ntp

## Task statement
Close the three pending TimeZoneManager mutation RPCs (`SetTimeZone`, `SetNTP`,
`ChangeTimeZones`) by shipping a gated MCP tool module that wraps both the read
side (already proven on the wire) and the three writes, mirroring the existing
audit-injector gating idiom. Bring TimeZoneManager to 7/7 tested-pass.

## Background (live-probed before build, against the demo stand)
- `GetTimeZone` current: `Arabian Standard Time` (UTC+04:00), DST-off=False, 139
  available zones.
- `GetNTP`: empty `{}` (no NTP configured).
- `ListTimeZones`: 1 zone in the TZ database.
- All three writes were live round-tripped and proven reversible:
  - SetTimeZone: -> UTC (readback UTC) -> restored Arabian Standard Time.
  - SetNTP: empty -> pool.ntp.org -> cleared back to empty.
  - ChangeTimeZones: add throwaway zone (1->2) -> remove (2->1), restored.

## Proto facts (docs/grpc-proto-files/axxonsoft/bl/tz/TimeZonesManager.proto)
- TimeZoneManager has NO etag / optimistic concurrency. Writes are plain.
- `SetTimeZoneRequest{ string timezone_id; google.protobuf.BoolValue daylight_saving_mode_off }`.
- `SetNTPRequest{ NTP ntp }`, `NTP{ string ntp_url; bool sync_ip_devices; google.protobuf.Duration refresh_rate }`.
- `ChangeTimeZonesRequest{ repeated string removed_zones; repeated string removed_intervals;
  repeated TimeZone modified_zones; repeated TZInterval modified_intervals;
  repeated TimeZone added_zones; repeated NewIntervalEntry added_intervals }`.
- `GetTimeZoneResponse{ Timezone current_timezone{timezone_id,timezone_name};
  BoolValue daylight_saving_mode_off; repeated Timezone available_timezones }`.

## Acceptance criteria
- **AC1**: New `tools/axxon_mcp_timezone.py` module (dataclass `AxxonMcpTimezone`)
  exposes reads `get_timezone`, `get_ntp`, `list_timezones` and gated writes
  `set_timezone`, `set_ntp`, `change_timezones`. Gating mirrors the settings
  idiom: `AXXON_TIMEZONE_APPROVE=1` + per-call `confirmation=CONFIRM-timezone-set`.
  Each write returns `{"status":"disabled"}` (env unset) or `{"status":"gap"}`
  (bad token) BEFORE any wire call.
- **AC2**: `set_timezone(timezone_id, daylight_saving_mode_off=None, confirmation)`
  builds the request, sets the BoolValue only when provided, sends SetTimeZone,
  and reads back the current timezone in the response. Empty `timezone_id` ->
  `{"status":"error"}`, no wire call.
- **AC3**: `set_ntp(ntp_url, sync_ip_devices=False, refresh_rate_s=None, confirmation)`
  builds the NTP message with a Duration only when `refresh_rate_s` is provided
  and sends SetNTP. `change_timezones(...)` supports `removed_zones`,
  `added_zones` (list of {id,name}), and is a no-op error when no edit field is
  provided.
- **AC4**: The 6 tools register through `register_timezone_tools` behind a new
  `--enable-timezone` flag in `tools/axxon_mcp_server.py`, following the 6-edit
  server registration pattern.
- **AC5**: Unit tests in `tools/tests/test_axxon_mcp_timezone.py` cover gating
  (disabled/gap), the empty-input errors, the BoolValue/Duration conditional
  build, the change_timezones add/remove request shape, and a read shape. Full
  suite `python3.12 -m unittest discover -s tools/tests` stays green.
- **AC6**: Corpus restamp marks SetTimeZone, SetNTP, ChangeTimeZones ->
  tested-pass with evidence; coverage doc updated (193 pass-class, TimeZoneManager
  7/7). Live evidence (raw/live-verify.txt) shows the reversible round-trips.

## Constraints
- No proto files, CA, or PDFs committed. Secrets env-only. Evidence sanitized
  (host -> `<demo-host>`, creds/etags -> `<redacted>`; `AXXON_TLS_CN=Server` may stay).
- Every live mutation reversed; stand ends in its original state.
- Smallest defensible diff; reuse the settings module's gating/connect idiom.

## Non-goals
- TZ interval editing helpers (modified_intervals / added_intervals / NewIntervalEntry)
  beyond raw passthrough; ServerSettings (SetLogLevel/DropLogs) is a later phase.
- No friendly timezone-name search/validation; callers pass the OS timezone id.

## Verification plan
- Build: import `axxon_mcp_server`, import `axxon_mcp_timezone`.
- Unit tests: `python3.12 -m unittest discover -s tools/tests`.
- Live: round-trip each of the 3 writes through the tool, reversed.
- Corpus: `python3.12 tools/axxon_corpus_restamp.py` then coverage doc check.
