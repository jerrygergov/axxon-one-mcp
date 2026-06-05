# Evidence Bundle: phase-15-alarm-severity-fix

## Summary
- Overall status: PASS (all 4 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — severity choices fixed to valid enum — PASS
- `tools/axxon_mcp_alarms.py` `SEVERITY_CHOICES` is now
  `("SV_UNCLASSIFIED","SV_FALSE","SV_NOTICE","SV_WARNING","SV_ALARM")`; the friendly
  strings are gone. `alarm_complete_review` passes the value straight to
  `complete_alert_review`.
- Wire proof (raw/live-verify.txt): severity `false_alarm` -> HTTP 500
  ("Unknown ESeverity"); `SV_FALSE` -> HTTP 200.

## AC2 — gating + validation preserved — PASS
- `_gate` (AXXON_ALARMS_APPROVE + CONFIRM-alarm-complete), severity-not-in-choices
  -> gap, empty bookmark -> gap, all unchanged.
- Proof: `test_complete_review_rejects_unknown_severity`,
  `test_complete_review_rejects_empty_bookmark`, `test_complete_review_ok_path`.

## AC3 — unit tests updated + regression — PASS
- Severity assertions updated to `SV_ALARM`. New
  `test_severity_choices_are_valid_enum_names` asserts SEVERITY_CHOICES are a
  subset of the valid ESeverity names and that `false_alarm` is absent.
- Full suite: `Ran 719 tests ... OK` (raw/test-unit.txt); alarms module 35 OK.

## AC4 — corpus restamp, live-justified — PASS
- RaiseAlert/GetActiveAlerts/BeginAlertReview/ContinueAlertReview/CancelAlertReview
  -> tested-pass; CompleteAlertReview/EscalateAlert -> tested-warn-fixture-needed,
  all evidence-cited (raw/live-verify.txt). LaunchMacro/ChangeArmState/ChangeConfig/
  ChangeCounters/CounterAction stay pending.
- Coverage doc: 186 pass / 138 pending / 37 warn; LogicService 13/29.

## Stand hygiene
- Every alert raised during the probe was left only to the bounded 300s TTL and
  confirmed expired (0 active alerts on the affected cameras afterward). The stand
  ends with no residue. No biometric data involved.

## Sanitization
- raw/live-verify.txt: host/creds redacted; AXXON_HTTP_URL host shown as
  <demo-host>. Alert guids are object ids, not secrets.
