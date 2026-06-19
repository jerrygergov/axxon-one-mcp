# axxon-one-mcp

A Model Context Protocol (MCP) server for [Axxon One VMS](https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314535799/Documentation).
It exposes the Axxon One gRPC / HTTP Integration API to an LLM as a large set of typed
tools, so you can inspect, operate, and configure a VMS — and generate integrations
against it — in plain language.

It covers what the desktop client can do: view live and archive video, pull events,
read and change configuration, add cameras / detectors / layouts, drive PTZ, manage
alarms and macros, run exports, browse the Web client surface, and generate partner
integrations.

## What's included

- **327 available tools** across **53 opt-in capability groups**. A no-flag start is the
  knowledge-only profile: it exposes exactly seven knowledge tools and requires no
  credentials or server connection.
- One client implementation (`tools/axxon_api_client.py`) for direct gRPC (with TLS CN
  override and proto compilation), the HTTPS `/grpc` bridge, legacy HTTP, and `/v1`.
- A sanitized knowledge layer: API corpus, verified examples, endpoint catalog, recipes,
  safety policies, and coverage status.

## Architecture

The server is layered. The entrypoint is `tools/axxon_mcp_server.py`; each capability
group is its own module (`tools/axxon_mcp_*.py`) and registers its tools on the FastMCP
server. Capability groups reuse the same client implementation class, but currently
construct separate client instances. There is no process-wide singleton or shared
session manager in this release.

| Layer | What it does |
| --- | --- |
| **Knowledge** | Search the API corpus, verified examples, endpoint catalog, and recipes with no server connection. |
| **Live read-only** | Connect to a server and inspect cameras, archives, detectors, events, layouts, maps, health, statistics, and bounded live subscriptions. |
| **Operator / config** | Create, modify, and delete configuration through separately registered, approval-gated tools and explicit plan/apply/verify/rollback stages. |
| **Export** | Plan/start/status/download/cleanup for owned snapshot exports, byte- and time-capped. |
| **Web / client** | Embeddable video-component helpers, bounded WebSocket-event probing, and a Client HTTP API preflight. |
| **Generator / partner** | Generate Python / Node integration skeletons (14 templates, each in both languages) and partner plugin scaffolds. |

Operator execution follows this boundary:

**plan → caller review and approval → explicit apply → verify → optional rollback**.

`execute_operator_workflow` is a plan-only convenience entrypoint. It never supplies its
own confirmation and never applies the plan. The caller must review the returned plan and
make a separate `apply_operator_plan` call with the required confirmation.

## Requirements

- Python 3.12
- A source checkout
- An Axxon One server and a least-privilege account only for explicitly enabled live tools

## Install

```bash
git clone https://github.com/jerrygergov/axxon-one-mcp.git
cd axxon-one-mcp
python3.12 -m pip install -r tools/requirements-mcp.txt
```

The default starts only the seven knowledge tools with no credentials:

```bash
python3.12 tools/axxon_mcp_server.py --transport stdio
```

## Run with Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config) and add the
server. This customer example explicitly opts into live reads and uses an HTTPS endpoint
with a dedicated least-privilege account:

```json
{
  "mcpServers": {
    "axxon-one": {
      "command": "python3.12",
      "args": [
        "/full/path/to/axxon-one-mcp/tools/axxon_mcp_server.py",
        "--enable-live"
      ],
      "env": {
        "AXXON_HOST": "vms.example.com",
        "AXXON_HTTP_URL": "https://vms.example.com",
        "AXXON_HTTP_PORT": "443",
        "AXXON_USERNAME": "axxon-mcp-reader",
        "AXXON_PASSWORD": "your-password"
      }
    }
  }
}
```

Restart Claude Desktop and ask things like *"list my cameras"* or *"what events fired in
the last hour?"*. Ask the assistant to call `list_capabilities` to see which explicit
flag enables another capability.

Any MCP client uses the same shape (a `command`, `args`, and `env`): Cursor, VS Code, and
frameworks like LangChain or the OpenAI Agents SDK all launch the stdio server the same way.

## Connection settings

