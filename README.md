# axxon-one-mcp

Model Context Protocol (MCP) server, audit tooling, and Integration APIs 3.0
coverage matrix for Axxon One VMS.

## Status

- **669 / 669** unit tests passing on `main`.
- **39** PDF gap-coverage matrix rows. 32 verified, 2 partial, and 5
  fixture-blocked rows (hardware / process gates on the demo stand are
  documented under `docs/api-audit/`).
- **31** MCP operator workflows, including 11 Phase 5D layouts/maps/videowalls
  workflows, with
  plan / apply / verify / rollback safety.
- **15** Phase 2 read-only live tools covering inventory, events, metadata,
  archive, detector discovery, and bounded subscriptions.
- **6** Phase 5A view tools: `live_view`, `snapshot_batch`, `archive_scrub`,
  `archive_frame`, `archive_mjpeg_bounded`, `stream_health` (URL-only, byte
  and time capped). Live-verified — see `docs/api-audit/phase-5a-view-smoke-latest.md`.
- **7 reads + 6 mutations** Phase 5C alarm tools (`list_active_alerts`,
  `get_active_alert`, `filter_active_alerts`, `list_alarm_history`,
  `list_alarm_event_types`, `alarm_subscribe`, plus `raise_alert` and the
  full review lifecycle). Live-verified — see
  `docs/api-audit/phase-5c-alarms-smoke-latest.md`.
- **11 reads + 11 workflows** Phase 5D view-object coverage for layouts, maps,
  markers, and videowalls. Live-verified for map/videowall round-trips and
  read inventory; layout-image live fixture is absent on the demo stand — see
  `docs/api-audit/phase-5d-view-objects-smoke-latest.md`.
- **11 reads + 9 workflows** Phase 5E detector/archive coverage for detector
  schemas, detector config snapshots, metadata sampling, archive policy/status
  reads, full detector creation/update/delete, archive policy update, and
  approval-gated archive maintenance no-ops. Live evidence PASS=12, WARN=3,
  FAIL=0 — see
  `docs/api-audit/phase-5e-detector-archive-smoke-latest.md`.
- **11** Phase 5F-A admin read tools cover security inventory,
  policy/permission summaries, current-user security, license/time/system
  health, bounded DomainNotifier/NodeNotifier pulls, and schedule descriptor
  discovery. Live evidence PASS=7, WARN=4, FAIL=0 — see
  `docs/api-audit/phase-5f-admin-smoke-latest.md`.
- **5** Phase 5F-B1 admin mutation workflows cover temporary `codex-*`
  user/role lifecycle, temp-role permissions, policy no-op replay, temporary
  LDAP add/edit/remove, and temporary-user TFA enable/disable. Live evidence
  PASS=5, WARN=0, FAIL=0 — see
  `docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md`.
  License, timezone, NTP, production user/role edits, LDAP sync against a real
  directory, and schedule authoring remain deferred.
- **13** integration generator template kinds, each in **Python + Node/TypeScript**
  (26 bundles). The 8 base templates (grpc_consumer, http_grpc_consumer,
  legacy_http_consumer, event_consumer, external_event_producer, export_job,
  webhook_bridge, inventory_sync) plus 5 higher-level kinds added in Phase 6A
  (alarm_responder, scheduled_exporter, ml_detector_bridge, dashboard_backend,
  plugin_scaffold). A static verifier rejects embedded secrets, disallowed
  imports, and missing safety caps in both languages. The 8 base templates are
  verified end-to-end against the demo stand
  (`docs/api-audit/mcp-generation-runtime-smoke-latest.md`); generated bundles
  (including the new kinds) were live-verified — see
  `.agent/tasks/phase-6a-live-verify/evidence.md`. A destructive gap-closure pass
  also exercised the mutating kinds live: `ml_detector_bridge` raised real events
  and `alarm_responder` completed review on real alerts (which fixed the
  CompleteAlertReview severity), see `.agent/tasks/phase-6-gap-closure/`.
