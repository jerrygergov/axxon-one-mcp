# Mutation Playbook: External Events And Virtual Trigger

- PDF pages: 168.
- APIs involved: external event injection, virtual trigger endpoints.
- Fixture requirements: isolated test source, event name prefixed `codex-`, known event-history query window.
- Preflight read snapshot: count matching `codex-` events before injection.
- Mutation request: inject one test event with non-sensitive payload.
- Verification command: search event history for the `codex-` event in the target window.
- Rollback request: none for history insertion; rollback is cleanup-by-expiry or isolated fixture disposal.
- Post-rollback verification: document that event history side effects remain and are expected.
- Risk level: medium.
- Approval requirement: explicit approval acknowledging persistent event-history side effect.
