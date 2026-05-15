# Mutation Playbook: Device Templates

- PDF pages: 482-487.
- APIs involved: template create/edit/assign/delete.
- Fixture requirements: template id prefixed `codex-`, isolated virtual device or no assignment.
- Preflight read snapshot: list templates and template assignments for the target unit.
- Mutation request: create a minimal `codex-` template; assignment only on an isolated unit.
- Verification command: list and batch-get the template.
- Rollback request: unassign if assigned, then remove the template.
- Post-rollback verification: batch-get returns not found and assignments return to baseline.
- Risk level: medium.
- Approval requirement: explicit unit id approval before assignment.
