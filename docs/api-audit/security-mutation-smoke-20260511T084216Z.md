# Axxon One Security Mutation Smoke

- Started: `2026-05-11T08:42:16.845645+00:00`
- Finished: `2026-05-11T08:42:42.436392+00:00`
- gRPC target: `<demo-host>:20109`

Controlled smoke for temporary `codex-*` security records. It does not store generated passwords in the report.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `security_user_role_lifecycle` | 17326 | role=c07190ec-ebd3-4fed-bc83-f42641cdf553 user=9ec55e3a-cf7d-493b-8ad5-8451f680eb45 assigned=1 restored_roles=True restored_users=True perms=True policy_noop=True ldap=True |
