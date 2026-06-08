# Evidence: phase-46-videowall-logic-writes

Overall: PASS (all acceptance criteria PASS)

## AC1 — Videowall module + server wiring — PASS
`tools/axxon_mcp_videowall.py` adds `AxxonMcpVideowall` (approval env `AXXON_VIDEOWALL_APPROVE`,
confirmation token `CONFIRM-videowall`, same dataclass idiom as logic_control) with `list_walls`
(ungated read), `register_wall`, `change_wall`, `set_control_data`, `unregister_wall`.
`register_wall` returns `cookie_present` + `wall_id` + `seq_number` and never the raw cookie (the
cookie is tracked internally keyed by wall_id; change/unregister reference wall_id). `change_wall`
and `set_control_data` return `{"status":"error"}` with no wire call on an unknown/empty wall_id.
VIDEOWALL_TOOL_NAMES lists all 6 tools. Server wired via the 6-edit pattern: create_server param
`videowall`, conditional `register_videowall_tools`, the register fn, `--enable-videowall`,
flag-gated instantiation, and `videowall=videowall` kwarg. build smoke (raw/build.txt) confirms the
new videowall tools register.

## AC2 — Logic control additions — PASS
`tools/axxon_mcp_logic_control.py` gains `change_config`, `change_counters`, `counter_action`,
behind the existing logic-control gate. `change_config` calls GetConfig first and only overrides
the fields the caller passes (round-trippable; returns `previous` + `applied`); rejects empty or
unknown fields with no wire. `change_counters` adds a counter by guid+name or removes by guid
(exactly one), validating before the wire. `counter_action` runs START/STOP/CLEANUP on a counter
guid via Macro_pb2.CounterAction. All three added to LOGIC_CONTROL_TOOL_NAMES and registered as
server tools.

## AC3 — Live evidence (reversible, no residue) — PASS
raw/live-verify.txt (sanitized, host shown as <demo-host>) exercises the SHIPPED MCP modules
against the real stand:
- Videowall: list_walls (1) -> register_wall (cookie_present, no raw cookie) -> list_walls shows it
  (2) -> change_wall new_seq 1 -> set_control_data new_seq 2 -> unregister_wall -> list_walls back
  to baseline (1). Reversible, no residue.
- ChangeConfig: original user_alert_ttl 300 -> change_config bump to 301 -> GetConfig confirms 301
  -> change_config restore -> GetConfig confirms 300.
- ChangeCounters + CounterAction: add throwaway counter -> ListCounters shows it -> counter_action
  START -> GetCounterState is_active=true -> remove -> ListCounters empty.
- Re-probe of the 5 stand-walled methods proves each was live-exercised and blocked:
  BatchCompleteAlertsReview (read-path sees the alert via node=Server, complete returns
  unreachable=['Server']); GlobalTracker ClearProfiles UNIMPLEMENTED, ChangeGlobalTrackerProfiles /
  BindGlobalTrackProfile INTERNAL, ChangeProfiles commits but terminates INTERNAL. Probe profile
  cleaned up. Secret scan of the output: clean (no host IP / cred pattern).

## AC4 — Corpus restamp honest + idempotent — PASS
tools/axxon_corpus_restamp.py adds 12 phase-46 entries: 7 -> tested-pass (VideowallService
Register/Change/SetControlData/Unregister; LogicService ChangeConfig/ChangeCounters/CounterAction),
5 -> tested-warn-fixture-needed (LogicService.BatchCompleteAlertsReview + 4 GlobalTracker methods),
all moved out of pending. `--write` applied; dry-run after = `0 method(s) restamped`. Totals now
283 tested-pass / 24 pending / 54 fixture-warn (361). VideowallService 6/7; LogicService 24/29.
Coverage doc headline + item 10ag + matrix rows updated.

## AC5 — Unit tests + full suite + lint — PASS
tools/tests/test_axxon_mcp_videowall.py (new) and tools/tests/test_axxon_mcp_logic_control.py
(extended) cover all 7 tools: happy-path wire shapes, missing-arg/unknown-arg paths assert
`client.calls == []`, disabled-gate + wrong-confirmation assert no wire, register asserts
`cookie` absent from the result, and no-secret-leak asserts the FakeConfig password sentinel never
appears. raw/test-unit.txt: 33 passed. raw/test-integration.txt: 969 passed (948 prior + 21 new).
raw/lint.txt: All checks passed!.
