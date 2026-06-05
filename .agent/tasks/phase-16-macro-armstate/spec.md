# Spec: phase-16-macro-armstate

## Original task statement
Add the two genuinely-missing operator mutations on LogicService: `LaunchMacro`
(run a configured macro by id) and `ChangeArmState` (arm/disarm a camera for a
bounded, auto-reverting window). Both are approval-gated and confirmation-tokened,
consistent with the audit-injector / recognizer-write mutation idiom. Plus a
read helper to list launchable macros, so a caller can discover macro ids.

## Background (live-verified before freeze)
- `ListMacros` returns `items[] {guid, name, mode}`. Macros with `mode.common`
  + `is_add_to_menu` are manually launchable (e.g. "Fire"); autorule macros are
  detector-triggered. LaunchMacro on the "Fire" macro returned cleanly.
- `LaunchMacroRequest{macro_id}` -> empty response on success.
- `ChangeArmStateRequest{camera_ap, state, timeout}` where state is
  `events.CameraArmStateEvent.ECameraArmState` = `CS_Disarm`(0)/`CS_Arm`(1)/
  `CS_ArmPrivate`(2). `timeout` (Duration) sets the state for that long, then the
  server reverts to the previous value. Live-verified both CS_Arm and CS_Disarm
  with a 3-5s timeout were accepted and auto-revert.

## Acceptance criteria

### AC1 — module + dataclass + gating
`tools/axxon_mcp_logic_control.py` adds `AxxonMcpLogicControl` (dataclass)
mirroring `AxxonMcpAudit`: `client_factory`/`config_factory`/`client`/`enabled`,
`logic_control_connect_axxon_profile`, `ensure_client`. Mutations gated by
`AXXON_LOGIC_CONTROL_APPROVE=1` + confirmation token `CONFIRM-logic-control`. When
approval env unset -> `disabled`; wrong token -> `gap`; neither touches the stand.

### AC2 — list_launchable_macros (read helper)
`list_launchable_macros()` calls `ListMacros` and returns each macro as
`{id, name, launchable}` where `launchable` is true for manual macros
(`mode.common` present, not an autorule). Read-only, not gated. Lets a caller
find a macro_id for launch_macro.

### AC3 — launch_macro
`launch_macro(macro_id, confirmation)` calls `LaunchMacro`. Empty/missing
macro_id -> error (no wire call). On success returns
`{"status": "launched", "macro_id": ...}`.

### AC4 — change_arm_state (bounded, auto-reverting)
`change_arm_state(camera_ap, state, timeout_s, confirmation)` calls
`ChangeArmState`. `state` accepts friendly `disarm`/`arm`/`arm_private` mapped to
the `CS_*` enum. `timeout_s` is REQUIRED and bounded (1..ARM_TIMEOUT_CAP_S, cap
300) so every arm/disarm auto-reverts; a non-positive or missing timeout is an
error (no permanent state change is allowed). Returns
`{"status": "applied", "camera_ap", "state", "timeout_s", "auto_reverts": true}`.

### AC5 — server registration behind a flag
`register_logic_control_tools` registers the 3 tools +
`logic_control_connect_axxon_profile`, wired via `--enable-logic-control` (off by
default) and a `logic_control` param through `create_server` (6-edit pattern).

### AC6 — unit tests + full suite green
`tools/tests/test_axxon_mcp_logic_control.py` covers (fake client, no network):
disabled-without-approval, gap-on-bad-token, list_launchable_macros classification,
launch_macro empty-id error + success wire shape, change_arm_state state mapping,
required+bounded timeout (rejects missing/zero, caps large), and the auto-revert
flag. Full suite `python3.12 -m unittest discover -s tools/tests` stays green.

### AC7 — corpus restamp, live-justified
After a live run (raw/live-verify.txt, sanitized), restamp `LaunchMacro` and
`ChangeArmState` `pending -> tested-pass` via `tools/axxon_corpus_restamp.py`.
Update the coverage doc counts and LogicService tally.

## Constraints
- Smallest defensible diff; reuse `public_config_summary`, `message_to_dict`,
  `stub_from_proto`, `import_module`.
- ChangeArmState must always be bounded/auto-reverting; never leave a camera in a
  permanently changed arm state.
- Secrets env-only; sanitize all committed evidence.
- No biometric data involved.

## Non-goals
- ChangeMacros/macro CRUD (operator module already has a macro lifecycle).
- Counter mutations (ChangeCounters/CounterAction) and LogicService ChangeConfig.
- Permanent (unbounded) arm-state changes.

## Verification plan
- Unit: the fake-client suite; full discover run.
- Live: list_launchable_macros; launch_macro on the "Fire" macro;
  change_arm_state arm+disarm with a short timeout (auto-reverts, no residue).
