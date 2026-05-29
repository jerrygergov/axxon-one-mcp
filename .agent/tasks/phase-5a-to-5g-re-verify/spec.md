# Task Spec: phase-5a-to-5g-re-verify

## Metadata
- Task ID: phase-5a-to-5g-re-verify
- Repo root: <worktree root>

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md

## Original task statement
Close every fixture/coverage gap that is closeable now across phases 5A through 5G,
verified live against the real demo stand. PTZ (Phase 5B) stays deferred (no PTZ hardware).
The stand is test-only; max-aggressive live mutations are authorized provided every mutation
is reversible and rolled back. The user bound camera 1 to an archive to enable recording.

## Corrected live env (critical)
The TLS CN for the stand's gRPC cert is `Server` (verified via openssl: subject CN=Server,
issuer "api.ngp Root CA"), NOT `axxon`. With `AXXON_TLS_CN=Server` plus the local CA
(`docs/grpc-proto-files/api.ngp.root-ca.crt`, gitignored) and the local proto files, direct
gRPC to port 20109 works from this host. Prior WARN/fixture results were largely caused by the
wrong CN. The proto/CA dir is symlinked into the worktree for live runs and must NOT be committed.

Live env for all smokes:
```
export AXXON_HOST=<demo-host> AXXON_HTTP_URL=http://<demo-host>
export AXXON_USERNAME=<demo-user> AXXON_PASSWORD=<redacted>
export AXXON_TLS_CN=Server
export AXXON_CA=docs/grpc-proto-files/api.ngp.root-ca.crt
```

## Live findings (probed this session)
- Stand exposes 37 cameras over HTTP /grpc (`DomainService.ListCameras`, server-streamed
  `text/event-stream`). `ListArchives`, `ListComponents` also stream; `GetVersion`, `ListNodes`
  are unary. All reachable over HTTP /grpc with bearer auth, NO TLS/CA.
- Root cause of the camera/archive "fixture-needed" WARNs: `AxxonApiClient.load_inventory()`
  uses direct gRPC stubs that need the stand root CA + proto files, which are unavailable on
  this stand (`load_inventory()` raises FileNotFoundError). The reads themselves work over HTTP.
- Archive recording on the stand is being enabled by the user (camera 1 bound to an archive);
  recorded intervals may appear with a delay.

## Acceptance criteria
- AC1: `AxxonApiClient` gains an HTTP /grpc inventory path that returns the same inventory dict
  shape as `load_inventory()` (keys: version, platform, nodes, cameras, archives, components,
  host_unit) using only `http_grpc` event-stream/unary calls (no gRPC stubs, no CA). When the
  gRPC-stub `load_inventory()` cannot run (missing CA/proto), the client transparently falls
  back to the HTTP path so `inventory`, `archive_access_point()`, `archive_source_access_point()`,
  and camera-dependent smokes work without the CA. Covered by unit tests using a fake transport
  that returns event-stream-shaped responses; tests assert camera/archive extraction and fallback.
- AC2: Live verification against the stand with approval envs set produces FAIL=0 for all of
  5A, 5C, 5D, 5E, 5F-A, 5F-B1, 5G. Camera-dependent read smokes (5A live_view/snapshot/scrub,
  5E detector/archive reads) resolve a real camera via the HTTP inventory instead of returning
  fixture-needed. Mutation lifecycles (5C alarms, 5F-B1 admin, 5G bookmark) are exercised with
  approval envs and per-call confirmation tokens, then rolled back. Any group that is still
  blocked by a genuine stand limitation (e.g. no recorded archive interval yet) records WARN
  with a precise reason, not FAIL. Evidence committed is sanitized.
- AC3: Full unit suite stays green (`python3.12 -m unittest discover -s tools/tests`, count
  >= 495). `git diff --check` clean. Docs updated: STATUS.md test baseline + phase notes,
  roadmap status, coverage matrix, and api_methods.json live_status flips for any methods that
  moved from fixture-blocked to live-verified. A fresh verifier writes verdict.json = PASS.

## Constraints
- Reuse `AxxonApiClient.http_grpc`; no new transport. No TLS/CA dependency in the HTTP inventory
  path. Keep the existing gRPC `load_inventory()` working when CA/proto ARE present.
- Mutations require approval env + per-call confirmation tokens (existing 5C/5F-B1/5G pattern).
  Every live mutation must be rolled back / deleted; leave the stand as found.
- Env-only secrets. Sanitize all committed evidence: host -> <demo-host>, user -> <demo-user>,
  CA/token/password -> <redacted>, camera UID/access point redacted where it is credential-like
  (hosts/Server/... device UIDs are intrinsic to the stand and may stay per existing policy).
- No defensive programming beyond the user-facing safety guarantees.
- TDD: failing test first, minimal code, passing test, commit per logical task. Push to main.
- Do not commit local proto files, the CA, or copyrighted PDFs.

## Non-goals
- Phase 5B (PTZ / Tag&Track): deferred, no PTZ hardware on the stand.
- RenderTrack (5G): out of scope (returns media).
- Phases 6A/6B/7: not part of this gap-closing pass.
- Forcing archive recording: cannot fabricate recorded footage; if no interval exists yet, that
  specific archive-frame/mjpeg path stays WARN with a precise reason.

## Verification plan
1. Unit: fake-transport tests for the HTTP inventory loader + fallback; full suite >= 495 OK.
2. Live: re-run all 7 phase smokes with approval envs against the stand; capture sanitized
   PASS/WARN/FAIL; confirm camera-dependent reads resolve a real camera via HTTP inventory.
3. Fresh verifier subagent judges current code + current live reruns, writes verdict.json.
