# Axxon One Layout Mutation Smoke

- Started: `2026-05-07T11:41:27.599847+00:00`
- Finished: `2026-05-07T11:41:36.141641+00:00`
- gRPC target: `<demo-host>:20109`

Controlled smoke for a temporary `codex-layout-*` layout. It creates, modifies, calls `LayoutsOnView` for the temporary layout, removes it, and verifies rollback.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `layout_mutation_lifecycle` | 5772 | layout=codex-layout-0c735714-9ec0-4dbd-b840-0d90e801b671 before=20 after=20 removed_not_found=1 current_unchanged=True |