- **Phase 6B partner SDK kit**: `scaffold_plugin`, `plugin_lint`,
  `plugin_package` (`tools/axxon_mcp_partner.py`), with reference Python + Node
  plugins under `customer-templates/` kept lint-clean and packageable by CI.
  Verified live end-to-end: scaffold -> lint -> package -> the scaffolded plugin
  connects to the stand and lists cameras.

See `docs/api-audit/pdf-gap-coverage-matrix.md` for the canonical coverage matrix
and [`STATUS.md`](STATUS.md) for the current handoff document and remaining roadmap.

### Roadmap snapshot

| Phase | Status |
| --- | --- |
| 5A — Live + archive viewing | ✅ shipped |
| 5B — PTZ + Tag&Track | ⏸ deferred (no PTZ fixture) |
| 5C — Alarms | ✅ shipped |
| 5D — Videowall / layouts / maps | ✅ shipped |
| 5E — Detector depth + archive policies | ✅ shipped (fixture caveats) |
| 5F-A — Security / system-health reads + bounded notifiers | ✅ shipped (fixture caveats) |
| 5F-B1 — Security/admin mutations | ✅ shipped |
| 5F-B2 — Reversible production role edit | ✅ partial (rest deferred) |
| 5G — BookmarkService reads + lifecycle | ✅ shipped |
| 5H — Metadata / VMDA object-track search | ✅ shipped (live tracklets + archived objects verified) |
| 6A — Authoring kit expansion (Python + Node) | ✅ shipped (only `ptz_controller` left, PTZ fixture gap) |
| 6B — Partner SDK kit + distribution | ✅ shipped |
| 7 — NL → plan translator | ✅ shipped |

Full plan: [`docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md`](docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md).

## Layout

```
tools/                       — runnable smokes, MCP server, operator workflows, fixtures
  axxon_mcp_server.py        — entrypoint; docs / live / operator transports
  axxon_mcp_docs.py          — phase-1 docs-only query layer
  axxon_mcp_live.py          — phase-2 read-only live inspection
  axxon_mcp_operator.py      — phase-3 controlled mutation workflows
  axxon_mcp_operator_smoke.py — live smoke harness for all operator workflows
  axxon_mcp_generator.py     — phase-4/6A integration code generator (python + node)
  axxon_mcp_generator_smoke.py — static smoke that generates+verifies all templates
  axxon_mcp_generator_runtime_smoke.py — live runtime smoke for the 8 base templates
  axxon_mcp_partner.py       — phase-6B partner SDK kit (scaffold/lint/package)
  axxon_mcp_metadata.py      — phase-5H metadata/VMDA search (live tracklets + archived query)
  axxon_mcp_view_objects.py  — phase-5D layouts/maps/videowalls read tools
  axxon_view_objects_smoke.py — phase-5D live read + mutation smoke
  axxon_mcp_detector_archive.py — phase-5E detector/archive read tools
  axxon_detector_archive_smoke.py — phase-5E live read + mutation smoke
  axxon_mcp_admin.py          — phase-5F-A security/health/notifier read tools
  axxon_admin_smoke.py        — phase-5F-A live read smoke
  axxon_mcp_admin_mutations.py — phase-5F-B1 approval-gated admin mutation workflows
  axxon_admin_mutation_smoke.py — phase-5F-B1 live mutation smoke
  templates/                 — phase-4 string templates for generated bundles
  axxon_aux_topics_smoke.py  — aux topic coverage smoke (statistics, groups, alerts, ...)
  axxon_api_client.py        — gRPC + HTTP /grpc + legacy HTTP transport
  axxon_*_smoke.py           — per-area runnable verification scripts
  tests/                     — unit tests

customer-templates/          — phase-6B reference plugins (python + node), CI-green
.agent/tasks/                — repo-task-proof-loop artifacts (spec/evidence/verdict per task)

docs/
  AXXON_ONE_API_BOOK.md      — primary API book (verified examples only)
  AXXON_ONE_API_EXPERT_CONTEXT.md
  AXXON_ONE_API_TESTING_RUNBOOK.md
  api-audit/                 — per-area evidence reports + run logs
    pdf-gap-coverage-matrix.{md,json}
    mcp-corpus/              — structured JSON corpus for MCP consumers
    mutation-playbooks/      — approval-gated mutation procedures
  plans/                     — planning docs
  api-test-runs/             — archived legacy probe runs
```

