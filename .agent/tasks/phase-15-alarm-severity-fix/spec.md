# Spec: phase-15-alarm-severity-fix

## Original task statement
Fix the severity-enum bug in the shipped alarm-completion tool and reconcile the
LogicService alert-lifecycle RPCs that the alarm tools actually exercise. While
probing LogicService (a pending-mutation target), the shipped
`alarm_complete_review` tool was found to send invalid severity strings that the
server rejects with HTTP 500 / "Unknown bl::events::AlertState::ESeverity", so
`CompleteAlertReview` never worked. The other lifecycle RPCs are reachable and
were live-exercised. This phase fixes the bug and restamps the reachable RPCs.

## Background (live-verified before freeze)
- `AlertState.ESeverity` proto enum is `SV_UNCLASSIFIED/SV_FALSE/SV_NOTICE/
  SV_WARNING/SV_ALARM`. The tool's `SEVERITY_CHOICES` was
  `("confirmed_alarm","suspicious_situation","false_alarm")` — none are valid enum
  names, so every complete_review 500s.
- Wire proof: on a fresh raised alert, severity `"false_alarm"` -> HTTP 500;
  severity `"SV_FALSE"` -> HTTP 200 (request accepted).
- `RaiseAlert`, `GetActiveAlerts`, `BeginAlertReview`, `ContinueAlertReview`,
  `CancelAlertReview` are reachable and live-exercised (all returned over the
  bridge with result fields).
- User-raised (`AIT_USER`) alerts can only be cleared by a 300s TTL on this stand;
  Begin/Continue/Complete/Cancel return result:False for them. So full
  `CompleteAlertReview`/`EscalateAlert` success needs a rule-generated alert that
  cannot be triggered here; those stay fixture-warn.
- `escalate_alert` priority already uses correct enum names
  (`AP_MINIMUM/AP_LOW/AP_MEDIUM/AP_HIGH`); no change needed there.

## Acceptance criteria

### AC1 — severity choices fixed to valid enum
`SEVERITY_CHOICES` in `tools/axxon_mcp_alarms.py` becomes the valid proto enum
names (`SV_UNCLASSIFIED`, `SV_FALSE`, `SV_NOTICE`, `SV_WARNING`, `SV_ALARM`), and
`alarm_complete_review` passes that value through unchanged. The tool no longer
offers `confirmed_alarm`/`suspicious_situation`/`false_alarm`.

### AC2 — gating + validation preserved
`alarm_complete_review` still: requires `AXXON_ALARMS_APPROVE=1` + the
`CONFIRM-alarm-complete` token, rejects a severity outside the new choices with a
`gap` (no wire call), and requires a non-empty `bookmark_message`. Behavior and
return shape otherwise unchanged.

### AC3 — unit tests updated + regression
`tools/tests/test_axxon_mcp_alarms.py` is updated so any severity assertions use
the new enum names, plus a regression test asserting `SEVERITY_CHOICES` are all
valid `AlertState.ESeverity` names (guards against re-introducing friendly
strings). Full suite `python3.12 -m unittest discover -s tools/tests` stays green.

### AC4 — corpus restamp, live-justified
Restamp via `tools/axxon_corpus_restamp.py` the LogicService RPCs that were
live-exercised: `RaiseAlert`, `GetActiveAlerts`, `BeginAlertReview`,
`ContinueAlertReview`, `CancelAlertReview` -> `tested-pass` (evidence-cited).
`CompleteAlertReview` and `EscalateAlert` -> `tested-warn-fixture-needed` (request
now valid but needs a rule-raised alert for full success). `LaunchMacro`,
`ChangeArmState`, `ChangeConfig`, `ChangeCounters`, `CounterAction` stay pending
(not exercised in this phase). Coverage doc counts updated.

## Constraints
- Smallest defensible diff. Fix the enum mapping; do not refactor the lifecycle.
- Any alert raised during verification must be cleaned up or left only to a
  bounded TTL; the stand must end with no residue beyond TTL-expiring alerts.
- Sanitize all committed evidence (host/user/creds).
- No biometric data involved.

## Non-goals
- Making user-raised alert completion succeed (stand limitation, not code).
- Building LaunchMacro/ChangeArmState (separate phase).
- Touching escalate's priority enum (already correct).

## Verification plan
- Unit: updated alarms suite + the new enum-validity regression; full discover run.
- Live (recorded, sanitized): old vs new severity wire test (500 vs 200) already
  captured; reachable lifecycle RPCs exercised; stand confirmed clean (0 active
  alerts after TTL).
