# Mutation Playbook: Detector Parameters

- PDF pages: 488-503.
- APIs involved: detector parameter reads and changes, GO track queries where configured.
- Fixture requirements: isolated detector, full read-before-write config snapshot, active VMDA endpoint.
- Preflight read snapshot: detector component, parameter shape, event/metadata baseline.
- Mutation request: change only one reversible parameter on a `codex-` detector fixture.
- Verification command: read parameter shape and detector health/events after change.
- Rollback request: write the saved parameter value back.
- Post-rollback verification: parameter shape/value matches preflight snapshot.
- Risk level: high.
- Approval requirement: explicit approval of detector id and exact parameter diff.
