# Axxon One Security Mutation Smoke

- Started: `2026-05-07T11:46:55.191907+00:00`
- Finished: `2026-05-07T11:47:02.969276+00:00`
- gRPC target: `<demo-host>:20109`

Controlled smoke for temporary `codex-*` security records. It does not store generated passwords in the report.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `security_user_role_lifecycle` | 6648 | role=519cc051-eaa1-4c34-9e11-fc39afbbcda5 user=ab871b1d-7cb8-4bdd-9d24-be72beb7b4b6 assigned=1 restored_roles=True restored_users=True |
