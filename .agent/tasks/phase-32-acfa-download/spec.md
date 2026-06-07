# Spec: phase-32-acfa-download

## Original task statement
Finish AcfaService fully: close the last pending method, AcfaService.DownloadData.
It downloads referenced data files (icon images) for an ACFA unit. The data_ids come
from a unit's visualization icons. Extend the existing control module with a read
helper to list visualizations (to discover data_ids) and a read tool to download the
data, returning size/identity metadata (not the raw blob).

Probe results (live, <demo-host>, ACFA emulator):
- ListUnitsVisualizations(uid) returns per-unit visualizations; icon visualizations
  carry an `image` data_id (e.g. ax_percos20v2_r_lock.png).
- DownloadData(uid, data_id[]) streams DownloadDataResponse{data, data_id}. For
  hosts/Server/ACFA.2/EMULATOR_LOCK.5 with two lock/unlock pngs it returned 2 chunks,
  each 344 bytes; data is base64-encoded PNG (head 'iVBORw0K'). Read-only.

## Acceptance criteria

- AC1: `list_unit_visualizations(uids)` (read) streams AcfaService.ListUnitsVisualizations
  and returns {status: ok, units: [{uid, visualizations: [{id, name, kind,
  image_data_ids: [...]}]}]}, surfacing icon image data_ids so a caller can feed them
  to download. Empty uids -> {status: error} with no wire call.
- AC2: `download_unit_data(uid, data_ids)` (read) streams AcfaService.DownloadData and
  returns metadata only: {status: ok, tool, uid, count, items: [{data_id,
  byte_count}], total_bytes}. The raw data blob is NEVER returned in the response.
  Missing uid or empty data_ids -> {status: error} with no wire call.
- AC3: Both tools are read-only (no gate, no mutation). The download response measures
  the data length per chunk; payloads are measured, not echoed. Config secrets never
  appear in the response.
- AC4: Server registers both as @server.tool in the existing register_control_tools
  (no new flag/param needed — the control module is already wired). Added to
  CONTROL_TOOL_NAMES. Unit tests cover both tools (ok shape, error-no-wire,
  metadata-only, no-leak). Full suite green.
- AC5: Corpus restamp ("AcfaService","DownloadData") -> tested-pass; restamp dry-run 0
  after --write. Coverage doc updated (count + item); AcfaService now 7/7 complete.
  Live verify recorded in raw/live-verify.txt.

## Constraints
- Read-only; reuse the existing control module (ensure_client/_stub_and_pb2) and the
  metadata-only return convention (never surface raw media bytes).
- These are extensions of an already-wired module: just add the methods + @server.tool
  inside register_control_tools; no new CLI flag/param.

## Non-goals
- Returning the raw image bytes to the MCP caller (metadata only).
- Re-testing the already-passing ACFA reads.

## Verification plan
- Build: pyimport smoke (server + control module)
- Unit tests: list_unit_visualizations + download_unit_data (ok/error/metadata/no-leak)
- Integration tests: full suite discover
- Lint: n/a
- Manual checks: live list_unit_visualizations -> image data_ids; download_unit_data
  on a lock unit -> count=2, byte sizes, no data blob; restamp dry 0 after write
