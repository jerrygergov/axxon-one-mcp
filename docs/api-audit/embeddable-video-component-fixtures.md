# Embeddable Video Component Fixtures

The embeddable video component surfaces in `Integration APIs 3.0.pdf` pages 525-528 require a browser-renderable host page and a server Web component fixture. Do not treat media endpoint reachability alone as component verification.

## Required Fixture

- A browser-renderable host page that loads the component.
- Web server access for the same Axxon target.
- A known camera access point with permission to render live video.
- Documented auth behavior for the component: Basic auth, session auth, reverse proxy auth, or another site-specific approach.
- A screenshot or browser automation check proving the component renders non-empty video or an explicit error state.

## Optional Smoke Commands

Use these only after the host page exists:

```bash
curl -s 'http://127.0.0.1:8000/'
```

Then use the in-app browser or Playwright to verify:

- The component script loads.
- Auth succeeds or fails with a documented status.
- The camera AP is accepted.
- The rendered area is non-empty or returns a clear permission/media error.

## Current Status

- Status: `fixture-needed`.
- Risk: `external-client`.
- Reason: the demo stand has server API access, but no checked-in component host page or browser fixture. The focused preflight in `external-client-preflight-latest.md` fetched `http://<demo-host>:80/` successfully with HTTP 200 and 955 bytes, but the HTML did not contain component, video, or embed signatures.

## Verification Rules

- Do not persist credentials, signed URLs, or session tokens from the browser.
- Store screenshots only if they do not expose credentials, license keys, full plates, or private operator data.
- Record camera AP, HTTP status, component load status, and high-level render result.
