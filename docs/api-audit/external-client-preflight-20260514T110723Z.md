# Axxon One External Client Preflight

- Started: `2026-05-14T11:07:23.871865+00:00`
- Finished: `2026-05-14T11:07:36.154694+00:00`
- HTTP target: `http://<demo-host>:80`
- Client HTTP port: `8888`

Read-only preflight for Axxon Client HTTP and embeddable component fixtures. It does not switch layouts, alter displays, change modes, render browser screenshots, or persist browser/session artifacts.

## Summary

- PASS: 0
- WARN: 2
- FAIL: 1

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| WARN | `client_http_targets` | 1902 | reachable=0 gap=no Axxon Client HTTP API target reachable |
| FAIL | `embeddable_host` | 10379 | 'size' |
| WARN | `approval_only_operations` | 0 | ClientHTTP.SwitchLayout, ClientHTTP.AddCameraToDisplay, ClientHTTP.RemoveCameraFromDisplay, ClientHTTP.SetArchiveMode, ClientHTTP.SetSearchMode, ClientHTTP.SetImmersionMode, EmbeddableComponent.BrowserRender |
