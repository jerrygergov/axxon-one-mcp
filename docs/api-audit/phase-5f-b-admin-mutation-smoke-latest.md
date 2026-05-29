# Axxon One Phase 5F-B Admin Mutation Smoke

- Started: `2026-05-29T14:41:47.819523+00:00`
- Finished: `2026-05-29T14:42:13.214326+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>`
- Approval env: `AXXON_ADMIN_MUTATION_APPROVE`

## Summary

- PASS: 6
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `security_user_role_lifecycle` | 5359 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_role_permissions_update` | 4442 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_policy_noop_probe` | 2158 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_ldap_temp_lifecycle` | 4520 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_tfa_temp_user_lifecycle` | 5623 | plan=planned apply=applied verify=verified rollback=rolled-back |
| PASS | `security_production_role_edit_lifecycle` | 3281 | plan=planned apply=applied verify=verified rollback=rolled_back |
