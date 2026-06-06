# Evidence Bundle: phase-25-update-subscription

## Summary
- Overall status: PASS (all 6 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — update_subscription_bounded client helper — PASS
- `tools/axxon_api_client.py` gains `update_subscription_bounded(*, notifier,
  event_types, new_event_types, subjects, new_subjects, timeout_s)`: builds
  before/after EventFilters via `build_pull_event_filters`, opens PullEvents on a
  background daemon thread to keep the subscription live, calls UpdateSubscription
  with the new filters, then DisconnectEventChannel. Works for domain + node.
- Proof: helper + `FakeNotifierScheduleClient.update_subscription_bounded`; live
  domain + node both `subscription_applied=True`.

## AC2 — graceful, disconnect-in-finally — PASS
- Background PullEvents errors are swallowed (subscription still registers); a
  failed UpdateSubscription -> `subscription_applied=False` + captured
  `update_error` (no propagation); DisconnectEventChannel runs in a finally with
  `disconnect_clean`.
- Proof: helper try/except + finally; live `disconnect_clean=True` both notifiers.

## AC3 — update_event_subscription admin tool — PASS
- Clamps timeout (NOTIFIER_TIMEOUT_CAP_S), validates notifier in {domain,node}
  (else gap, no wire call), calls the helper, returns the redacted result + tool
  name. Added to the admin TOOL list.
- Proof: `test_update_event_subscription_applies_new_filters_and_clamps_and_redacts`,
  `test_update_event_subscription_node_notifier`,
  `test_update_event_subscription_bad_notifier_is_gap_without_wire_call`; live gap
  path.

## AC4 — server registration — PASS
- `update_event_subscription` registered next to `node_event_subscribe` in the
  existing admin registration (no new flag/param).
- Proof: raw/test-unit.txt (server import OK).

## AC5 — unit + full suite green — PASS
- 3 new tests (24 in the admin suite). Full suite `Ran 796 tests ... OK`
  (raw/test-unit.txt).

## AC6 — corpus restamp + coverage doc — PASS
- DomainNotifier + NodeNotifier UpdateSubscription -> tested-pass (same helper via
  the notifier param). Coverage 202 pass-class / 121 pending / 38 fixture-warn;
  item 10l. Restamp dry-run reports 0 after --write.

## Stand hygiene
- Each opened subscription was disconnected (DisconnectEventChannel) in a finally;
  disconnect_clean=True both notifiers. Nothing persists on the stand. No
  proto/CA/PDF committed; secrets env-only; no biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`,
  subscription_id -> `<uuid>`.
