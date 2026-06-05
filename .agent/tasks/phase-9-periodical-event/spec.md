# Task Spec: phase-9-periodical-event

## Metadata
- Task ID: phase-9-periodical-event
- Created: 2026-06-05
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp

## Guidance sources
- STATUS.md, docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md
- docs/api-audit/capability-vs-coverage-2026-06-05.md (this gap identified there)
- Existing pattern: `_build_external_event_inject_plan` in tools/axxon_mcp_operator.py

## Original task statement
Add a `raise_periodical_event` operator workflow that pushes an external
periodical detector event into Axxon One via
`ExternalDetectorService.RaisePeriodicalEvent`
(HTTP `POST /v1/detectors/external:raisePeriodicalEvent`). The payload carries a
`PeriodicalEventData.TargetList` of `Tracklet`s (object id, type, bounding box
rectangle): object-tracking metadata from an external ML detector. Closes a
genuine zero-coverage capability: today only one-shot `external_event_inject`
(`RaiseOccasionalEvent`, freeform `Struct`) is exposed.

## Acceptance criteria
- AC1: A `raise_periodical_event` workflow is registered in
  `tools/axxon_mcp_operator.py` `WORKFLOWS`, built by
  `_build_raise_periodical_event_plan(host_uid, params)` mirroring
  `_build_external_event_inject_plan`.
- AC2: The plan emits a single `http_post` step to
  `/v1/detectors/external:raisePeriodicalEvent` whose body has `accessPoint`,
  `eventType`, `timestamp` (RFC3339 Z), and `data.targetList.tracklets[]`; each
  tracklet carries `objectId`, `objectType`, `rectangle` (x/y/w/h). Tracklets
  come from `params["tracklets"]`; a default single tracklet is synthesized when
  none supplied.
- AC3: Missing `access_point` returns `{"status": "gap", ...}` (same contract as
  `external_event_inject`), not an exception.
- AC4: Plan declares `risk: "mutation"`, `confirmation_token`
  (`CONFIRM-raise_periodical_event`), a rollback token, and `noop` rollback.
- AC5: Unit tests under `tools/tests/` cover plan shape (path + body keys),
  tracklet defaulting, custom-tracklet pass-through, and the missing-access_point
  gap. Full suite stays green (`python3.12 -m unittest discover -s tools/tests`).
- AC6: Corpus `ExternalDetectorService.RaisePeriodicalEvent` is restamped
  `pending -> tested-pass` via `tools/axxon_corpus_restamp.py` with a cited
  evidence string ONLY IF live evidence confirms the stand accepts the call;
  otherwise it stays `pending` and the live result is recorded in the evidence
  bundle.

## Constraints
- Reuse `AxxonApiClient` HTTP path; mirror plan/apply/verify/rollback, `codex-*`
  ids, env-only secrets.
- Mutating: runs only under `--enable-operator-mutations` +
  `AXXON_OPERATOR_APPROVE=1` + confirmation token, like `external_event_inject`.
- No defensive programming beyond the existing gap-return contract.
- Sanitize committed live evidence (`<demo-host>`, `<demo-user>`, `<redacted>`).
- No copyrighted proto/PDF content committed. Google-style docstrings, no banned words.

## Non-goals
- gRPC-stub path (HTTP `/v1` is the verified CA-free path).
- A generator template for periodical events.
- Full Tracklet schema fidelity (color/velocity/keypoints) beyond id/type/rectangle.

## Verification plan
- Build: edit tools/axxon_mcp_operator.py only (plus tests).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` green incl. new tests.
- Integration tests: live apply against `hosts/Server/DetectorEx.1/EventSupplier`
  (proven external-detector AP from phase-6-gap-closure); record HTTP code/body in
  `raw/`. Retry up to 3x on transient urlopen timeouts. Stand may be unreachable;
  record outcome either way.
- Lint: n/a (repo has no configured linter gate; rely on unittest).
- Manual checks: dry-run plan JSON inspected for AC2/AC4 shape.

## Live findings (2026-06-05, drove an AC/scope update)
- The external-detector endpoints return **HTTP 200 even on rejection**; the real
  outcome is in the JSON body `{"error": "OK" | "BAD_EVENT_TYPE" | ...}`. The
  apply-loop `status >= 400` check therefore silently reported success on a
  rejected event (false positive). **Added AC7**: the `http_post` apply handler
  must treat a response body `{"error": <non-OK>}` as a failure. This also hardens
  the existing `external_event_inject`.
- The **periodical** endpoint accepts `eventType: "TargetList"` (matches
  `PeriodicalEventData.TargetList`); `Event1` is rejected. The **occasional**
  endpoint accepts `Event1`, rejects `TargetList`. So the periodical default
  `event_type` is `"TargetList"`, not `"Event1"` (updates AC2's default).
- AC6 restamp is justified: with `eventType=TargetList` the stand returns
  `{"error": "OK"}` at `hosts/Server/DetectorEx.1/EventSupplier`.

## AC7 (added from live findings)
- AC7: The operator `http_post` apply handler treats a 2xx response carrying a
  body `{"error": <value other than "OK">}` as an apply failure (returns
  `{"status": "error", ...}`), so external-detector rejections are not reported as
  `applied`. A unit test covers both the OK and the BAD_EVENT_TYPE body paths.
