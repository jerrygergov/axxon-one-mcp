# Phase 5D - Layouts / Maps / Videowalls Live Smoke Evidence

**Date:** 2026-05-18
**Stand:** `<demo-host>` (sanitized)
**Auth mode:** Bearer (HTTP `/grpc`)
**Caps:** list limit = 200; map image bytes = 4 MiB; map image tool returns metadata only.

## Coverage

| Tool / Workflow | Status | Notes |
| --- | --- | --- |
| `view_objects_connect_axxon_profile` | verified | Bearer auth ok against `<demo-host>` |
| `list_layouts` | verified | `VIEW_MODE_ONLY_META`; 10 layouts returned in smoke |
| `get_layout` | verified | `BatchGetLayouts` returned a full layout body |
| `layouts_on_view` | offline-tested only | Dispatch shape covered; not run in live smoke because it pushes client view state |
| `list_layout_images` | live fixture-gap; offline-tested | All listed demo layouts returned unreadable/not-found for `ListLayoutImages`; tool reports `status: gap` |
| `list_maps` | verified | 5 maps returned in smoke |
| `get_map` | verified | `BatchGetMaps` one-item path |
| `get_map_image` | verified | Nested `image` response parsed; 161,057 bytes reported, not echoed |
| `get_markers` | verified | Live `markers` map keyed by component/access point normalized |
| `list_map_providers` | verified | 2 providers returned: Bitmap/vector image and Google Map |
| `list_walls` | verified | Stream/multipart response flattened; 1 existing wall on stand |
| `temp_wall` / `videowall_register` | verified | Synthetic wall registered; cookie redacted |
| `videowall_change` | verified | Uses register `seq_number`; returned next sequence |
| `videowall_set_control_data` | verified | Uses `ChangeWall.new_seq_number`; returned next sequence |
| `videowall_unregister` | verified | Rollback unregistered synthetic wall with no failures |
| `create_map` / `delete_map` | verified | Synthetic raster map created and removed |
| `update_markers` | verified | Marker update applied on the synthetic map |
| `update_map` | offline-tested only | Live update skipped to keep smoke to create/update-marker/delete round-trip |
| `update_layout` / `delete_layout` | offline-tested only | Live mutation not run on shared demo layouts |

Offline tests: `tools/tests/test_axxon_mcp_view_objects.py`, `tools/tests/test_axxon_api_client_view_objects.py`, `tools/tests/test_axxon_mcp_operator.py`, `tools/tests/test_axxon_mcp_server.py`, and `tools/tests/test_axxon_view_objects_smoke.py`.

Full repo suite after this task:

```text
Ran 281 tests in 0.152s
OK
```

## Sanitized Live Smoke Output

Read smoke summary from `tools/axxon_view_objects_smoke.py`:

```json
{
  "host": "<demo-host>",
  "reads": {
    "list_layouts_meta": {"status": "ok", "count": 10},
    "get_layout": {"status": "ok"},
    "list_layout_images": {"status": "gap"},
    "list_maps": {"status": "ok", "count": 5},
    "get_map": {"status": "ok"},
    "get_map_image": {
      "status": "ok",
      "bytes_returned": 161057,
      "truncated": false,
      "content_type": "PNG",
      "applied_cap": 4194304
    },
    "get_markers": {"status": "ok", "count": 4},
    "list_map_providers": {"status": "ok", "count": 2},
    "list_walls": {"status": "ok", "count": 1}
  }
}
```

Mutation smoke summary from `tools/axxon_view_objects_smoke.py --mutation`:

```json
{
  "host": "<demo-host>",
  "mutation_wall": {
    "apply": {
      "status": "applied",
      "created_uids": [
        "709ea161-44cd-4870-afc0-922e8fe77282|hosts/Server/VideowallCoordinator.0/Coordinator"
      ],
      "wall_seq_numbers": [0]
    },
    "change_apply": {
      "status": "applied",
      "created_uids": [],
      "wall_seq_numbers": [1]
    },
    "control_apply": {
      "status": "applied",
      "created_uids": [],
      "wall_seq_numbers": [2]
    },
    "rollback": {
      "status": "rolled_back",
      "removed_uids": [
        "709ea161-44cd-4870-afc0-922e8fe77282|hosts/Server/VideowallCoordinator.0/Coordinator"
      ],
      "failed": []
    }
  },
  "mutation_map": {
    "apply": {
      "status": "applied",
      "created_uids": ["d3f3b052-fd7f-49f6-a41e-b2dddd1edf03"]
    },
    "rollback": {
      "status": "rolled_back",
      "removed_uids": ["d3f3b052-fd7f-49f6-a41e-b2dddd1edf03"],
      "failed": []
    }
  },
  "mutation_markers": {
    "apply": {
      "status": "applied",
      "created_uids": []
    }
  },
  "audit_log_count": 12
}
```

## Observations

- `MapService.ChangeMaps` live JSON-over-`/grpc` uses `{created: [...]}`, `{updated: [...]}`, and `{removed: [...]}`. The earlier draft shape `{added: [...]}` / `{changed: [...]}` returned HTTP 500.
- `MapService.UpdateMarkers` requires `{changed: [{map_id, updated: [...]}]}`. A flat `{map_id, markers}` payload returned HTTP 500.
- `MapService.GetMapImage` returns a nested `{image: {meta, data, etag}}` body. The MCP tool extracts `etag`, `content_type`, and byte counts, and never returns raw image bytes.
- `MapService.GetMarkers` returns a map keyed by component/access point on this stand, not a list. The normalizer preserves that key as `marker_id` and `access_point`.
- `VideowallService.RegisterWall` returned `seq_number: 0`; `ChangeWall` with `seq_number: 0` returned `new_seq_number: 1`; `SetControlData` with `seq_number: 1` returned `new_seq_number: 2`.
- `ListLayoutImages` did not have a readable live fixture on the demo stand. The tool surfaces this as `status: gap`; offline tests cover successful image-meta normalization.
- Synthetic wall and map round-trips left no known residue: wall rollback called `UnregisterWall`, map rollback called `ChangeMaps.removed`, and both reported `failed: []`.

## Sanitization Rules Applied

- Host IP -> `<demo-host>`.
- Wall cookies and cookie prefixes -> `<demo-wall-cookie>`.
- Bearer tokens and passwords never echoed.
- `hosts/Server/...` access points kept as intrinsic object identifiers.
- Map image bytes never echoed; only `bytes_returned`, `truncated`, `content_type`, `etag`, and cap metadata are retained.