Set these as environment variables (in the client `env` block, or exported in your shell).
Only enabled live groups need connection values. Use a dedicated account with only the
permissions required by those groups.

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `AXXON_HOST` | yes | — | Server IP or hostname |
| `AXXON_HTTP_URL` | for HTTP-backed live groups | `http://127.0.0.1:8000` | Use `https://<host>` for customer deployments. |
| `AXXON_USERNAME` | yes | — | Axxon One user |
| `AXXON_PASSWORD` | yes | — | password (kept in memory, never logged) |
| `AXXON_HTTP_PORT` | no | `8000` | Use the port assigned to the HTTPS endpoint. |
| `AXXON_GRPC_PORT` | no | `20109` | direct gRPC port |
| `AXXON_TLS_CN` | for gRPC | `Server` | gRPC certificate common name |
| `AXXON_CA` | for gRPC | — | path to the gRPC root CA |
| `AXXON_PROTO_DIR` | for gRPC | — | folder with the `.proto` files |

**Basic reads** (cameras, archives, events) work over the HTTPS `/grpc` bridge with host
and credentials. Plain HTTP is appropriate only in an explicitly accepted, isolated
trusted lab; it is not the recommended customer configuration.

**Full gRPC tools** (configuration, PTZ, media, etc.) also need the Axxon One `.proto`
files and the gRPC root CA. These are AxxonSoft material and are **not** in this repo —
request them from AxxonSoft technical support, then point the server at them:

```bash
export AXXON_PROTO_DIR=/path/to/axxon-proto-files
export AXXON_CA=/path/to/api.ngp.root-ca.crt
```

The server compiles the protos automatically on first use.

## Capability and mutation authorization

Capability flags control tool registration. Read groups such as `--enable-live`,
`--enable-view`, and `--enable-site-graph` may be combined so a deployment exposes only
the reads it needs. `--enable-all` is registration only: it registers the full surface,
does not authorize mutations, and never grants mutation approval.

A mutation requires all of the following independent controls:

1. The explicit capability group flag, such as `--enable-operator`.
2. The module's externally supplied `AXXON_<MODULE>_APPROVE=1` variable, with the exact
   value `1`; for example, operator apply uses `AXXON_OPERATOR_APPROVE=1`.
3. The per-call plan/confirmation check required by that tool.

Do not put approval variables into a shared base configuration. Add one to a narrowly
scoped deployment only after reviewing the tools in that group. `--read-only` is the
authoritative, broad compatibility profile: it registers all groups but leaves every
mutation-disabled even if the process inherits approval variables.

## Tools

Every group exposes a `*_connect_axxon_profile` tool (env-backed) plus the tools below.
The knowledge tools are always on; the rest connect to the live server.

**Knowledge (always on):** `search_api_docs`, `get_api_method`, `get_http_endpoint`,
`get_verified_example`, `explain_task_recipe`, `list_remaining_gaps`, `list_capabilities`

**live** — `connect_axxon_profile`, `list_cameras`, `list_archives`, `list_config_units`,
`list_detectors`, `list_appdata_detectors`, `find_event_suppliers`, `find_metadata_endpoints`,
`get_archive_intervals`, `subscribe_events_bounded`, `preflight_task`, `list_event_types`,
`list_detector_kinds`, `search_events`, `pull_metadata_bounded`

**view** — `live_view`, `snapshot_batch`, `archive_scrub`, `archive_frame`,
`archive_mjpeg_bounded`, `stream_health`, `get_cameras_by_components`, `batch_get_archives`,
`search_maps`

**view_objects** — `list_layouts`, `get_layout`, `layouts_on_view`, `list_layout_images`,
`download_layout_image`, `list_maps`, `get_map`, `get_map_image`, `get_markers`,
`list_map_providers`, `list_walls`

**site_graph** — `build_site_graph`

**metadata** — `list_vmda_sources`, `live_track_sample`, `vmda_query`

**heatmap** — `build_heatmap`, `build_events_heatmap`, `build_floor_heatmap`,
`execute_heatmap_query`, `execute_heatmap_query_typed`

**media** — `request_connection`, `request_qos`, `request_tunnel`, `stream_probe`,
`connect_endpoint`

**ptz** — `list_telemetry_sources`, `ptz_session_available`, `ptz_acquire_session`,
`ptz_keepalive_session`, `ptz_release_session`, `ptz_get_position`, `ptz_move`, `ptz_zoom`,
`ptz_focus`, `ptz_iris`, `ptz_point_move`, `ptz_absolute_move`, `ptz_get_position_normalized`,
`ptz_absolute_move_normalized`, `ptz_save_preset`, `ptz_configure_preset`, `ptz_get_tours`,
`ptz_get_tour_points`, `ptz_list_presets`, `ptz_set_preset`, `ptz_go_preset`,
`ptz_remove_preset`, `ptz_auxiliary_operations`

