# Phase 5C — Alarm Lifecycle + Notifications Design

**Date:** 2026-05-16
**Status:** Draft for review
**Stand verified against:** `100.76.150.18:20109` (HTTP `80`, root/root, CA at `docs/grpc-proto-files/api.ngp.root-ca.crt`)
**Prior phases:** 1 (docs), 2 (live read-only), 3 (operator workflows), 4 (integration generator), 5A (live + archive viewing)

---

## 1. Goal

Expose Axxon One's alarm-review surface as MCP tools so a customer's LLM or integration code can:

1. **See active alarms** on a stand (per-camera, per-node, or filtered).
2. **Subscribe** to a bounded stream of alarm events with domain-aware filters.
3. **Raise a synthetic alarm** for testing or operator escalation paths.
4. **Review an alarm** through its full lifecycle: begin → continue → cancel/complete/escalate.
5. **Read alarm history** from `EventHistoryService` filtered to the alarm event types.

This phase is the second-largest pending service (LogicService — 19 pending methods of 29). The scope here closes the alarm slice of that service. Counter mutations, rule `ChangeConfig`, and the Batch* variants are explicitly deferred to later phases.

---

## 2. Source-of-truth references

| Source | Location | Use |
| --- | --- | --- |
| `LogicService.proto` | `docs/grpc-proto-files/axxonsoft/bl/logic/LogicService.proto` | Exact request/response message shapes |
| `Events.proto` | `docs/grpc-proto-files/axxonsoft/bl/events/Events.proto` | `EEventType` enum (`ET_Alert=15`, `ET_AlertState=16`), `EAlertPriority`, `AlertState.ESeverity` |
| Existing alarm reads | `tools/axxon_aux_topics_smoke.py` lines 70–88 | Verified `GetActiveAlerts` / `BatchGetActiveAlerts` dispatch shape |
| Phase 5A view module | `tools/axxon_mcp_view.py` | Dataclass-with-factories pattern to mirror |
| Phase 2 live module | `tools/axxon_mcp_live.py` | `pull_events_bounded` + filter pattern to reuse for `alarm_subscribe` |
| Phase 3 operator audit | `tools/axxon_mcp_operator.py` | Audit-log entry shape to follow |
| Demo stand | `100.76.150.18`, `root`/`root`, CA `docs/grpc-proto-files/api.ngp.root-ca.crt`, TLS CN `Server` | All live verification |

### Verified live behaviors (probed against demo stand 2026-05-16)

The following were end-to-end probed before this spec was written and inform the design:

1. **`RaiseAlert({camera_ap})` returns `{result: true, alert_id: "<guid>"}`.** Captured alert id `332e1fe4-5caa-4898-9c54-c34ffe0119db` against camera `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`.
2. **Active alarm shape** (`GetActiveAlerts.alerts[]`): `guid`, `timestamp` (Axxon `YYYYMMDDTHHMMSS.uuuuuu` form), `node_info.{name,friendly_name}`, `camera.{access_point,friendly_name,group}`, `archive.{access_point,friendly_name,group}`, `required_comment.{confirmed_alarm,suspicious_situation,false_alarm}`.
3. **`BeginAlertReview({camera_ap, alert_id})` → `{result: true}`.**
4. **`CancelAlertReview({camera_ap, alert_id})` → `{result: true}`.** Used to clean up the test alert with no persisted bookmark/severity side-effect.
5. **`BatchGetActiveAlerts({nodes: [host]})` paginates with `event_stream_items[].alerts[]` plus `unreachable_nodes[]`.** First page on this stand reports `unreachable_nodes: ["hosts/Server"]`; second page is empty. The unreachable field is per-page noise on a single-node stand; we ignore it unless it persists across all pages.
6. **`BatchFilterActiveAlerts({nodes, filter})` accepts an empty `filter` object** (verified shape; returns the same paginated stream).
7. **`LogicService.GetConfig({})` works** and returns `{user_alert_ttl, rule_alert_ttl, conditional_ttl, required_comment, max_event_age, event_cleanup_period}` — useful for `system_health` later, not in 5C.

### Verified proto shapes (read directly from `LogicService.proto`)