## MCP server

The MCP server has optional capability sets:

Set connection credentials through environment variables before starting a live
server. Keep `AXXON_PASSWORD` in the shell/secret manager and out of command
lines.

```bash
# docs-only (no live connection)
python tools/axxon_mcp_server.py --transport stdio

# + read-only live inventory tools
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-live --transport stdio

# + controlled operator (plan/apply/verify/rollback) workflows
AXXON_OPERATOR_APPROVE=1 \
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-live --enable-operator --transport stdio

# + integration code generator (list/plan/generate/verify_integration)
python tools/axxon_mcp_server.py --enable-generator --transport stdio

# + partner SDK kit (scaffold_plugin/plugin_lint/plugin_package, Phase 6B)
python tools/axxon_mcp_server.py --enable-partner --transport stdio

# + metadata / VMDA object-track search (Phase 5H)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-metadata --transport stdio

# + NL -> plan translator / recipe assembler (Phase 7)
python tools/axxon_mcp_server.py --enable-translator --transport stdio

# + live + archive viewing tools (Phase 5A)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-view --transport stdio

# + alarm read tools (Phase 5C)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-alarms --transport stdio

# + alarm lifecycle mutations (Phase 5C) — requires per-call confirmation tokens
AXXON_ALARMS_APPROVE=1 \
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-alarms --enable-alarms-mutation --transport stdio

# + layouts/maps/videowalls read tools (Phase 5D)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-view-objects --transport stdio

# + detector/archive read tools (Phase 5E)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-detector-archive --transport stdio

# + security/system-health/notifier read tools (Phase 5F-A)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-admin --transport stdio

# + admin mutation workflows (Phase 5F-B1) — requires plan/apply/verify/rollback confirmations
AXXON_ADMIN_MUTATION_APPROVE=1 \
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> \
python tools/axxon_mcp_server.py --enable-admin-mutations --transport stdio
```

### Live tools (read-only)

`connect_axxon_profile`, `list_cameras`, `list_archives`, `list_config_units`,
`list_detectors`, `list_appdata_detectors`, `find_event_suppliers`,
`find_metadata_endpoints`, `preflight_task`, `get_archive_intervals`,
`subscribe_events_bounded`, `list_event_types`, `list_detector_kinds`,
`search_events`, `pull_metadata_bounded`.

### Operator workflows

Ephemeral (auto-rollback): `temp_camera`, `temp_archive`, `temp_av_detector`,
`temp_appdata_detector`, `temp_device_template`, `external_event_inject`,
`temp_macro`, `temp_wall`.

Persistent (caller owns lifecycle): `create_camera`, `create_macro`,
`create_layout`, `set_unit_properties`, `update_layout`, `delete_layout`,
`videowall_register`, `videowall_change`, `videowall_set_control_data`,
`videowall_unregister`, `create_map`, `update_map`, `delete_map`,
`update_markers`, `create_av_detector_full`, `create_appdata_detector_full`,
`update_detector_parameters`, `update_detector_visual_element`,
`delete_detector`, `archive_policy_update`, `archive_format_volume`,
`archive_reindex`, `archive_cancel_reindex`.

All workflows expose: `list_operator_workflows`, `plan_operator_workflow`,
`apply_operator_plan`, `verify_operator_plan`, `rollback_operator_plan`. Plans
require a confirmation token before apply; rollback uses a separate token.

### Integration generator (Phase 4 + 6A)

`list_integration_templates`, `plan_integration`, `generate_integration`,
`verify_integration`. Each template generates in `language="python"` (default)
or `language="node"`.

Base templates: `grpc_consumer`, `http_grpc_consumer`, `legacy_http_consumer`,
`event_consumer`, `external_event_producer`, `export_job`, `webhook_bridge`,
`inventory_sync`.

