# Axxon One External Client Preflight

- Started: `2026-05-12T12:32:38.512295+00:00`
- Finished: `2026-05-12T12:32:39.674208+00:00`
- HTTP target: `http://<demo-host>:80`
- Client HTTP port: `8888`

Read-only preflight for Axxon Client HTTP and embeddable component fixtures. It does not switch layouts, alter displays, change modes, render browser screenshots, or persist browser/session artifacts.

## Summary

- PASS: 1
- WARN: 2
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| WARN | `client_http_targets` | 226 | reachable=0 gap=no Axxon Client HTTP API target reachable |
| PASS | `embeddable_host` | 935 | path=/embedded.html http=200 bytes=856 component=True video=True embed=True gap= |
| WARN | `approval_only_operations` | 0 | ClientHTTP.SwitchLayout, ClientHTTP.AddCameraToDisplay, ClientHTTP.RemoveCameraFromDisplay, ClientHTTP.SetArchiveMode, ClientHTTP.SetSearchMode, ClientHTTP.SetImmersionMode, EmbeddableComponent.BrowserRender |