| RPC | Request | Response |
| --- | --- | --- |
| `RaiseAlert` | `{camera_ap}` | `{result, alert_id}` |
| `BeginAlertReview` | `{camera_ap, alert_id}` | `{result}` |
| `ContinueAlertReview` | `{camera_ap, alert_id}` (same shape) | `{result}` |
| `CancelAlertReview` | `{camera_ap, alert_id}` | `{result}` |
| `CompleteAlertReview` | `{severity: ESeverity, bookmark: Bookmark, camera_ap, alert_id}` | `{result}` |
| `EscalateAlert` | `{camera_ap, alert_id, priority: EAlertPriority, user_roles[], comment}` | `{result}` |
| `BatchFilterActiveAlerts` | `{nodes[], filter: AlertFilter}` | `stream` of `{alerts[], unreachable_nodes[]}` |
| `GetActiveAlerts` | `{camera_ap}` | `{alerts[]}` |
| `BatchGetActiveAlerts` | `{nodes[]}` | `stream` of `{alerts[], unreachable_nodes[]}` |

---

## 3. Tools shipped

### 3.1 Reads — behind `--enable-alarms` (no special env var required)

| Tool | Signature | Backed by | Returns |
| --- | --- | --- | --- |
| `alarms_connect_axxon_profile(profile="env")` | — | `AxxonApiClient` auth + `authenticate_http_grpc` | profile summary, `mode: "read-only"` |
| `list_active_alerts(camera_access_point=None, limit=50)` | clamps `limit` to `LIST_LIMIT_CAP=200` | per-camera: `LogicService.GetActiveAlerts({camera_ap})`; node-wide: `BatchGetActiveAlerts({nodes:[host]})` with stream flatten | `{status, count, items: [normalize_alarm(a) for a in alerts]}` |
| `get_active_alert(camera_access_point, alert_id)` | — | `GetActiveAlerts({camera_ap})` then filter by `guid == alert_id` | one alarm dict or `{status:"gap", message: ...}` |
| `filter_active_alerts(severity_min=None, camera=None, state="all", limit=50)` | clamps `limit` | `BatchFilterActiveAlerts({nodes:[host], filter:{}})` plus in-process filter on the flattened stream | normalized list |
| `list_alarm_history(hours=1, limit=100, camera=None, severity_min=None)` | clamps `hours` to `HISTORY_HOURS_CAP=24`, `limit` to `LIST_LIMIT_CAP=200` | `EventHistoryService.ReadEvents` filtered to `ET_Alert`/`ET_AlertState` (reuses `client.search_events` from Phase 2 with type filter) | normalized list |
| `list_alarm_event_types()` | — | `client.list_event_types()` (Phase 2) filtered to the constants list | `{items: [{name:"ET_Alert", value:15}, {name:"ET_AlertState", value:16}]}` |
| `alarm_subscribe(severity_min=None, camera_access_point=None, state="all", duration_s=10, limit=25)` | `duration_s` clamped to `SUBSCRIBE_DURATION_CAP_S=30`, `limit` to `SUBSCRIBE_LIMIT_CAP=100` | `client.pull_events_bounded(subjects=[host], event_types=ALARM_EVENT_TYPES, timeout=duration_s, max_events=limit)` plus in-process filter and normalization | `{status, applied_duration_s, applied_limit, partial: bool, reason: "time_cap"\|"limit_cap"\|"ok", items: [normalize_alarm_event(e)]}` |

### 3.2 Mutations — behind `--enable-alarms-mutation` and require `AXXON_ALARMS_APPROVE=1`

Each mutation requires a per-call confirmation token passed as `confirmation` parameter.

