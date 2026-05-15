# Axxon One Macro Smoke

- Started: `2026-05-07T11:51:14.517123+00:00`
- Finished: `2026-05-07T11:51:20.503279+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a disabled common `codex-temp-*` macro with no rules, changes it, optionally launches only that disabled empty macro, reads it back, then removes it.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `macro_lifecycle` | 3925 | macro=3ad19c14-886e-4f05-8f87-658435fa6594 added=codex-temp-macro-115116 modified=codex-temp-macro-updated-115118 launch_tested=True launch_keys=[] not_found=['3ad19c14-886e-4f05-8f87-658435fa6594'] |
