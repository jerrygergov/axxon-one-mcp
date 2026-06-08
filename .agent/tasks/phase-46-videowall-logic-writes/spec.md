# Spec: phase-46-videowall-logic-writes

## Original task

Close the reversible-write cluster across three services that the coverage ledger still lists as
`pending`. Live probing against the stand sorted the 12 pending methods into code-closeable vs
stand-walled:

Code-closeable (RPC executes end-to-end, returns a valid typed response, fully reversible):
- VideowallService: RegisterWall, UnregisterWall, ChangeWall, SetControlData (4)
- LogicService: ChangeConfig, ChangeCounters, CounterAction (3)

Stand-walled (re-probed live, stays fixture-warn, NOT in scope to close):
- LogicService.BatchCompleteAlertsReview: read path resolves node `Server`
  (BatchGetActiveAlerts returns the in-review alert) but the complete write path returns
  `unreachable=['Server']` for both the node-name and domain-uid forms, and the only raisable
  alerts are AIT_USER which return failure on complete (same wall as the already fixture-warned
  CompleteAlertReview/EscalateAlert; needs a rule-generated alert this stand cannot trigger).
- GlobalTrackerService.ChangeGlobalTrackerProfiles / ClearProfiles / BindGlobalTrackProfile:
  no global tracker object is configured on this stand. ClearProfiles/GetGlobalTrackerProfiles
  return UNIMPLEMENTED; ChangeGlobalTrackerProfiles returns INTERNAL "Failed to change global
  tracker profiles".
- GlobalTrackerService.ChangeProfiles: the profile store works (a throwaway profile was added
  then removed, confirmed via GetProfile), but the streaming response always terminates INTERNAL
  ("Internal errors occurred") because the global-tracker notify side is absent. Not a clean pass.

This phase ships MCP tools for the 7 code-closeable methods and restamps only those tested-pass.
The 5 stand-walled methods are re-probed, documented, and left fixture-warn (moving from pending
to tested-warn-fixture-needed, since "pending" means never-probed and they are now
live-probed-and-blocked).

## Repo guidance sources

- tools/axxon_mcp_logic_control.py: the gated-mutation module idiom (approval env + per-call
  confirmation token, `<name>_connect_axxon_profile`, `connect_axxon_profile`, `ensure_client`,
  `_stub_and_pb2`, reuse `public_config_summary`). ChangeConfig/ChangeCounters/CounterAction are
  LogicService mutations and belong in this existing module, not a new one.
- tools/axxon_mcp_server.py: 6-edit wiring for a NEW module (param, conditional register call,
  register_*_tools def, --enable flag, gated instantiation, create_server kwarg). Videowall is a
  new module; Logic additions reuse the already-wired logic_control registration.
- docs/grpc-proto-files/axxonsoft/bl/videowall/Videowall.proto and
  docs/grpc-proto-files/axxonsoft/bl/logic/LogicService.proto + Macro.proto (CounterAction).

## Acceptance criteria

- AC1: `tools/axxon_mcp_videowall.py` adds a NEW gated module `AxxonMcpVideowall` (approval env
  `AXXON_VIDEOWALL_APPROVE`, confirmation token, same dataclass idiom as logic_control) exposing
  `register_wall`, `unregister_wall`, `change_wall`, `set_control_data` plus a read helper
  `list_walls`. `register_wall` returns `cookie_present` boolean + `wall_id` + `seq_number` and
  NEVER returns the raw cookie. `change_wall`/`set_control_data` validate their required args
  (cookie / wall_id) before any wire call. The module is wired into the server via the full 6-edit
  pattern (`--enable-videowall`, `register_videowall_tools`) and a VIDEOWALL_TOOL_NAMES tuple.