| Tool | Signature | Token | Backed by |
| --- | --- | --- | --- |
| `raise_alert(camera_access_point, confirmation)` | — | `CONFIRM-raise-alert` | `LogicService.RaiseAlert({camera_ap})` |
| `alarm_begin_review(camera_access_point, alert_id, confirmation)` | — | `CONFIRM-alarm-begin` | `BeginAlertReview` |
| `alarm_continue_review(camera_access_point, alert_id, confirmation)` | — | `CONFIRM-alarm-continue` | `ContinueAlertReview` |
| `alarm_cancel_review(camera_access_point, alert_id, confirmation)` | — | `CONFIRM-alarm-cancel` | `CancelAlertReview` |
| `alarm_complete_review(camera_access_point, alert_id, severity, bookmark_message, confirmation)` | `severity` is one of `"confirmed_alarm"\|"suspicious_situation"\|"false_alarm"`; `bookmark_message` is required because the stand's `required_comment` policy is `true` for all three categories | `CONFIRM-alarm-complete` | `CompleteAlertReview({severity, bookmark:{message:bookmark_message}, camera_ap, alert_id})` |
| `alarm_escalate(camera_access_point, alert_id, priority, user_roles, comment, confirmation)` | `priority` is `"AP_MINIMUM"\|"AP_LOW"\|"AP_MEDIUM"\|"AP_HIGH"`; `user_roles` is a non-empty list of role identifiers; `comment` is required | `CONFIRM-alarm-escalate` | `EscalateAlert({camera_ap, alert_id, priority, user_roles, comment})` |

**Common refusal paths:**

- `AXXON_ALARMS_APPROVE` ≠ `1` → `{status: "refused", reason: "approval_env_not_set"}`.
- Bad/missing token → `{status: "refused", reason: "bad_token", expected: "CONFIRM-..."}`.
- Unknown camera in inventory → `{status: "gap", message: "Camera not in inventory: ..."}`.
- `complete` with an unknown severity string → `{status: "gap", message: "severity must be one of ..."}`.
- `escalate` with empty `user_roles` or empty `comment` → `{status: "gap", message: ...}`.
- RPC failure → `{status: "error", error_type: ..., message: <sanitized>}` plus an audit-log entry with `result_status: "error"`.

---

## 4. Architecture

### 4.1 File layout

| Path | Purpose |
| --- | --- |
| `tools/axxon_mcp_alarms.py` | New module. `AxxonMcpAlarms` (reads + subscription) and `AxxonAlarmMutator` (mutations). |
| `tools/axxon_api_client.py` | Add 9 thin wrappers: `get_active_alerts`, `batch_get_active_alerts`, `batch_filter_active_alerts`, `raise_alert`, `begin_alert_review`, `continue_alert_review`, `cancel_alert_review`, `complete_alert_review`, `escalate_alert`. Each reuses `http_grpc(fqmn, data)`. |
| `tools/axxon_mcp_server.py` | Add `register_alarm_read_tools(server, alarms)` and `register_alarm_mutation_tools(server, mutator)`. Add `--enable-alarms` and `--enable-alarms-mutation` flags. Mutation block in `main()` constructs the mutator only when `AXXON_ALARMS_APPROVE=1`. |
| `tools/axxon_alarms_smoke.py` | New live smoke. Reads-only by default; `--mutation` flag runs synthetic `raise → begin → cancel` round-trip. |
| `tools/tests/test_axxon_mcp_alarms.py` | Offline unit tests with `FakeClient`. |
| `tools/tests/test_axxon_mcp_server.py` | Add registration tests for the two new groups. |
| `docs/api-audit/phase-5c-alarms-smoke-latest.md` | Sanitized live evidence. |
| `docs/api-audit/pdf-gap-coverage-matrix.md` | New row. |
| `README.md` | Document the two flags and list the tools. |

### 4.2 Class shape

```python
@dataclass
class AxxonMcpAlarms:
    """Read-only alarm tools + bounded alarm subscription."""
    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    _inventory: dict[str, Any] | None = None
    # methods: connect_axxon_profile, list_active_alerts, get_active_alert,
    #          filter_active_alerts, list_alarm_history, list_alarm_event_types,
    #          alarm_subscribe

@dataclass
class AxxonAlarmMutator:
    """Alarm lifecycle mutations gated by token + AXXON_ALARMS_APPROVE."""
    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    approve_env: str = "AXXON_ALARMS_APPROVE"
    env_getter: Callable[[str], str | None] = os.environ.get
    client: Any | None = None
    audit: list[dict[str, Any]] = field(default_factory=list)
    # methods: raise_alert, alarm_begin_review, alarm_continue_review,
    #          alarm_cancel_review, alarm_complete_review, alarm_escalate, audit_log
```