Phase 6A higher-level kinds: `alarm_responder` (reads a camera's active alerts
then runs the `BeginAlertReview`->`CompleteAlertReview` lifecycle,
mutation-gated), `scheduled_exporter` (bounded scheduled loop over
`ExportService.ListSessions`), `ml_detector_bridge` (reads ML results from disk
then raises a bounded `RaiseOccasionalEvent` batch, mutation-gated),
`dashboard_backend` (read-only snapshot of `ListCameras` + per-camera
`GetActiveAlerts` + `ReadEvents` to a byte-capped JSON file), and
`plugin_scaffold` (a full runnable plugin repo: auth + `ListCameras` with retry,
env loader, test, CI, README + Safety section, LICENSE).

`ptz_controller` is the only planned 6A kind not yet shipped; it is blocked on a
live PTZ-camera fixture on the demo stand. C# remains a future renderer layer.

Generated bundles read credentials only from environment, apply
duration/byte/count caps, and refuse `output_dir` paths inside this repo unless
`AXXON_GENERATOR_ALLOW_IN_REPO=1`. The static verifier covers both Python and
TypeScript. See
`docs/plans/2026-05-15-mcp-phase-4-integration-generation.md`, the static smoke
evidence at `docs/api-audit/mcp-generation-smoke-latest.md`, and the 6A
increment artifacts under `.agent/tasks/phase-6a-*`.

### Partner SDK kit (Phase 6B)

`scaffold_plugin`, `plugin_lint`, `plugin_package` (enable with
`--enable-partner`; `tools/axxon_mcp_partner.py`). `scaffold_plugin(name,
output_dir, language)` emits a runnable plugin repo (reusing the
`plugin_scaffold` template). `plugin_lint(path)` runs the static verifier plus
repo-level checks (`.env.example` present, a test file present, README has a
Safety section, no committed secrets). `plugin_package(path, output, fmt)`
produces a `zip` or `tar.gz` plus a manifest with a SHA-256 of every file, and
refuses to package a repo that does not lint clean. Reference Python + Node
plugins live in `customer-templates/` and are kept lint-clean and packageable by
`tools/tests/test_customer_templates.py`. See
`.agent/tasks/phase-6b-partner-sdk/evidence.md`.

### Metadata / VMDA search (Phase 5H)

Reads (`--enable-metadata`): `metadata_connect_axxon_profile`, `list_vmda_sources`,
`live_track_sample`, `vmda_query`. This is the gRPC equivalent of the desktop client's
"Metadata search". `list_vmda_sources` enumerates the stand's `*/SourceEndpoint.vmda`
endpoints. `live_track_sample(access_point, seconds, limit)` streams bounded live object
tracklets via `MetadataService.PullMetadata` (id, state, behavior, bbox), clamped to module
caps and stopped cleanly at the duration/limit cap. `vmda_query(camera_id, query_type,
database, hours, max_intervals, timeout)` runs an archived forensic search via
`VMDAService.ExecuteQuery` MomentQuest motion-in-area: it binds `access_point` to the VMDA
database (`*/VMDA_DB.N/Database`, auto-discovered), `camera_ID` to the host-relative detector
source, `schema_ID="vmda_schema"`, and a MomentQuest `query` string with
`language="EVENT_BASIC"` (per Integration APIs 3.0). It returns intervals with object bounding
boxes, and is live-verified against real recorded objects on camera 1's tracker. Credentials are
env-only and the module never mutates stand config. See
`.agent/tasks/phase-5h-metadata-search/evidence.md` and `.agent/tasks/phase-5h-vmda-fix/`.

### View tools (Phase 5A)

`view_connect_axxon_profile`, `live_view`, `snapshot_batch`, `archive_scrub`,
`archive_frame`, `archive_mjpeg_bounded`, `stream_health`. URL-only — callers
fetch media with the Bearer token from `view_connect_axxon_profile`. Every
tool clamps inputs against module constants (`DEFAULT_MAX_BYTES = 1 MiB`,
`DEFAULT_DURATION_S = 10`, `DEFAULT_FPS = 5`, `SNAPSHOT_BATCH_LIMIT = 8`,
`ARCHIVE_MJPEG_BYTE_CAP = 4 MiB`, `ARCHIVE_FRAME_THRESHOLD_MS = 60_000`) and
reports the applied value back in `caps`. The MCP never proxies media bytes.
See `docs/superpowers/plans/2026-05-16-phase-5a-live-archive-viewing.md` and
the offline + live evidence at `docs/api-audit/phase-5a-view-smoke-latest.md`.

