# Spec: phase-25-update-subscription

## Original task statement
Close the pending `UpdateSubscription` method on DomainNotifier (it is also
pending on NodeNotifier with the identical shape) by adding a self-contained,
read-only-ish demo tool `update_event_subscription` to the existing
`tools/axxon_mcp_admin.py` notifier layer, backed by a new
`update_subscription_bounded` client helper. UpdateSubscription only works while a
PullEvents stream is live (the subscription exists only for the open stream), so
the tool establishes a short-lived subscription on a background thread, applies
`UpdateSubscription` to change its filters, drains briefly, and disconnects. The
subscription is fully torn down at the end; nothing persists on the stand.

## Acceptance criteria
- **AC1**: `tools/axxon_api_client.py` gains `update_subscription_bounded(*,
  notifier, event_types, new_event_types, subjects=None, new_subjects=None,
  timeout_s=5.0)` that: builds initial + updated `EventFilters` via
  `build_pull_event_filters`; generates a client subscription_id; opens
  `PullEvents` on a background daemon thread to keep the subscription live; calls
  `UpdateSubscription(UpdateSubscriptionRequest{subscription_id, filters})` with
  the new filters on the main thread; then `DisconnectEventChannel`. It returns a
  dict with `status`, `notifier`, `service`, `subscription_applied` (bool),
  `before_event_types`, `after_event_types`, and `disconnect_clean`. Works for
  both `notifier="domain"` (DomainNotifier) and `notifier="node"` (NodeNotifier).
- **AC2**: The helper never raises on an idle/slow stream: a background-thread
  PullEvents error is swallowed (the subscription still registers), and a failed
  UpdateSubscription is reported as `subscription_applied=False` with a captured
  `update_error` rather than propagating. Disconnect always runs in a finally.
- **AC3**: `tools/axxon_mcp_admin.py` gains `update_event_subscription(notifier=
  "domain", event_types=None, new_event_types=None, subjects=None,
  new_subjects=None, timeout_s=5.0)` that clamps the timeout with
  NOTIFIER_TIMEOUT_CAP_S, validates `notifier in {"domain","node"}` (else a `gap`
  dict, no wire call), calls the helper, and returns the redacted result with the
  `tool` name. Added to the admin `__all__`/TOOL list.
- **AC4**: `tools/axxon_mcp_server.py` registers `update_event_subscription` next
  to `domain_event_subscribe`/`node_event_subscribe` in the existing admin
  registration (no new flag/param; admin is already wired behind
  `--enable-admin`).
- **AC5**: Unit tests (admin test module + client/admin fakes) cover: the helper
  builds before/after filters and applies UpdateSubscription via a fake stub
  (recording the two filter sets), the order (PullEvents opened, UpdateSubscription
  called, DisconnectEventChannel called), `subscription_applied=False` + captured
  error when UpdateSubscription raises, the bad-notifier gap path (no wire call),
  and that the tool clamps the timeout. Full suite stays green.
- **AC6**: `tools/axxon_corpus_restamp.py` restamps BOTH DomainNotifier and
  NodeNotifier `UpdateSubscription` to `tested-pass` (both live-verified through
  the same helper via the `notifier` param);
  `docs/api-audit/mcp-corpus/api_methods.json` reflects it. Coverage doc count
  moves to 202 pass-class / 121 pending / 38 fixture-warn and notes the
  subscription-update tool. Restamp dry-run reports 0 after `--write`.

## Constraints
- Probe-first already done: live round-tripped through direct gRPC. Opened a
  DomainNotifier subscription (ET_Bookmark filter) on a background thread, called
  UpdateSubscription to switch filters to ET_Alert (returned the empty response),
  then DisconnectEventChannel cleanly. Subscription torn down; nothing persists.
  See raw/live-verify.txt.
- Wire shape: `UpdateSubscriptionRequest{subscription_id, EventFilters filters}` ->
  empty `UpdateSubscriptionResponse`. subscription_id is client-generated and must
  match the live PullEvents stream's id. EEventType numbers: ET_Bookmark=14,
  ET_Alert=15 (resolved via build_pull_event_filters / event_type_number).
- The tool is a self-contained demo: it owns the full subscribe -> update ->
  disconnect lifecycle in one bounded call; no caller-managed stream state.
- Reuse `build_pull_event_filters` and the existing notifier idiom
  (`pull_notifier_events_bounded` structure, caps, redact_admin_secrets). Do not
  duplicate filter building.
- Secrets env-only. Committed evidence sanitized: host -> `<demo-host>`, creds ->
  `<redacted>`, subscription_id -> `<uuid>`. No proto/CA/PDF committed.
- TDD: add the failing tests first, then implement.

## Non-goals
- No persistent/caller-managed subscription handle; the lifecycle is self-contained.
- No PushDiagnosticEvents (stays pending; separate diagnostic-injection method).
- No change to the existing domain/node event subscribe tools.
- No new server flag or create_server param.

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_admin; import axxon_api_client"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_admin.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
