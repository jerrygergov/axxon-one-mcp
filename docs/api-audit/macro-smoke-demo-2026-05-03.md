# Axxon One Macro Smoke

- Started: `2026-05-02T22:23:02.693705+00:00`
- Finished: `2026-05-02T22:23:05.545108+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a disabled common `codex-temp-*` macro with no rules, changes it, reads it back, then removes it. `LaunchMacro` is intentionally not called.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `macro_lifecycle` | 2295 | macro=c06d793b-67d4-4bc4-bf9a-1120394dbe5c added=codex-temp-macro-222303 modified=codex-temp-macro-updated-222304 launch_tested=False not_found=['c06d793b-67d4-4bc4-bf9a-1120394dbe5c'] |
