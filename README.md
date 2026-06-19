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

- **327 tools** across **53 capability groups**, all on by default.
- One shared client (`tools/axxon_api_client.py`) that talks to the server over direct
  gRPC (with TLS CN override and proto compilation) or the HTTP `/grpc` bridge, plus
  legacy HTTP and `/v1`. Basic reads work over HTTP with just host + credentials; full
  gRPC tools also need the Axxon `.proto` files and the gRPC root CA.
- A knowledge layer (API corpus, verified examples, recipes) that works with **no server
  connection at all**.

## Architecture

The server is layered. The entrypoint is `tools/axxon_mcp_server.py`; each capability
group is its own module (`tools/axxon_mcp_*.py`) and registers its tools on the FastMCP
server.

| Layer | What it does |
| --- | --- |
| **Knowledge** | Search the API corpus, verified examples, endpoint catalog, and recipes with no server connection. |
| **Live read-only** | Connect to a server and inspect cameras, archives, detectors, events, layouts, maps, health, statistics, and bounded live subscriptions. |
| **Operator / config** | Create, modify, and delete configuration (cameras, detectors, layouts, macros, settings, PTZ, alarms, videowall). Reversible workflows run in one call via `execute`; irreversible ones keep the plan → apply → verify → rollback flow. |
| **Export** | Plan/start/status/download/cleanup for owned snapshot exports, byte- and time-capped. |
| **Web / client** | Embeddable video-component helpers, bounded WebSocket-event probing, and a Client HTTP API preflight. |
| **Generator / partner** | Generate Python / Node integration skeletons (14 templates, each in both languages) and partner plugin scaffolds. |

Reversible workflows (create camera, archive, macro, wall) run in a single `execute` call:
the assistant supplies the confirmation token from the plan automatically. Irreversible
workflows (deletes, property pushes, event injection) return `needs_two_step`, so the
assistant falls back to `plan` → `apply` and a destructive call takes a deliberate second
step.

## Requirements

- Python 3.12
- `pip install -r tools/requirements-mcp.txt`
- An Axxon One server and its credentials (for the live tools).

## Install

```bash
git clone https://github.com/jerrygergov/axxon-one-mcp.git
cd axxon-one-mcp
pip install -r tools/requirements-mcp.txt
```

That alone runs the **knowledge layer** (API search, verified examples) with no server:

```bash
python tools/axxon_mcp_server.py --transport stdio
```

## Run with Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config) and add the
server with your Axxon One connection details. **No flags** — running with no flags
enables every group:

```json
{
  "mcpServers": {
    "axxon-one": {
      "command": "python",
      "args": ["/full/path/to/axxon-one-mcp/tools/axxon_mcp_server.py"],
      "env": {
        "AXXON_HOST": "192.168.1.50",
        "AXXON_HTTP_URL": "http://192.168.1.50",
        "AXXON_HTTP_PORT": "80",
        "AXXON_USERNAME": "root",
        "AXXON_PASSWORD": "your-password"
      }
    }
  }
}
```

Restart Claude Desktop and ask things like *"list my cameras"*, *"what events fired in
the last hour?"*, *"add a virtual camera named Lobby-Cam"*, or *"build me the site graph"*.
Ask the assistant to call `list_capabilities` to see everything the server can do.

Any MCP client uses the same shape (a `command`, `args`, and `env`): Cursor, VS Code, and
frameworks like LangChain or the OpenAI Agents SDK all launch the stdio server the same way.

## Connection settings

Set these as environment variables (in the client `env` block, or exported in your shell).
Only host, URL, username, and password are required.

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `AXXON_HOST` | yes | — | Server IP or hostname |
| `AXXON_HTTP_URL` | yes | `http://127.0.0.1:8000` | `http://<host>` (or `https://`) |
| `AXXON_USERNAME` | yes | — | Axxon One user |
| `AXXON_PASSWORD` | yes | — | password (kept in memory, never logged) |
| `AXXON_HTTP_PORT` | no | `8000` | set to `80` for a standard install |
| `AXXON_GRPC_PORT` | no | `20109` | direct gRPC port |
| `AXXON_TLS_CN` | for gRPC | `Server` | gRPC certificate common name |
| `AXXON_CA` | for gRPC | — | path to the gRPC root CA |
| `AXXON_PROTO_DIR` | for gRPC | — | folder with the `.proto` files |

**Basic reads** (cameras, archives, events) work over the HTTP `/grpc` bridge with just
host + credentials.

**Full gRPC tools** (configuration, PTZ, media, etc.) also need the Axxon One `.proto`
files and the gRPC root CA. These are AxxonSoft material and are **not** in this repo —
request them from AxxonSoft technical support, then point the server at them:

```bash
export AXXON_PROTO_DIR=/path/to/axxon-proto-files
export AXXON_CA=/path/to/api.ngp.root-ca.crt
```

The server compiles the protos automatically on first use.

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

## Restricting what's on (optional)

Running with no flags enables everything. To restrict:

```bash
# Reads only — mutating tools disabled
python tools/axxon_mcp_server.py --read-only --transport stdio

# Only specific groups
python tools/axxon_mcp_server.py --enable-live --enable-ptz --transport stdio
```

Run `python tools/axxon_mcp_server.py --help` for the full flag list.

## Examples

Runnable standalone scripts that use the same client (`tools/examples/`):

- `camera_archive_status.py` — list cameras and their archive intervals
- `event_search_summary.py` — search and summarize events
- `metadata_tracker_stream.py` — bounded live object-track sampling
- `inventory_sync.py` — dump the full device inventory
- `http_grpc_vs_grpc.py` — compare the HTTP `/grpc` bridge vs direct gRPC

## Tests

```bash
python3.12 -m unittest discover -s tools/tests     # offline, no server needed
```

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
