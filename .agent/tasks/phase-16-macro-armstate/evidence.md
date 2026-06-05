# Evidence Bundle: phase-16-macro-armstate

## Summary
- Overall status: PASS (all 7 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — module + dataclass + gating — PASS
- `tools/axxon_mcp_logic_control.py` adds `AxxonMcpLogicControl` mirroring
  `AxxonMcpAudit`. Gated by `AXXON_LOGIC_CONTROL_APPROVE=1` +
  `LOGIC_CONTROL_CONFIRMATION="CONFIRM-logic-control"`; `_gate` returns `disabled`
  (env unset) / `gap` (bad token) before any wire call.
- Proof: `GatingTests`; live `[gate]` line in raw/live-verify.txt.

## AC2 — list_launchable_macros (read helper) — PASS
- `ListMacros` -> `{id, name, launchable}`; launchable = `mode.common` present.
- Proof: `ListMacrosTests.test_classifies_launchable`; live total=24, launchable=9.

## AC3 — launch_macro — PASS
- `LaunchMacro` by id; empty id -> error, no wire call.
- Proof: `LaunchMacroTests`; live launched manual macro "Fire" -> launched.

## AC4 — change_arm_state (bounded, auto-reverting) — PASS
- `ChangeArmState` with friendly state map (disarm/arm/arm_private -> CS_*); a
  required, positive, capped (300s) timeout so every change auto-reverts. Missing/
  zero timeout and unknown state -> error, no wire call.
- Proof: `ChangeArmStateTests` (mapping, required+capped timeout, auto_reverts);
  live arm+disarm cam1 with 5s timeout (auto_reverts=true), bad state/missing
  timeout -> error. Hygiene: cam1 reachable after timeouts elapsed, no residue.

## AC5 — server registration behind a flag — PASS
- `register_logic_control_tools` registers 3 tools +
  `logic_control_connect_axxon_profile`; wired via `--enable-logic-control` (off by
  default) + `logic_control` param (6-edit pattern). Server import OK.
- Proof: raw/test-unit.txt (server import OK).

## AC6 — unit tests + full suite green — PASS
- 12 tests in `tools/tests/test_axxon_mcp_logic_control.py`.
- Full suite: `Ran 731 tests ... OK` (raw/test-unit.txt).

## AC7 — corpus restamp, live-justified — PASS
- `LaunchMacro`, `ChangeArmState` restamped `pending -> tested-pass` with evidence
  citations. Coverage 188 pass / 136 pending / 37 warn; LogicService 15/29.

## Sanitization
- raw/live-verify.txt: host/creds redacted; macro/camera guids are object ids, not
  secrets. No biometric data.
