# Axxon One Phase 5F Admin Smoke

- Started: `2026-05-29T14:02:30.813527+00:00`
- Finished: `2026-05-29T14:02:58.954481+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>`
- Node notifier: `True`

## Summary

- PASS: 10
- WARN: 1
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `connect` | 0 | keys=['connected', 'mode', 'profile', 'profile_name'] |
| PASS | `security_inventory` | 1974 | tool=security_inventory keys=['ldap_servers', 'roles', 'status', 'tool', 'users'] |
| PASS | `security_policy_summary` | 818 | tool=security_policy_summary keys=['cloud_public_key_present', 'ip_filter_count', 'ldap', 'password_policy_count', 'status', 'system_integrity_modes_count', 'tool', 'trusted_ip_count'] |
| PASS | `role_permissions` | 3676 | tool=role_permissions keys=['global', 'groups', 'macros', 'objects', 'role_id', 'status', 'tool'] |
| PASS | `current_user_security` | 382 | tool=current_user_security keys=['all_roles_count', 'all_users_count', 'current_roles', 'current_user', 'password_policy_count', 'status', 'system_integrity_modes_count', 'tool'] |
| PASS | `license_status` | 2604 | tool=license_status keys=['applied_limit', 'domain', 'global_restrictions', 'host_info', 'key_info', 'launch', 'node_restrictions', 'status', 'tool'] |
| PASS | `time_status` | 1618 | tool=time_status keys=['available_zones', 'current_zone', 'ntp', 'status', 'tool'] |
| PASS | `system_health` | 6643 | tool=system_health keys=['archive', 'license', 'security', 'session', 'status', 'time', 'tool'] |
| PASS | `domain_event_subscribe` | 5205 | tool=domain_event_subscribe keys=['caps', 'count', 'detailed', 'disconnect_clean', 'event_types', 'events', 'notifier', 'service', 'status', 'stream_error', 'stream_idle', 'subjects', 'tool'] |
| PASS | `node_event_subscribe` | 5214 | tool=node_event_subscribe keys=['caps', 'count', 'detailed', 'disconnect_clean', 'event_types', 'events', 'notifier', 'service', 'status', 'stream_error', 'stream_idle', 'subjects', 'tool'] |
| WARN | `schedule_descriptor_get` | 0 | Could not resolve descriptor with schedule-like fields; provide an isolated config fixture. |
