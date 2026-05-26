# Axxon One Phase 5F-B Admin Mutation Smoke

- Started: `2026-05-26T19:22:04.034662+00:00`
- Finished: `2026-05-26T19:22:24.837642+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>`
- Approval env: `AXXON_ADMIN_MUTATION_APPROVE`

## Summary

- PASS: 5
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `security_user_role_lifecycle` | 5072 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_role_permissions_update` | 4008 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_policy_noop_probe` | 2094 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_ldap_temp_lifecycle` | 4196 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_tfa_temp_user_lifecycle` | 5420 | plan=planned apply=applied verify=verified rollback=rolled-back |
