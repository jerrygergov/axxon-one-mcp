# Axxon One External Client Preflight

- Started: `2026-05-12T09:00:47.280522+00:00`
- Finished: `2026-05-12T09:00:56.008095+00:00`
- HTTP target: `http://<demo-host>:80`
- Client HTTP port: `8888`

Read-only preflight for Axxon Client HTTP and embeddable component fixtures. It does not switch layouts, alter displays, change modes, render browser screenshots, or persist browser/session artifacts.

## Summary

- PASS: 0
- WARN: 3
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| WARN | `client_http_targets` | 871 | reachable=0 gap=no Axxon Client HTTP API target reachable |
| WARN | `embeddable_host` | 7855 | http=200 bytes=955 component=False video=False gap=web root does not look like an embeddable component host |
| WARN | `approval_only_operations` | 0 | ClientHTTP.SwitchLayout, ClientHTTP.AddCameraToDisplay, ClientHTTP.RemoveCameraFromDisplay, ClientHTTP.SetArchiveMode, ClientHTTP.SetSearchMode, ClientHTTP.SetImmersionMode, EmbeddableComponent.BrowserRender |