`AxxonAlarmMutator` takes `env_getter` as a factory so tests can inject `lambda _k: "1"` instead of monkeypatching `os.environ`.

### 4.3 Module constants

```python
# Cap and policy constants
LIST_LIMIT_CAP = 200
HISTORY_HOURS_CAP = 24
SUBSCRIBE_DURATION_CAP_S = 30
SUBSCRIBE_LIMIT_CAP = 100

# Alarm event-type filter (verified against Events.proto)
ALARM_EVENT_TYPES = ("ET_Alert", "ET_AlertState")

# Severity / priority enum mappings (string → proto enum)
SEVERITY_CHOICES = ("confirmed_alarm", "suspicious_situation", "false_alarm")
PRIORITY_CHOICES = ("AP_MINIMUM", "AP_LOW", "AP_MEDIUM", "AP_HIGH")

# Confirmation tokens — one per mutation
CONFIRMATION_TOKENS = {
    "raise_alert": "CONFIRM-raise-alert",
    "alarm_begin_review": "CONFIRM-alarm-begin",
    "alarm_continue_review": "CONFIRM-alarm-continue",
    "alarm_cancel_review": "CONFIRM-alarm-cancel",
    "alarm_complete_review": "CONFIRM-alarm-complete",
    "alarm_escalate": "CONFIRM-alarm-escalate",
}
```

### 4.4 Normalization helper

```python
def normalize_alarm(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize an active-alarm dict from GetActiveAlerts / BatchGet / Filter responses.

    Maps the verified Axxon shape to a stable MCP-side schema. Drops sub-fields
    that are not load-bearing for callers (`friendly_name` and `group` are
    optional; `required_comment` is preserved because completion needs it).
    """
    return {
        "alert_id": raw.get("guid") or raw.get("alert_id") or "",
        "state": _derive_state(raw),
        "severity": raw.get("severity"),
        "camera_access_point": (raw.get("camera") or {}).get("access_point"),
        "camera_friendly_name": (raw.get("camera") or {}).get("friendly_name"),
        "archive_access_point": (raw.get("archive") or {}).get("access_point"),
        "node_name": (raw.get("node_info") or {}).get("name"),
        "timestamp": raw.get("timestamp"),
        "required_comment": raw.get("required_comment"),
    }


def normalize_alarm_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a streamed event from PullEvents that has type ET_Alert/ET_AlertState.

    Adds a `transition` field derived from the event's state-change subtype,
    so callers can react to `raised` vs. `begun_review` vs. `completed` etc.
    without reading proto enum values.
    """
    ...
```

`_derive_state(raw)` maps from raw alarm fields to one of `"active"`, `"reviewing"`, `"completed"`, `"cancelled"`, `"escalated"`. On a quiet stand most active alerts are `"active"`. The exact derivation matches the `AlertState` proto enum found in `Events.proto`.

### 4.5 Audit-log entry shape

Each mutation appends one entry to `AxxonAlarmMutator.audit`:

```python
{
    "timestamp": "2026-05-16T17:57:40.155991+00:00",  # ISO 8601, UTC
    "action": "alarm_begin_review",
    "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
    "alert_id": "332e1fe4-5caa-4898-9c54-c34ffe0119db",
    "extra": {"reason": None, "severity": None, ...},  # action-specific
    "result_status": "ok" | "error" | "refused",
    "result_detail": "..." | None,
}
```

Audit is exposed via an MCP resource `axxon://alarms/audit-log` analogous to the existing `axxon://operator/audit-log` resource.

### 4.6 Server registration

```python
def register_alarm_read_tools(server, alarms):
    @server.tool(name="alarms_connect_axxon_profile")
    def _(profile: str = "env"): return alarms.connect_axxon_profile(profile)
    @server.tool(name="list_active_alerts")
    def _(camera_access_point: str | None = None, limit: int = 50): ...
    # ... 5 more reads

def register_alarm_mutation_tools(server, mutator):
    @server.tool(name="raise_alert")
    def _(camera_access_point: str, confirmation: str): ...
    # ... 5 more mutations
    @server.resource("axxon://alarms/audit-log")
    def _(): return {"entries": mutator.audit_log()}
```

