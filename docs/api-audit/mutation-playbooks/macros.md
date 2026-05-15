# Mutation Playbook: Macros

- PDF pages: 181-183, 213-217, 390-395.
- APIs involved: macro create/change/remove and launch.
- Fixture requirements: temporary macro id/name prefixed `codex-`; action body reviewed for no operational side effects.
- Preflight read snapshot: list macros and macro config shape.
- Mutation request: create or change only the `codex-` macro.
- Verification command: batch-get the macro by id and compare shape/etag.
- Rollback request: remove the `codex-` macro.
- Post-rollback verification: list/batch-get and verify absence.
- Risk level: high for launch, medium for create/change/remove.
- Approval requirement: explicit approval of macro body before any launch.
