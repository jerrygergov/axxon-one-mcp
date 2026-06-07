# Spec: phase-35-logic-batch-alerts

## Original task statement
Close the LogicService node-scoped batch alert methods (7 of the 10 pending). These
operate on whatever active alerts match a node+filter selection, so they execute
cleanly even with 0 active alerts (valid no-op) - unlike the single-alert
CompleteAlertReview/EscalateAlert which need a specific reviewable alert. Ship a new
module: 2 read tools + 5 gated batch-review tools.

Probe results (live, <demo-host>, node "Server", 0 active alerts):
- BatchGetActiveAlerts(nodes), BatchFilterActiveAlerts(nodes[,filter]) -> stream, PASS.
- BatchBeginAlertsReview / BatchContinueAlertsRewiew / BatchCancelAlertsReview /
  BatchCompleteAlertsReview / BatchEscalateAlerts all take {nodes, filter, ...} and
  returned PASS (success/failure/unreachable_nodes lists, empty no-op on 0 alerts).
- Counter ops (GetCounterState/ChangeCounters/CounterAction/GetCounterGroupState) are
  FIXTURE-WALLED: ListCounters returns empty (no counter configured); GetCounterState
  on an empty/guess name raises a CORBA exception. NOT in scope.

## Acceptance criteria

- AC1: New module `tools/axxon_mcp_logic_alerts.py` with read tools
  `batch_get_active_alerts(nodes)` and `batch_filter_active_alerts(nodes, groups,
  parents)` that drain the streams and return {status: ok, alert_count, alerts (id +
  basic fields), unreachable_nodes}. Empty nodes -> {status: error} no wire call.
- AC2: Gated batch-review tools `batch_begin_alerts_review`,
  `batch_continue_alerts_review`, `batch_cancel_alerts_review`,
  `batch_complete_alerts_review`, `batch_escalate_alerts` under env
  `AXXON_LOGIC_ALERTS_APPROVE=1` + token `CONFIRM-batch-alerts`. Each takes nodes +
  optional filter (groups/parents); complete also takes severity, escalate takes
  priority/comment. Return {status: applied, success, failure, unreachable_nodes}.
- AC3: Gate matrix: disabled (env off) / gap (bad token) / error (empty nodes) all
  before any wire call. Config secrets never leak.
- AC4: Server wired with the 6-edit pattern (--enable-logic-alerts flag, param,
  register, instantiation, create_server arg). Unit tests cover reads + gated writes +
  gate matrix + no-leak. Full suite green.
- AC5: Corpus restamp 7 methods -> tested-pass (BatchGetActiveAlerts,
  BatchFilterActiveAlerts, BatchBeginAlertsReview, BatchContinueAlertsRewiew,
  BatchCancelAlertsReview, BatchCompleteAlertsReview, BatchEscalateAlerts). The counter
  ops + single CompleteAlertReview/EscalateAlert stay pending/fixture-warn. Restamp
  dry-run 0 after --write; coverage doc updated. Live verify recorded.

## Constraints
- Batch reviews are approval-gated (env + token), default-off.
- Live verification is a node-scoped no-op (0 active alerts) - nothing is actually
  reviewed/escalated; the RPC executes and returns empty success/failure lists.
- Reuse the groups/gdpr gating idiom and the 6-edit server pattern.

## Non-goals
- Counter ops (ChangeCounters/CounterAction/GetCounterState/GetCounterGroupState) -
  no counter configured on the stand.
- Single-alert CompleteAlertReview/EscalateAlert (need a specific reviewable alert).

## Verification plan
- Build: pyimport smoke
- Unit tests: reads + gated writes + gate matrix + no-leak
- Integration tests: full suite discover
- Lint: n/a
- Manual checks: live batch reads + each gated batch review (node Server, no-op);
  gate disabled/gap; restamp dry 0 after write