In `main()`:

```python
alarms = None
if args.enable_alarms:
    from axxon_mcp_alarms import AxxonMcpAlarms
    alarms = AxxonMcpAlarms()

mutator = None
if args.enable_alarms_mutation:
    from axxon_mcp_alarms import AxxonAlarmMutator
    mutator = AxxonAlarmMutator()  # constructor doesn't check env; the methods do
```

### 4.7 Data-flow diagrams

**Read path:**
```
caller -> MCP tool -> AxxonMcpAlarms.method
       -> AxxonApiClient.http_grpc("LogicService.X", payload)
       -> normalize_alarm() per item
       -> sanitized dict to caller
```

**Subscription path:**
```
caller -> alarm_subscribe -> AxxonMcpAlarms.alarm_subscribe
       -> client.pull_events_bounded(subjects=[host], event_types=ALARM_EVENT_TYPES,
                                     timeout=applied_duration_s, max_events=applied_limit)
       -> iterate -> filter by severity_min/camera/state
       -> normalize_alarm_event() per item
       -> {items, partial, reason} to caller
```

**Mutation path:**
```
caller -> mutation tool (incl. confirmation token)
       -> AxxonAlarmMutator.method
       -> verify env_getter("AXXON_ALARMS_APPROVE") == "1"
       -> verify confirmation == CONFIRMATION_TOKENS[method]
       -> AxxonApiClient.http_grpc("LogicService.X", payload)
       -> append audit entry
       -> sanitized dict to caller
```

---

## 5. Error handling

| Condition | Result |
| --- | --- |
| Read tool transport error | `{status: "error", tool, error_type, message}`; never raises |
| Unknown camera in any tool | `{status: "gap", tool, message: "Camera not in inventory: <ap>"}` |
| Subscription cap reached | `{status: "ok", partial: true, reason: "time_cap"\|"limit_cap", items, applied_duration_s, applied_limit}` |
| Mutation: missing approval env | `{status: "refused", reason: "approval_env_not_set"}` |
| Mutation: bad confirmation token | `{status: "refused", reason: "bad_token", expected}` |
| Mutation: missing required field (e.g. empty `user_roles`) | `{status: "gap", message}` |
| Mutation: RPC error | `{status: "error", error_type, message}` + audit entry `result_status: "error"` |

Sanitization (carried over from Phase 5A): host IP, bearer token, password are stripped from every message field before returning. Tests assert `"secret" not in str(result)` and `"SHOULD_NOT_LEAK" not in str(result)` for both read and mutation paths.

---

## 6. Fixtures

| Tool | Fixture requirement |
| --- | --- |
| Reads (excl. subscription) | None — work on quiet stand returning empty lists |
| `alarm_subscribe` | None — empty result on quiet stand is a legitimate pass |
| `list_alarm_history` | None — empty result is legitimate |
| `raise_alert` | An inventoried camera. Every stand has cameras. |
| Single-target lifecycle mutations | An active alarm. Provided by chaining `raise_alert` in the smoke. |
| `alarm_complete_review` smoke step | Persists a bookmark — smoke uses `alarm_cancel_review` instead in normal runs and only exercises `alarm_complete_review` behind `--full` flag |
| `alarm_escalate` smoke step | Needs at least one configured role. Smoke probes `SecurityService.ListRoles` first; if zero non-system roles → `fixture-needed` with `missing: ["role"]` |

---

## 7. Testing strategy

### 7.1 Offline unit tests (`tools/tests/test_axxon_mcp_alarms.py`)

Following the Phase 5A test pattern (FakeConfig + FakeClient, no network).