### Alarm tools (Phase 5C)

Reads (`--enable-alarms`): `alarms_connect_axxon_profile`, `list_active_alerts`,
`get_active_alert`, `filter_active_alerts`, `list_alarm_history`,
`list_alarm_event_types`, `alarm_subscribe` (bounded by 30 s / 100 events).

Mutations (`--enable-alarms-mutation` + `AXXON_ALARMS_APPROVE=1`):
`raise_alert`, `alarm_begin_review`, `alarm_continue_review`,
`alarm_cancel_review`, `alarm_complete_review` (requires `severity` in
`confirmed_alarm|suspicious_situation|false_alarm` and a non-empty bookmark
message), `alarm_escalate` (requires `priority` in
`AP_MINIMUM|AP_LOW|AP_MEDIUM|AP_HIGH`, non-empty `user_roles`, non-empty
`comment`). Every mutation requires a per-call `CONFIRM-...` token and writes
one audit entry; the audit log is exposed via the
`axxon://alarms/audit-log` resource. See
`docs/superpowers/plans/2026-05-16-phase-5c-alarms.md` and the live evidence
at `docs/api-audit/phase-5c-alarms-smoke-latest.md`.

### View-object tools (Phase 5D)

Reads (`--enable-view-objects`): `view_objects_connect_axxon_profile`,
`list_layouts`, `get_layout`, `layouts_on_view`, `list_layout_images`,
`list_maps`, `get_map`, `get_map_image` (4 MiB byte cap; returns metadata only,
never raw image bytes), `get_markers`, `list_map_providers`, `list_walls`.

Operator workflows (under `--enable-operator` + `AXXON_OPERATOR_APPROVE=1`):
`temp_wall`, `videowall_register`, `videowall_change`,
`videowall_set_control_data`, `videowall_unregister`, `create_map`,
`update_map`, `delete_map`, `update_markers`, `update_layout`,
`delete_layout`. Synthetic wall and map round-trips are live-verified; layout
mutations are offline-tested and intentionally not run against shared demo
layouts. `list_layout_images` dispatch is offline-tested, but the demo stand
has no readable layout-image fixture and reports `status: gap`.

Schedules moved to Phase 5F-A descriptor discovery; authoring remains
fixture-needed until an isolated descriptor-backed schedule fixture exists. See
`docs/superpowers/plans/2026-05-26-phase-5f-security-health-schedules.md` and
the Phase 5D live evidence at `docs/api-audit/phase-5d-view-objects-smoke-latest.md`.

### Detector/archive tools (Phase 5E)

Reads (`--enable-detector-archive`): `detector_archive_connect_axxon_profile`,
`detector_kind_catalog`, `detector_parameter_schema`, `detector_config_get`,
`detector_visual_elements`, `metadata_schema_catalog`,
`metadata_sample_bounded`, `archive_policy_get`, `archive_management_status`,
`archive_volume_probe`, `analytics_fixture_report`.

Operator workflows (under `--enable-operator` + `AXXON_OPERATOR_APPROVE=1`):
`create_av_detector_full`, `create_appdata_detector_full`,
`update_detector_parameters`, `update_detector_visual_element`,
`delete_detector`, `archive_policy_update`, `archive_format_volume`,
`archive_reindex`, `archive_cancel_reindex`. Full detector workflows are
caller-owned persistent creations with explicit rollback tokens; AppData
creation can derive a VMDA source by chain-creating a SceneDescription
AVDetector. Archive policy updates require descriptor-backed property IDs and a
snapshot rollback. Archive maintenance workflows require
`AXXON_ARCHIVE_MAINTENANCE_APPROVE=1`; the live smoke only verifies no-op
dispatch against `codex-nonexistent-*` volume ids.