**alarms** — `list_active_alerts`, `get_active_alert`, `filter_active_alerts`,
`list_alarm_history`, `list_alarm_event_types`, `alarm_subscribe`, `raise_alert`,
`alarm_begin_review`, `alarm_continue_review`, `alarm_cancel_review`, `alarm_complete_review`,
`alarm_escalate`

**logic_alerts** — `batch_get_active_alerts`, `batch_filter_active_alerts`,
`batch_begin_alerts_review`, `batch_continue_alerts_review`, `batch_cancel_alerts_review`,
`batch_complete_alerts_review`, `batch_escalate_alerts`

**logic_control** — `list_launchable_macros`, `launch_macro`, `change_arm_state`,
`change_config`, `change_counters`, `counter_action`

**operator** — `list_operator_workflows`, `execute_operator_workflow`, `plan_operator_workflow`,
`apply_operator_plan`, `verify_operator_plan`, `rollback_operator_plan`

**config_change** — `list_similar_units`, `batch_get_factories`, `change_unit_property`,
`change_unit_property_stream`

**detector_archive** — `detector_kind_catalog`, `detector_parameter_schema`,
`detector_config_get`, `detector_visual_elements`, `metadata_schema_catalog`,
`metadata_sample_bounded`, `archive_policy_get`, `archive_management_status`,
`archive_volume_probe`, `analytics_fixture_report`

**detector_playbooks** — `list_detector_playbooks`, `detector_playbook_parameter_schema`,
`plan_detector_playbook`, `apply_detector_playbook_plan`, `verify_detector_playbook_plan`,
`rollback_detector_playbook_plan`, `detector_playbooks_audit_log`

**recognizer** — `list_recognizer_lists`, `get_recognizer_list`, `list_recognizer_items`

**recognizer_write** — `recognizer_change_lists`, `recognizer_change_lists_stream`,
`recognizer_change_items`, `recognizer_clear`

**bookmarks** — `bookmark_list`, `bookmark_get`

**bookmark_extras** — `update_bookmark`, `set_bookmark_exported_time`, `render_bookmark_track`

**bookmark_mutation** — `list_bookmark_mutation_workflows`, `plan_bookmark_mutation_workflow`,
`apply_bookmark_mutation_plan`, `verify_bookmark_mutation_plan`, `rollback_bookmark_mutation_plan`,
`read_bookmark_mutation_audit_log`

**export** — `export_plan_snapshot`, `export_start_snapshot`, `export_status`,
`export_download`, `export_stop`, `export_destroy`, `export_cleanup_owned`

**bulk_onboarding** — `bulk_onboarding_schema`, `bulk_onboarding_validate_manifest`,
`bulk_onboarding_plan`, `bulk_onboarding_apply_plan`, `bulk_onboarding_verify_plan`,
`bulk_onboarding_rollback_plan`, `bulk_onboarding_audit_log`

**devices_catalog** — `list_vendors`, `list_vendors_v2`, `list_devices`, `list_devices_v2`,
`get_device`

**discovery** — `discover_devices`, `discover_node_devices`

**videowall** — `videowall_list_walls`, `register_wall`, `change_wall`, `set_control_data`,
`unregister_wall`

**layout_manager** — `batch_get_layouts`, `layout_manager_layouts_on_view`, `update_layout_name`

**map_providers** — `configure_map_providers`, `get_map_provider`

**groups** — `list_groups`, `change_groups`, `set_objects_membership`

**control** — `list_unit_actions`, `list_unit_visualizations`, `download_unit_data`,
`perform_unit_action`, `vmda_cleanup`

**state_control** — `get_current_state`, `get_default_state`, `set_state`

**global_tracker** — `get_profile`

**scene_description** — `list_scene_description`

**web_api** — `embeddable_component_url`, `embeddable_component_commands`, `web_events_probe`,
`web_events_sample`, `web_client_parity_report`

**client_api** — `client_api_preflight`, `list_client_api_operations`

**admin** — `security_inventory`, `security_policy_summary`, `role_permissions`,
`current_user_security`, `license_status`, `time_status`, `system_health`,
`domain_event_subscribe`, `node_event_subscribe`, `update_event_subscription`,
`collect_config_backup`, `schedule_descriptor_get`

**admin_mutation** — `list_admin_mutation_workflows`, `plan_admin_mutation_workflow`,
`apply_admin_mutation_plan`, `verify_admin_mutation_plan`, `rollback_admin_mutation_plan`

