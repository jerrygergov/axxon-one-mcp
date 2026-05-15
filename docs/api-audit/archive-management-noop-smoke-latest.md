# Axxon One Archive Management No-Op Smoke

- Started: `2026-05-12T08:32:23.737080+00:00`
- Finished: `2026-05-12T08:32:27.761140+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`
- Archive AP: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`

Uses a `codex-nonexistent-*` volume id to verify archive-management method dispatch without formatting or reindexing a real volume.

## Summary

- PASS: 5
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `pre_fake_volume_state` | 202 | keys=['fake_not_found', 'fake_volume_id_len', 'not_found_count', 'volume_state_count'] |
| PASS | `format_fake_volume` | 205 | keys=['result_count', 'status_code'] |
| PASS | `reindex_fake_volume` | 198 | keys=['failed_volume_count', 'response_keys'] |
| PASS | `cancel_reindex_fake_volume` | 203 | keys=['response_keys'] |
| PASS | `post_fake_volume_state` | 201 | keys=['fake_not_found', 'fake_volume_id_len', 'not_found_count', 'volume_state_count'] |