**Reads:**
- `connect_axxon_profile` returns `connected`, `profile_name`, `mode: "read-only"`; no leaks.
- `list_active_alerts(camera_ap=known)` calls `client.get_active_alerts(known)`, normalizes one synthetic alert, returns `count=1` and the alarm fields.
- `list_active_alerts(camera_ap=None)` calls `client.batch_get_active_alerts([host])`, flattens `event_stream_items[].alerts`, ignores `unreachable_nodes` when at least one page has alerts.
- `list_active_alerts(camera_ap="unknown")` → gap.
- `get_active_alert(camera_ap=known, alert_id=existing)` returns that one alert.
- `get_active_alert(camera_ap=known, alert_id=missing)` → gap.
- `filter_active_alerts(severity_min=5)` filters out lower-severity items from the synthetic page.
- `list_alarm_history(hours=999)` clamps to 24, calls `client.search_events(event_types=ALARM_EVENT_TYPES, hours=24, limit=100)`.
- `list_alarm_event_types()` returns exactly the constants list with values from a FakeClient `list_event_types`.
- `alarm_subscribe(duration_s=999, limit=999)` clamps to caps; FakeClient's `pull_events_bounded` returns 3 synthetic events, normalizer produces `transition` per event; `partial=False, reason="ok"` because count < limit.
- `alarm_subscribe(limit=1)` with FakeClient yielding 3 events → `partial=True, reason="limit_cap"`.
- `normalize_alarm` strips serial-number-like fields; assertion `"SHOULD_NOT_LEAK" not in str(result)`.

**Mutations:**
- `AxxonAlarmMutator(env_getter=lambda _: None)` rejects all mutations with `reason: "approval_env_not_set"`.
- `AxxonAlarmMutator(env_getter=lambda _: "1")` with bad token → `reason: "bad_token", expected: "CONFIRM-..."`.
- `raise_alert(camera_ap="unknown", confirmation="CONFIRM-raise-alert")` → gap.
- `raise_alert(known, "CONFIRM-raise-alert")` calls `client.raise_alert(known)`, appends one audit entry with `result_status:"ok"`, returns `{status:"ok", alert_id:"..."}`.
- `alarm_complete_review` with severity not in `SEVERITY_CHOICES` → gap.
- `alarm_complete_review` with empty `bookmark_message` → gap.
- `alarm_escalate` with empty `user_roles` → gap.
- `alarm_escalate` with priority not in `PRIORITY_CHOICES` → gap.
- Each successful mutation: audit entry has timestamp, action, camera, alert_id, result_status, action-specific extras.
- RPC-raising FakeClient → `{status:"error", error_type:"FakeError", message:"..."}` and audit entry with `result_status:"error"`.

### 7.2 Server registration tests (`tools/tests/test_axxon_mcp_server.py`)

- `create_server(..., alarms=StubAlarms())` registers exactly: `alarms_connect_axxon_profile`, `list_active_alerts`, `get_active_alert`, `filter_active_alerts`, `list_alarm_history`, `list_alarm_event_types`, `alarm_subscribe`. Does NOT register mutation tools.
- `create_server(..., alarm_mutator=StubMutator())` registers exactly: `raise_alert`, `alarm_begin_review`, `alarm_continue_review`, `alarm_cancel_review`, `alarm_complete_review`, `alarm_escalate`, and the `axxon://alarms/audit-log` resource. Does NOT register read tools.
- `create_server(docs_only)` registers neither set.

### 7.3 Live smoke (`tools/axxon_alarms_smoke.py`)

Run modes:

- **Default (reads only):** authenticate; `list_active_alerts(camera=None)`; `list_active_alerts(camera=first_camera)`; `filter_active_alerts(state="all")`; `list_alarm_history(hours=1)`; `list_alarm_event_types()`; `alarm_subscribe(duration_s=5, limit=10)`. Prints sanitized JSON, exits `0` on success.
- **`--mutation` (synthetic round-trip):** authenticate; check `AXXON_ALARMS_APPROVE=1`; pick first camera; `raise_alert(camera) → capture alert_id → alarm_begin_review → alarm_continue_review → alarm_cancel_review`. Then read `list_active_alerts(camera)` and assert the alarm is gone. Print full audit log. Exits `0` on success, `2` on fixture-needed (e.g. zero cameras), `1` on real error. Does NOT exercise `complete` or `escalate` to avoid leaving bookmarks/escalation-records on the stand.
- **`--full`:** same as `--mutation` plus one `complete` and one `escalate` cycle. Run only on a dedicated stand. Documented behind a `--i-know-this-leaves-records` confirmation flag.

