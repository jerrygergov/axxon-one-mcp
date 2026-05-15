# Axxon One Security Mutation Smoke

- Started: `2026-05-12T18:55:00.207960+00:00`
- Finished: `2026-05-12T18:55:19.350330+00:00`
- gRPC target: `<demo-host>:20109`

Controlled smoke for temporary `codex-*` security records. It does not store generated passwords in the report.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `security_user_role_lifecycle` | 17697 | role=8452ab6f-e79e-4296-9e8f-23b985d32633 user=1e8caecf-26fb-4540-ad6c-6fff6ed25312 assigned=1 restored_roles=True restored_users=True perms=True policy_noop=True ldap=True tfa=True |
