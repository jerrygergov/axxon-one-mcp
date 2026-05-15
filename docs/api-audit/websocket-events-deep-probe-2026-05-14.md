# WebSocket `/events` Deep Probe

Date: 2026-05-14
Target: demo stand `<demo-host>:80`
Endpoint: `ws://<demo-host>:80/events`

## Method

Raw socket WebSocket handshake (plus a proper `websocket-client` follow-up) with `Basic root:root` Authorization, full RFC 6455 headers, and the three subscription command shapes documented in `axxon_subscription_smoke.py`:

1. `{"include": [<event_supplier_ap>], "exclude": []}`
2. `{"subjects": [<event_supplier_ap>]}`
3. `{"track": [<device_ap>]}`

## Result

| Stage | Behavior |
|---|---|
| Plain `GET /events` over HTTP | HTTP 400 (no Upgrade header) — expected. |
| Proper WebSocket handshake with `Upgrade: websocket` + valid `Sec-WebSocket-Key` | HTTP 101 Switching Protocols + correct `Sec-WebSocket-Accept`. CSP headers present. |
| Send subscription command frame | Server responds with a single empty frame (length 0) then closes the connection. |
| Subsequent send attempts | `socket is already closed`. |

Same behavior across all three command shapes. Auth is accepted; the upgrade succeeds. The server closes after receiving any application-layer frame, before delivering events.

## Verdict

This is consistent with prior observations in `subscription-smoke-latest.md` and `websocket-compat-20260508.md`. It is a server-side issue on this Axxon One build, **not** a fixture gap solvable by the client. Direct gRPC `DomainNotifier.PullEvents` is the documented, working alternative and is already covered as `verified`.

Row classification stays **fixture-needed** with the precise blocker:

> Demo Web server closes the WebSocket immediately after a subscription frame across all auth/schema/Origin/include/subjects/track variants. Verifiable only on an Axxon Web server build where `/events` honors application-layer subscription frames.

## Reproducer

```python
import base64, websocket
ws = websocket.WebSocket()
ws.connect(
    "ws://<demo-host>:80/events",
    header=[
        f"Authorization: Basic {base64.b64encode(b'root:root').decode()}",
        "Origin: http://<demo-host>",
    ],
    timeout=15,
)
ws.send('{"include":["hosts/Server/AppDataDetector.6/EventSupplier"],"exclude":[]}')
# -> single empty frame, then connection closed by server.
```

## Notes

- No password is stored in this report; `root:root` matches the demo-stand's documented default credentials and the PDF examples.
- Network conditions verified on the same probe pass: gRPC `20109` reachable, HTTP `80` reachable, direct gRPC `DomainNotifier.PullEvents` working.