- AC2: `tools/axxon_mcp_logic_control.py` gains `change_config`, `change_counters`,
  `counter_action` (all behind the existing logic-control gate + confirmation). `change_config`
  reads current config and only overrides the fields the caller passes (round-trippable).
  `change_counters` adds a counter from a guid+name (or removes by guid). `counter_action`
  performs START/STOP/CLEANUP on a counter guid. All three validate required args before the wire
  call and are added to LOGIC_CONTROL_TOOL_NAMES. New server tools `change_config`,
  `change_counters`, `counter_action` registered in register_logic_control_tools.

- AC3: Live evidence (sanitized, host shown as <demo-host>) in raw/live-verify.txt shows, against
  the real stand, a full reversible round-trip for each of the 7 closed methods: RegisterWall ->
  ListWalls shows it -> ChangeWall (new_seq) -> SetControlData (new_seq) -> UnregisterWall ->
  ListWalls no longer shows it; GetConfig -> ChangeConfig bump -> GetConfig confirms -> ChangeConfig
  restore -> GetConfig confirms original; ChangeCounters add -> ListCounters shows it ->
  CounterAction START -> GetCounterState is_active=true -> ChangeCounters remove -> ListCounters
  empty. No residue is left on the stand. The raw file also records the re-probe of the 5
  stand-walled methods proving they were live-exercised and blocked.

- AC4: Corpus restamp is honest + idempotent. The 7 closed methods -> tested-pass with phase-46
  evidence citations. The 5 stand-walled methods -> tested-warn-fixture-needed (moved out of
  pending) with the live re-probe citation. `python3.12 tools/axxon_corpus_restamp.py --write` then
  a dry-run reports `0 method(s) restamped`. Totals updated: 283 tested-pass / 24 pending /
  54 fixture-warn (361). VideowallService becomes 6/7; LogicService gains 3 tested-pass. Coverage
  doc docs/api-audit/capability-vs-coverage-2026-06-05.md headline + a phase-46 section updated.

- AC5: Unit tests (FakeClient, no network) for all 7 tools plus the gate paths: a happy-path call
  per tool asserting the parsed response shape; a missing-required-arg call per mutating tool
  asserting `client.calls == []` (no wire); a disabled-gate / wrong-confirmation call asserting
  no wire; and a no-secret-leak assertion (FakeConfig password sentinel never appears in any
  output). Full suite green; production modules lint clean (uvx ruff check).

## Constraints

- Credentials only from env; `.env` never staged. Sanitize host/creds in artifacts; secret-scan
  the staged diff for the demo host IP and plaintext credential patterns and redact to
  <demo-host> / redacted patterns.
- Metadata only: `register_wall` returns `cookie_present` boolean, never the raw cookie. No raw
  control-data bytes echoed back beyond a length.
- Every mutation must be reversible and must leave no residue: registered walls are unregistered;
  throwaway counters are removed; config changes are restored to the original values read first.
- Gate every mutating tool behind its approval env + confirmation token, matching the existing
  logic_control idiom. Read helpers (list_walls) are ungated.
- Only restamp the 7 closed methods to tested-pass and the 5 re-probed methods to
  tested-warn-fixture-needed. Do not touch any other ledger row.

## Non-goals

- No attempt to close BatchCompleteAlertsReview (write-path node-unreachable + AIT_USER-only
  alerts) or the 4 GlobalTracker methods (no global tracker object on this stand). They are
  re-probed and documented, not code-closed.
- No new GlobalTracker or Videowall read tooling beyond list_walls.
- No raw cookie / raw control-data relay.

## Verification plan
- Build: import tools/axxon_mcp_videowall.py + server build smoke registers the 7 new tools.
- Unit tests: python3.12 -m pytest tools/tests/test_axxon_mcp_videowall.py tools/tests/test_axxon_mcp_logic_control.py -q
- Integration tests: python3.12 -m pytest tools/tests/ -q (full suite green)
- Lint: uvx ruff check tools/axxon_mcp_videowall.py tools/axxon_mcp_logic_control.py tools/axxon_mcp_server.py
- Manual checks: live round-trip script against the stand -> raw/live-verify.txt; restamp dry-run = 0.
