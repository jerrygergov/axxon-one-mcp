# Client HTTP API Fixtures

The Client HTTP API surfaces in `Integration APIs 3.0.pdf` pages 189-205 require an Axxon Client process with its HTTP API enabled. Do not mark these examples verified from the server-only demo stand.

## Required Fixture

- A reachable Axxon Client HTTP API target, usually `http://127.0.0.1:8888`.
- At least one active display id.
- At least one layout id visible to the logged-in operator.
- Permission to switch layouts, add and remove cameras from a display, switch archive mode, switch search mode, and switch immersion mode.
- A known camera access point that is safe to display.
- A rollback step that restores the previous layout or display state.

## Optional Smoke Commands

Use these only when a Client fixture exists:

```bash
nc -zv 127.0.0.1 8888
curl -s 'http://127.0.0.1:8888/GetDisplays'
```

## Current Status

- Status: `fixture-needed`.
- Risk: `external-client`.
- Reason: the current demo stand verifies server-side layouts and maps, but does not expose an Axxon Client HTTP API endpoint. The focused preflight in `external-client-preflight-latest.md` checked `127.0.0.1:8888` and `<demo-host>:8888`; both refused TCP connections.

## Verification Rules

- Record display and layout counts, not operator-private workspace details.
- Do not leave the operator display in a modified state.
- Do not run layout switching, camera add/remove, archive/search/immersion mode changes, or videowall control without an explicit rollback plan.
