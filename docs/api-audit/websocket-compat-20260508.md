# Axxon One WebSocket Compatibility Probe

- Date: `2026-05-08`
- Target: demo stand `<demo-host>`
- Endpoint: `/events`
- Scope: bounded compatibility check for Integration APIs 3.0 pages 184-189.

## Summary

- The Web server accepts the WebSocket upgrade and returns HTTP `101 Switching Protocols`.
- After upgrade, the server immediately returns an empty WebSocket receive / close frame.
- The behavior is the same with `schema=proto` and without a schema query.
- The behavior is the same with credentials in the URL and with an explicit `Authorization: Basic` header.
- The behavior is the same with `include` camera-source commands, `include` detector-subject commands, and `track` device commands.
- Origin and WebSocket protocol header variants did not change the result.
- gRPC `DomainNotifier.PullEvents` remains the verified subscription path on this stand.

## Variants

| Variant | Result |
| --- | --- |
| `ws://user:password@host/events?schema=proto` + camera `include` | HTTP 101, then close/empty receive |
| `ws://user:password@host/events` + camera `include` | HTTP 101, then close/empty receive |
| `Authorization: Basic ...` + `schema=proto` + camera `include` | HTTP 101, then close/empty receive |
| `Authorization: Basic ...` + no schema + camera `include` | HTTP 101, then close/empty receive |
| `include` detector subject | HTTP 101, then close/empty receive |
| `track` camera device | HTTP 101, then close/empty receive |
| Explicit `Origin` header variants | HTTP 101, then close/empty receive |

## Current Conclusion

The documented WebSocket command shapes are implemented in the smoke tool, but this demo Web server closes the `/events` socket immediately after upgrade. Keep the HTTP WebSocket row as `fixture-needed` until a Web server instance with working `/events` streaming is available or product configuration explains why this endpoint is closing.