All printed URLs and stand identifiers are sanitized to `<demo-host>` / `<your-tls-cn>` / `<demo-alarm-id>` before printing.

### 7.4 Definition of done

1. All 13 tools registered (7 reads + 6 mutations) and offline-tested.
2. Server-registration tests for both groups pass.
3. Live `default` smoke passes against `100.76.150.18`.
4. Live `--mutation` smoke completes the `raise → begin → continue → cancel → verify-gone` round-trip cleanly, audit log captured.
5. Coverage matrix row added; LogicService pending count drops from 19 to ≤ 7 (deferred: 5 Batch* lifecycle methods, 2 counter mutations, `RaiseAlert` is now covered).
6. README documents `--enable-alarms`, `--enable-alarms-mutation`, `AXXON_ALARMS_APPROVE=1`, and lists tool names.
7. Repo unit-test suite stays green; target ≥ 215 / 215 (current 187 + ~25 new alarm tests + ~3 new server tests).

---

## 8. Out of scope

These are explicitly deferred to later phases:

- **Batch* lifecycle methods** (`BatchBeginAlertsReview`, `BatchContinueAlertsRewiew`, `BatchCancelAlertsReview`, `BatchCompleteAlertsReview`, `BatchEscalateAlerts`) — same shapes as single-target with `nodes[]` + `AlertFilter`; one-day extension once a customer asks.
- **Counter management** (`ChangeCounters`, `CounterAction`) — different LogicService domain; lives in Phase 5E (detector + analytics depth).
- **Rule `ChangeConfig`** — alarm-rule authoring; lives in Phase 5E or alongside macro authoring.
- **Notification-rule CRUD** — there is no separate "notification rule" service in this stand's surface; macros + rules cover that ground.
- **`GetActiveAlerts` streaming variant** — the single-page response is sufficient on a typical stand; if a high-volume stand exceeds a page we add the streaming variant then.
- **Alarm dashboards or UI rendering** — out of scope for this MCP entirely.

---

## 9. Risks and open questions

| Risk | Mitigation |
| --- | --- |
| `BatchGetActiveAlerts` `unreachable_nodes` first-page quirk could be misread as "node is down" | Flatten across all pages; only treat the node as unreachable if every page reports it. Document the quirk in `known_behaviors.json` after Phase 5C lands. |
| `alarm_complete_review` and `alarm_escalate` leave persistent records on the stand | Default `--mutation` smoke uses only `raise → begin → continue → cancel`. `complete`/`escalate` are gated behind `--full` + a typed confirmation flag. |
| Confirmation token strings are not secret — anyone reading the source knows them | Tokens are a UI affordance against accidents, not a security boundary. Real security is `AXXON_ALARMS_APPROVE=1` (intentional environment), plus the MCP transport layer's own auth. Same model as existing operator workflows. |
| `AlertFilter` proto message has many fields we are not using | We pass `filter: {}` for now, which the stand accepts. Adding filter knobs is a follow-up if a partner needs it. |
| Demo stand has no configured non-system roles → `alarm_escalate --full` smoke can't run | Smoke pre-flight queries `SecurityService.ListRoles`; if zero → `fixture-needed` with `missing: ["role"]`. Tools themselves still register and are usable on stands that do have roles. |

---

## 10. Sanitization summary

| Field | Rule |
| --- | --- |
| Host IP (`100.76.150.18`) | Replace with `<demo-host>` in all printed evidence |
| TLS CN (`Server`) | Replace with `<your-tls-cn>` in README and matrix; keep as literal `Server` in evidence when it's a structural value (e.g. `hosts/Server`) |
| Bearer token | Never echoed |
| Password | Never echoed; tests assert `"secret"` absent in `str(result)` |
| `alert_id` GUID | Kept as-is in code (it's ephemeral) but replaced with `<demo-alarm-id>` in committed evidence |
| Real usernames / role ids | Replaced with `<demo-user>` / `<demo-role>` in evidence if they appear |
| `hosts/Server/...` access points | Kept as-is (intrinsic, not credential material) |