**security_credentials** — `check_password`, `change_my_password`, `change_my_login`

**auth_sessions** — `authenticate`, `renew_session`, `close_session`

**license_reads** — `get_license_key`, `get_restrictions`

**audit** — `list_audit_event_kinds`, `audit_inject`

**settings** — `get_data_storage_settings`, `update_data_storage_settings`,
`get_bookmark_settings`, `update_bookmark_settings`, `get_gdpr_settings`, `update_gdpr_settings`

**gdpr_cleanup** — `layout_user_data_cleanup`, `map_user_data_cleanup`

**timezone** — `list_timezones`, `get_timezone`, `get_ntp`, `set_timezone`, `set_ntp`,
`change_timezones`

**server_settings** — `get_log_level`, `set_log_level`, `drop_logs`

**statistics** — `get_statistics`

**event_taxonomy** — `get_event_grouping_tags`

**misc_reads** — `acquire_dynamic_parameters`, `acquire_device_additional_data`, `probe_volume`,
`ping_node`, `get_generic_settings`, `save_generic_settings`, `remove_generic_settings`

**filesystem_browser** — `list_directory`, `get_file_info`, `get_space`

**archive_volume** — `list_volume_states`, `resize_volume`

**config_revisions** — `get_revision_info`, `collect_backup_probe`

**package_availability** — `check_package_availability`

**domain_topology** — `enumerate_nodes`

**shared_kv** — `list_records`, `get_records`, `get_records_stream`, `commit_record`

**generator** — `list_integration_templates`, `plan_integration`, `generate_integration`,
`verify_integration`

**partner** — `scaffold_plugin`, `plugin_lint`, `plugin_package`

**translator** — `assemble_recipe`, `validate_recipe`, `explain_recipe`, `resolve_device`,
`run_recipe`

## Startup profiles

```bash
# Secure default: exactly seven offline knowledge tools, no credentials
python3.12 tools/axxon_mcp_server.py --transport stdio

# Explicit live/read groups only
python3.12 tools/axxon_mcp_server.py \
  --enable-live --enable-view --enable-site-graph --transport stdio

# Broad compatibility surface with mutations authoritatively disabled
python3.12 tools/axxon_mcp_server.py --read-only --transport stdio

# Full registration only; does not approve any mutation
python3.12 tools/axxon_mcp_server.py --enable-all --transport stdio
```

Run `python3.12 tools/axxon_mcp_server.py --help` for the full flag list.

## Examples

Runnable standalone scripts that use the same client (`tools/examples/`):

- `camera_archive_status.py` — list cameras and their archive intervals
- `event_search_summary.py` — search and summarize events
- `metadata_tracker_stream.py` — bounded live object-track sampling
- `inventory_sync.py` — dump the full device inventory
- `http_grpc_vs_grpc.py` — compare the HTTP `/grpc` bridge vs direct gRPC

## Release checks

```bash
# Offline Python suite and real stdio startup profiles
python3.12 -m unittest discover -s tools/tests -v
python3.12 tools/verify_mcp_startup.py

# Corpus evidence and deterministic generated coverage
python3.12 tools/axxon_corpus_restamp.py --check
python3.12 tools/generate_coverage.py --check

# Committed customer references
python3.12 -m unittest discover -s customer-templates/python-reference -p 'test*.py' -v
npm --prefix customer-templates/node-reference ci
npm --prefix customer-templates/node-reference run build
npm --prefix customer-templates/node-reference test
```

These are the same offline checks run by root CI. They need no Axxon credentials, live
server, CA file, or private proto material.

## Layout

```
tools/
  axxon_mcp_server.py        MCP server entrypoint (--enable-* flags, --transport)
  axxon_mcp_*.py             feature modules (live reads, operator, ptz, alarms, web, …)
  axxon_api_client.py        gRPC/HTTP client (TLS-CN override, HTTP /grpc fallback, auth)
  examples/                  runnable standalone scripts
  templates/                 integration generator templates
  tests/                     offline unit tests
docs/api-audit/mcp-corpus/   the API corpus the server loads (methods, recipes, fixtures)
docs/COVERAGE.md             per-RPC live-verification status
customer-templates/          reference partner plugins (Python + Node)
```

## License

See [LICENSE](LICENSE). Axxon One, the Integration API, and the proto files are property
of AxxonSoft and are not redistributed here.