Combined live evidence is PASS=12, WARN=3, FAIL=0 for read-only, mutation, and
archive-maintenance-no-op modes. Remaining warnings require a descriptor that
exposes archive policy fields, an AV detector fixture with a writable visual
child, and an isolated `codex-*` archive/camera fixture. See
`docs/superpowers/plans/2026-05-19-phase-5e-detectors-archive-policies.md` and
`docs/api-audit/phase-5e-detector-archive-smoke-latest.md`.

### Admin tools (Phase 5F-A)

Reads (`--enable-admin`): `admin_connect_axxon_profile`,
`security_inventory`, `security_policy_summary`, `role_permissions`,
`current_user_security`, `license_status`, `time_status`, `system_health`,
`domain_event_subscribe`, `node_event_subscribe`, `schedule_descriptor_get`.
The admin layer is read-only except for bounded notifier subscription channel
creation/disconnect cleanup. The live smoke also keeps credentials env-only and
redacts host, user, role, CA, token, license, serial, and hardware evidence.

Live evidence is PASS=7, WARN=4, FAIL=0. Warnings are fixture or stand
behavior: `LicenseService.GetHostInfo` closes the connection while other
license reads succeed, both notifier streams are quiet and end by bounded
deadline after disconnect cleanup, and schedule descriptor discovery needs an
isolated descriptor-backed schedule fixture. See
`docs/superpowers/plans/2026-05-26-phase-5f-security-health-schedules.md` and
`docs/api-audit/phase-5f-admin-smoke-latest.md`.

### Admin mutation tools (Phase 5F-B1)

Mutations (`--enable-admin-mutations` + `AXXON_ADMIN_MUTATION_APPROVE=1`):
`list_admin_mutation_workflows`, `plan_admin_mutation_workflow`,
`apply_admin_mutation_plan`, `verify_admin_mutation_plan`,
`rollback_admin_mutation_plan`. Every workflow returns a plan id, an apply
confirmation token, and a separate rollback confirmation token; `apply` and
`rollback` reject mismatched tokens or missing approval.

The shipped workflows are intentionally limited to temporary `codex-*`
fixtures: `security_user_role_lifecycle`, `security_role_permissions_update`,
`security_policy_noop_probe`, `security_ldap_temp_lifecycle`, and
`security_tfa_temp_user_lifecycle`. Generated passwords, TFA secrets, OTP
codes, bearer tokens, concrete host/user/CA values, licensing identifiers, and
device identifiers are redacted from reports and audit output.

Live evidence is PASS=5, WARN=0, FAIL=0 at
`docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md`. Deferred 5F-B2
scope remains high-risk or fixture-dependent: license apply/drop, timezone and
NTP changes, production user/role edits, LDAP sync against a real directory,
and schedule authoring.

## Verification

```bash
# Unit tests (669 / 669)
python3.12 -m unittest discover -s tools/tests

# Generator runtime smoke against a stand (set AXXON_HOST to host:GRPC_PORT for
# the direct-gRPC bundles, e.g. AXXON_HOST=<host>:20109)
python3.12 tools/axxon_mcp_generator_runtime_smoke.py

# Operator live smoke (plan-only by default)
python3.12 tools/axxon_mcp_operator_smoke.py

# Operator live smoke (full apply/verify/rollback cycle)
python3.12 tools/axxon_mcp_operator_smoke.py --enable-live
```

## Demo stand notes

The audit evidence under `docs/api-audit/` was generated against a private
Axxon One demo stand. Host IP and TLS CN are sanitized in published evidence
(replaced with `<demo-host>` / `<your-tls-cn>` / `<demo-tls-cn>`). The
`hosts/Server/...` access-point UIDs in evidence are intrinsic to that stand
and are meaningless without it.

## License

See `LICENSE`.

This project is unaffiliated with AxxonSoft. The Integration APIs 3.0 PDF and
its derived proto / Markdown content (under `docs/integration-apis-3.0/` in
the source repo) are AxxonSoft copyrighted material and are intentionally
excluded from this repository. Only audit tooling and evidence authored for
this project is published here.
