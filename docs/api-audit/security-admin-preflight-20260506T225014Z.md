# Axxon One Security Admin Preflight

- Started: `2026-05-06T22:50:14.110153+00:00`
- Finished: `2026-05-06T22:50:17.789194+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`
- Node: `Server`

Read-only preflight for security administration mutations. It does not create users, change passwords, edit roles, change permissions, start LDAP synchronization, or change policy/IP filters.

## Summary

- PASS: 3
- WARN: 2
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `security_inventory` | 375 | roles=4 users=35 ldap_servers=0 assignments=35 |
| WARN | `security_policies` | 518 | pwd_policies=1 ip_filters=0 trusted_ips=0 ldap_state=WARN |
| PASS | `security_permissions` | 644 | global_roles=1 object_items=36 group_items=1 macros=16 |
| PASS | `restricted_config` | 124 | keys=6 |
| WARN | `approval_only_mutations` | 0 | SecurityService.ChangeConfig, SecurityService.SetGlobalPermissions, SecurityService.SetObjectPermissions, SecurityService.SetGroupsPermissions, SecurityService.SetMacrosPermissions, SecurityService.StartLDAPSynchronizati |
