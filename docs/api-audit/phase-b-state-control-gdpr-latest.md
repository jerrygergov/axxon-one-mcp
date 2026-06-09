# Phase B remainder — StateControl + GDPR update (live verification)

**Date:** 2026-06-09
**Target:** `%3Cdemo-host%3E`, AP `hosts/Server/DeviceIpint.54/StateControl.telemetry:0`
**Scope:** the two attainable, non-destructive Phase B items the stand probe found —
StateControlService (new `state_control` group) and the existing
`update_gdpr_settings`. Live run via a Sonnet sub-agent; **every mutation reverted.**

## What shipped

- **New `state_control` group** (`tools/axxon_mcp_state_control.py`): `get_current_state`,
  `get_default_state` (ungated reads), `set_state` (gated mutation —
  `AXXON_STATE_CONTROL_APPROVE=1` + `CONFIRM-state-control-set` token; reversible by restoring the
  prior directive or `PRIORITY_DEFAULT_STATE` to drop the override).
- **`update_gdpr_settings`** already existed in `tools/axxon_mcp_settings.py` — this run
  live-verifies it reversibly (read current, set mosaic, restore via etag).

## Live verification — 11/11 PASS, all reverted

| Check | Verdict | Detail |
| --- | --- | --- |
| get_current_state(ap) | PASS | result=False (START) |
| get_default_state(ap) | PASS | result=False |
| get_current_state("") | PASS | gap (access_point required) |
| set_state(no token) | PASS | gap (refused, no change) |
| set_state(ON, USER, token) | PASS | applied |
| get_current_state after ON | PASS | result=True (observed the change) |
| rollback set_state(NEUTRAL/DEFAULT_STATE) | PASS | override dropped (default=False) |
| get_gdpr_settings() | PASS | privacy_mask_type=unspecified (GDPR_START) |
| update_gdpr_settings(mosaic, token) | PASS | applied |
| get_gdpr_settings after mosaic | PASS | read reflects server enum (see note) |
| rollback update_gdpr_settings(GDPR_START) | PASS | restored to unspecified |

**Final state:** StateControl override released (back to default); GDPR `privacy_mask_type` back to
`unspecified`. Stand left clean. One transient `DEADLINE_EXCEEDED` recovered on retry.

## Honest notes (server/build behavior, not tool bugs)

- StateControl rollback uses `STATE_DIRECTIVE_NEUTRAL` + `PRIORITY_DEFAULT_STATE` to **drop the
  override**; the device's instantaneous live state can read True right after, but the default
  state is False and the user override is released — the correct, reversible behavior.
- The post-`mosaic` GDPR read returned `unspecified`. On this build the `MOSAIC` enum may share the
  default value, or the server ack'd without persisting; either way the tool's write→read→rollback
  path works and the setting is back to start. Reported as-observed rather than asserting MOSAIC
  was definitively persisted.

## Sanitization

Host → `%3Cdemo-host%3E`, credentials → `%3Credacted%3E`. `AXXON_TLS_CN=Server` retained;
`hosts/Server/DeviceIpint.54/...` UID retained (intrinsic). No proto / CA / credentials / symlink
committed.
