# Pre-existing Tools Live Audit

| Verdict | Count |
|---------|-------|
| OK | 59 |
| EMPTY | 15 |
| CAP | 0 |
| DRIFT | 0 |
| FAIL | 0 |

## Results

| Group | Tool | Verdict | Detail |
|-------|------|---------|--------|
| live | list_cameras | OK | count=42 |
| live | list_archives | OK | count=20 |
| live | list_detectors | OK | count=42 |
| live | search_events | OK | count=20 |
| metadata | list_vmda_sources | OK | count=15 |
| metadata | vmda_query | EMPTY | message=<_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Internal errors occurred: tracking-id:mUR62pVGROu@Server"
	debug_error_string = "UNKNOWN:Error received from peer ipv4:<demo-host>:20109 {grp |
| alarms | list_active_alerts | EMPTY | count=0 |
| alarms | list_alarm_history | EMPTY | count=0 |
| alarms | list_alarm_event_types | OK | count=2 |
| alarms_mutate | raise_alert | OK | gate=refused obs=refused |
| alarms_mutate | alarm_begin_review | OK | gate=refused obs=refused |
| logic_alerts | batch_get_active_alerts | EMPTY | ok |
| logic_alerts | batch_filter_active_alerts | EMPTY | ok |
| logic_alerts_mutate | batch_begin_alerts_review | OK | gate=refused obs=disabled |
| ptz | list_telemetry_sources | OK | count=3 |
| heatmap | build_heatmap | EMPTY | message=<_InactiveRpcError of RPC that terminated with: |
| heatmap | build_events_heatmap | OK | result=True |
| media | request_connection | EMPTY | message=<_InactiveRpcError of RPC that terminated with: |
| media | request_tunnel | OK | ok |
| recognizer | list_recognizer_lists | EMPTY | count=0 |
| discovery | discover_node_devices | OK | count=3 |
| admin | security_inventory | OK | ok |
| admin | system_health | OK | ok |
| admin | time_status | OK | ok |
| admin | license_status | OK | ok |
| admin | current_user_security | OK | ok |
| admin | role_permissions | OK | ok |
| license_reads | get_license_key | OK | key_present=True |
| license_reads | get_restrictions | OK | ok |
| misc_reads | ping_node | OK | responses=1 |
| misc_reads | get_generic_settings | EMPTY | message=<_InactiveRpcError of RPC that terminated with: |
| misc_reads_mutate | save_generic_settings | OK | gate=refused obs=disabled |
| bookmarks | bookmark_list | EMPTY | count=0 |
| bookmarks_mutate | apply(bookmark_lifecycle) | OK | gate=refused obs=rejected |
| layout_manager | batch_get_layouts | EMPTY | item_count=0 |
| layout_manager_mutate | update_layout_name | OK | gate=refused obs=disabled |
| map_providers | get_map_provider | EMPTY | message=<_InactiveRpcError of RPC that terminated with: |
| map_providers_mutate | configure_map_providers | OK | gate=refused obs=disabled |
| groups | list_groups | OK | count=5 |
| groups_mutate | change_groups | OK | gate=refused obs=disabled |
| timezone | list_timezones | OK | count=1 |
| timezone | get_timezone | OK | ok |
| timezone | get_ntp | EMPTY | ok |
| timezone_mutate | set_timezone | OK | gate=refused obs=disabled |
| settings | get_data_storage_settings | OK | ok |
| settings | get_bookmark_settings | OK | ok |
| settings | get_gdpr_settings | OK | ok |
| settings_mutate | update_data_storage_settings | OK | gate=refused obs=disabled |
| detector_archive | detector_kind_catalog | OK | count=8 |
| detector_archive | archive_management_status | OK | ok |
| detector_archive | analytics_fixture_report | OK | ok |
| auth_sessions | authenticate | OK | ok |
| auth_sessions | renew_session | OK | ok |
| auth_sessions_mutate | close_session | OK | gate=refused obs=disabled |
| server_settings | get_log_level | OK | ok |
| server_settings_mutate | set_log_level | OK | gate=refused obs=disabled |
| server_settings_mutate | drop_logs | OK | gate=refused obs=disabled |
| audit | list_audit_event_kinds | OK | count=6 |
| audit_mutate | audit_inject | OK | gate=refused obs=disabled |
| config_change | list_similar_units | OK | ok |
| config_change | batch_get_factories | OK | item_count=1 |
| config_change_mutate | change_unit_property | OK | gate=refused obs=disabled |
| archive_volume | list_volume_states | EMPTY | message=<_InactiveRpcError of RPC that terminated with: |
| archive_volume_mutate | resize_volume | OK | gate=refused obs=disabled |
| gdpr_cleanup_mutate | layout_user_data_cleanup | OK | gate=refused obs=disabled |
| gdpr_cleanup_mutate | map_user_data_cleanup | OK | gate=refused obs=disabled |
| recognizer_write_mutate | recognizer_change_lists | OK | gate=refused obs=disabled |
| recognizer_write_mutate | recognizer_clear | OK | gate=refused obs=disabled |
| videowall | list_walls | OK | count=1 |
| videowall_mutate | register_wall | OK | gate=refused obs=disabled |
| security_credentials | check_password | EMPTY | message=<_InactiveRpcError of RPC that terminated with: |
| security_credentials_mutate | change_my_password | OK | gate=refused obs=disabled |
| generator | list_templates | OK | count=14 |
| generator | generate(grpc_consumer) | OK | files=['main.py', 'README.md', 'requirements.txt'] |

Host: `<demo-host>`  User: `<demo-user>`