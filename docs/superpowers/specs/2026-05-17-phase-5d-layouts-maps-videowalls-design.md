# Phase 5D — Layouts, Maps, Videowalls Design

**Date:** 2026-05-17
**Status:** Draft for review
**Spec type:** Phase implementation spec (one of seven from `2026-05-16-axxon-mcp-full-coverage-roadmap.md`)

---

## 1. Goal

Cover the LayoutManager, LayoutImagesManager, MapService, and VideowallService surfaces as first-class MCP tools and operator workflows. After 5D ships:

- Customers can list and inspect every layout, map, and videowall on a stand from natural-language prompts.
- LLM agents can author maps and videowalls end-to-end through plan / apply / verify / rollback workflows.
- Layout authoring (cells, map arrangement, special layouts) becomes mutable via persistent `update_layout` / `delete_layout` to complement the already-shipped `temp_layout` (ephemeral) and `create_layout` (persistent create).
- Videowall control surfaces (`RegisterWall`, `ChangeWall`, `SetControlData`, `UnregisterWall`) ship with live evidence on the demo stand at `100.76.150.18` via a synthetic-fixture chain (the MCP registers a temporary wall, exercises it, and unregisters it cleanly).

Schedules are deferred to Phase 5F (the demo stand has no schedule units configured, and schedules conceptually belong with admin / time-zone management).

## 2. Source-of-truth references

- Roadmap: `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md` §5D.
- Phase 5A (mirror pattern): `tools/axxon_mcp_view.py`, `tools/tests/test_axxon_mcp_view.py`, `tools/axxon_view_smoke.py`.
- Phase 5C (mirror pattern for read normalizers and live smoke): `tools/axxon_mcp_alarms.py`, `tools/tests/test_axxon_mcp_alarms.py`, `tools/axxon_alarms_smoke.py`.
- Existing operator workflows (reuse plan / apply / verify / rollback machinery): `tools/axxon_mcp_operator.py` — registry of `_build_*_plan` functions plus `axxon_mcp_operator.OperatorRegistry`.
- Proto shapes verified during brainstorming:
  - `docs/grpc-proto-files/axxonsoft/bl/layout/LayoutManager.proto` (service `axxonsoft.bl.layout.LayoutManager`).
  - `docs/grpc-proto-files/axxonsoft/bl/layout/LayoutImagesManager.proto` (service `axxonsoft.bl.layout.LayoutImagesManager`).
  - `docs/grpc-proto-files/axxonsoft/bl/videowall/Videowall.proto` (service `axxonsoft.bl.videowall.VideowallService`).
  - `docs/grpc-proto-files/axxonsoft/bl/maps/MapService.proto` (service `axxonsoft.bl.maps.MapService`).
- Live data observed on demo stand `100.76.150.18` during brainstorming probes:
  - `ListLayouts(view: "VIEW_MODE_ONLY_META")` returns `{current, items[].meta{layout_id, owned_by_user, etag, has_write_access, sharing_properties}}`.
  - `ListLayouts(view: "VIEW_MODE_FULL")` returns the same plus `items[].body{id, display_name, cells, map_id, alert_panel_state, ...}`.
  - `ListMaps()` returns `{items[].meta{id, access, sharing{owner, kind, shared_roles}, name, type, etag, image_etag}}`.
  - `ListMapProviders()` returns Bitmap + Google + OSM with per-provider `map_types`, `min_zoom`, `max_zoom`, `etag`.
  - `ListWalls()` returns `{event_stream_items[].walls[], unreachable_objects[]}` (paginated stream shape).
  - `host_unit.units` contains only `[{type: "Node"}]` — no schedule units (confirms 5F deferral).

## 3. Tool inventory

### 3.1 Read tools (11, behind `--enable-view-objects`)

| Tool | RPC | Cap or fallback |
| --- | --- | --- |
| `view_objects_connect_axxon_profile(profile="env")` | auth | n/a |
| `list_layouts(view="meta"\|"full", limit=50)` | `LayoutManager.ListLayouts` | limit clamped to `LIST_LIMIT_CAP=200`; view defaults to `"meta"` |
| `get_layout(layout_id, etag=None)` | `LayoutManager.BatchGetLayouts` | unknown id → `{status: "gap"}` |
| `layouts_on_view(layouts=[{layout_id, layout_display_name}])` | `LayoutManager.LayoutsOnView` | push-only; returns `{status: "ok", pushed: count}` |
| `list_layout_images(layout_id)` | `LayoutImagesManager.ListLayoutImages` | unknown layout → `{status: "gap"}` |
| `list_maps(limit=50)` | `MapService.ListMaps` | limit clamped to `LIST_LIMIT_CAP` |
| `get_map(map_id)` | `MapService.BatchGetMaps` | unknown id → `{status: "gap"}` |
| `get_map_image(map_id, max_bytes=4_194_304)` | `MapService.GetMapImage` | byte cap `MAP_IMAGE_BYTES_CAP=4 MiB`; returns metadata only (bytes_returned, truncated, content_type, etag), never raw image bytes in tool response |
| `get_markers(map_id)` | `MapService.GetMarkers` | unknown id → `{status: "gap"}` |
| `list_map_providers()` | `MapService.ListMapProviders` | full list |
| `list_walls(limit=50)` | `VideowallService.ListWalls` | flattens paginated `event_stream_items[].walls[]`; empty list is legitimate (not gap) |

### 3.2 Operator workflows (11, behind `--enable-operator` + `AXXON_OPERATOR_APPROVE=1`)

All workflows use the existing plan / apply / verify / rollback machinery (`tools/axxon_mcp_operator.py`). Each appends to the existing in-memory audit log exposed via `axxon://operator/audit-log`. Confirmation tokens follow the existing `CONFIRM-<workflow>` / `CONFIRM-<workflow>-rollback` pattern.

| Workflow | Wraps | Persistence | Rollback |
| --- | --- | --- | --- |
| `temp_wall` | `RegisterWall` | ephemeral (auto-rolls back on plan expiry) | `UnregisterWall(cookie)` |
| `videowall_register` | `RegisterWall` | persistent (caller owns cookie) | `UnregisterWall(cookie)` |
| `videowall_change` | `ChangeWall(cookie, data, seq_number)` | persistent state-mutate | no-op (cookie still valid) |
| `videowall_set_control_data` | `SetControlData(wall_id, seq_number, data)` | persistent | no-op (data is push only) |
| `videowall_unregister` | `UnregisterWall(cookie)` | persistent | no-op (already removed) |
| `create_map` | `MapService.ChangeMaps` (added=[{Map}]) | persistent | `ChangeMaps(removed=[map_id])` |
| `update_map` | `MapService.ChangeMaps` (changed=[{Map}]) | persistent state-mutate | restore previous Map from etag-guarded snapshot captured in plan |
| `delete_map` | `MapService.ChangeMaps` (removed=[map_id]) | persistent | restore previous Map from snapshot |
| `update_markers` | `MapService.UpdateMarkers` | persistent | restore previous markers from snapshot |
| `update_layout` | `LayoutManager.Update` | persistent | restore previous layout body from etag-guarded snapshot |
| `delete_layout` | `LayoutManager.Update` (remove path) | persistent | restore previous layout from snapshot |

`get_my_control_data` is wrapped in `AxxonApiClient` for the smoke chain but **not** exposed as a standalone MCP tool — callers cannot get a wall cookie without first running `temp_wall` / `videowall_register`, and the workflow's plan output already includes the cookie when needed.

## 4. Module layout

```
tools/
├── axxon_mcp_view_objects.py          # NEW: AxxonMcpViewObjects dataclass + 11 read tools + normalizers
├── axxon_api_client.py                # MODIFY: add 14 thin wrappers
├── axxon_mcp_operator.py              # MODIFY: add 11 _build_*_plan functions + registry entries
├── axxon_mcp_server.py                # MODIFY: register_view_objects_tools + --enable-view-objects flag
├── axxon_view_objects_smoke.py        # NEW: live smoke (reads + 2 round-trips)
└── tests/
    ├── test_axxon_mcp_view_objects.py             # NEW: ~22 offline tests
    ├── test_axxon_api_client_view_objects.py      # NEW: ~6 wrapper dispatch tests
    ├── test_axxon_mcp_operator.py                 # MODIFY: append ~11 workflow tests
    └── test_axxon_mcp_server.py                   # MODIFY: append registration test
```

## 5. Class shape

```python
# tools/axxon_mcp_view_objects.py

LIST_LIMIT_CAP = 200
MAP_IMAGE_BYTES_CAP = 4_194_304
LAYOUT_VIEW_MODES = ("meta", "full")
LAYOUT_VIEW_MAP = {"meta": "VIEW_MODE_ONLY_META", "full": "VIEW_MODE_FULL"}


@dataclass
class AxxonMcpViewObjects:
    """Read-only tools for layouts, maps, and videowalls."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    _inventory: dict[str, Any] | None = None

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]: ...
    def list_layouts(self, view: str = "meta", limit: int = 50) -> dict[str, Any]: ...
    def get_layout(self, layout_id: str, etag: str | None = None) -> dict[str, Any]: ...
    def layouts_on_view(self, layouts: list[dict[str, str]]) -> dict[str, Any]: ...
    def list_layout_images(self, layout_id: str) -> dict[str, Any]: ...
    def list_maps(self, limit: int = 50) -> dict[str, Any]: ...
    def get_map(self, map_id: str) -> dict[str, Any]: ...
    def get_map_image(self, map_id: str, max_bytes: int = MAP_IMAGE_BYTES_CAP) -> dict[str, Any]: ...
    def get_markers(self, map_id: str) -> dict[str, Any]: ...
    def list_map_providers(self) -> dict[str, Any]: ...
    def list_walls(self, limit: int = 50) -> dict[str, Any]: ...
```

## 6. Normalizers

```python
def normalize_layout(raw_full_or_meta: dict[str, Any]) -> dict[str, Any]:
    """Flatten LayoutFull or LayoutMeta to a stable schema.

    Returns:
        {
            "layout_id": str,
            "display_name": str | None,
            "is_user_defined": bool | None,
            "is_for_alarm": bool | None,
            "owned_by_user": bool,
            "etag": str,
            "has_write_access": bool,
            "cells_count": int | None,
            "map_id": str | None,
        }
    """


def normalize_map(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Map (with meta) to a stable schema.

    Returns:
        {
            "map_id": str,
            "name": str,
            "type": str,          # "MAP_TYPE_RASTER" | "MAP_TYPE_GOOGLE" | ...
            "access": str,        # "MAP_ACCESS_FULL" | "MAP_ACCESS_READ"
            "owner": str,
            "sharing_kind": str,
            "etag": str,
            "image_etag": str | None,
        }
    """


def normalize_wall(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten WallInfo to a stable schema.

    Returns:
        {
            "wall_id": str,
            "host_name": str,
            "pid": int,
            "ppid": int,
            "name": str,
            "display_name": str,
            "seq_number": int,
            "data_size": int,     # len(VideowallData.data); raw bytes never echoed
        }
    """


def normalize_marker(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Marker (from GetMarkers) to a stable schema with access_point + position."""
```

## 7. Audit, sanitization, and secrets

- Wall cookies and seq_numbers are operator-state, recorded in the plan record. The audit log surface (`axxon://operator/audit-log`) keeps them; `audit_log()` returns a copy.
- `VideowallData.data` and `ControlData.data` are raw byte blobs. The MCP never echoes them in tool responses; only `data_size` is reported.
- Map images returned by `get_map_image` stay inside the client; the tool returns only `bytes_returned`, `truncated`, `content_type`, `etag` — the image content is **not** returned to the caller. (If a caller needs the image bytes, the operator-side smoke prints sanitized hash + size only.)
- Same sanitization rules as 5A/5C: host IP → `<demo-host>`, GUIDs kept (intrinsic), bearer never echoed, password never echoed.

## 8. Testing strategy

### 8.1 Offline unit tests

`tools/tests/test_axxon_mcp_view_objects.py` (~22 tests):

- `test_module_loads_and_connect_reports_profile`
- `test_list_layouts_meta_returns_normalized_items`
- `test_list_layouts_full_includes_body_fields`
- `test_list_layouts_view_validation` (unknown view → gap)
- `test_list_layouts_clamps_limit`
- `test_get_layout_returns_full_body`
- `test_get_layout_unknown_id_returns_gap`
- `test_layouts_on_view_pushes_and_returns_count`
- `test_list_layout_images_returns_image_meta`
- `test_list_layout_images_unknown_layout_returns_gap`
- `test_list_maps_returns_normalized_items`
- `test_list_maps_clamps_limit`
- `test_get_map_returns_normalized_meta`
- `test_get_map_unknown_id_returns_gap`
- `test_get_map_image_truncates_at_cap`
- `test_get_map_image_unknown_id_returns_gap`
- `test_get_markers_returns_normalized_list`
- `test_list_map_providers_returns_provider_list`
- `test_list_walls_flattens_pages_and_drops_transient_unreachable`
- `test_normalize_wall_redacts_data_bytes` (asserts `data_size` present, `data` not echoed)
- `test_normalize_layout_strips_password_keys` (sanity: never leaks `password`/`token`/`SHOULD_NOT_LEAK`)
- `test_normalize_map_passes_through_etags`

`tools/tests/test_axxon_api_client_view_objects.py` (~6 tests): each new client method dispatches the correct FQMN with the correct payload shape (parity with 5C wrapper tests).

`tools/tests/test_axxon_mcp_operator.py` (~11 new tests, one per workflow): for each workflow, `_build_*_plan` returns the expected plan structure, and a mocked apply/verify/rollback cycle records correct audit entries.

`tools/tests/test_axxon_mcp_server.py` (~1 new test): `--enable-view-objects` registers exactly the 11 read tools; operator workflows surface through the existing `register_operator_tools`.

### 8.2 Live smoke

`tools/axxon_view_objects_smoke.py`:

**Reads mode (default):** `list_layouts(meta)` → `get_layout(first_id)` → `list_layout_images(first_id)` → `list_maps()` → `get_map(first_map_id)` → `get_map_image(first_map_id)` → `get_markers(first_map_id)` → `list_map_providers()` → `list_walls()`.

**Mutation mode (`--mutation`, requires `AXXON_OPERATOR_APPROVE=1`):**

A. **Wall round-trip:**
```
plan(temp_wall, {name, display_name}) → apply (RegisterWall) → capture cookie + wall_id
plan(videowall_change, {cookie, data}) → apply
plan(videowall_set_control_data, {wall_id, data}) → apply
plan(videowall_unregister, {cookie}) → apply  (cleanup)
verify state from list_walls
```

B. **Map round-trip:**
```
plan(create_map, {name: "codex-5d-test", type: "MAP_TYPE_RASTER"}) → apply → capture map_id
plan(update_markers, {map_id, markers: [{x, y, access_point}]}) → apply
plan(delete_map, {map_id}) → apply  (cleanup)
verify gone from list_maps
```

Both round-trips run only with `AXXON_OPERATOR_APPROVE=1`. Smoke exits `0` on clean round-trip, `2` on fixture-needed (e.g., write permission denied), `1` on hard error.

### 8.3 Definition of done

1. 11 read tools + 11 operator workflows shipped, registered, offline-tested.
2. LayoutManager pending: 4 → ≤ 1 (`UserDataCleanup` deferred).
3. LayoutImagesManager pending: 3 → ≤ 1 (`Upload`/`Download` streaming RPCs deferred to a future phase; `ListLayoutImages` and `RemoveLayoutImages` covered).
4. VideowallService pending: 4 → 0 (all four register/unregister/change/set_control_data verified live via synthetic fixture).
5. MapService pending: 2 → ≤ 1 (`ConfigureMapProviders` deferred; `UserDataCleanup` deferred).
6. Live smoke reads green on demo stand; both round-trips clean on `AXXON_OPERATOR_APPROVE=1`.
7. Test suite count: 229 → ≥ 270.
8. Coverage matrix row appended; README documents `--enable-view-objects` and lists new operator workflows.
9. Sanitized live evidence at `docs/api-audit/phase-5d-view-objects-smoke-latest.md`.

## 9. Risks and open questions

| Risk | Mitigation |
| --- | --- |
| `MapService.ChangeMaps` removed-path may permanently delete maps without rollback if etag drifts. | Snapshot the full Map from `BatchGetMaps` into the plan record before apply; rollback re-adds with `ChangeMaps(changed=...)` or `(added=...)`. |
| `LayoutManager.Update` is a write-anything RPC; bad payloads can break a layout. | `update_layout` plan records the previous `LayoutFull` (from `BatchGetLayouts`) before apply; rollback restores it. |
| `RegisterWall` requires a `host_name` — using the bearer-user's hostname may collide with a real client's registration. | Use a sentinel hostname `codex-5d-smoke-<uuid>` plus randomised `pid`/`ppid` to guarantee uniqueness; `UnregisterWall` cleans up. |
| Map image bytes can exceed 4 MiB on real installs. | Byte cap clamps; smoke reports `truncated: true` and exits clean. |
| Plan / apply state crosses smoke runs (operator audit log is in-memory). | Smoke uses a single `OperatorRegistry` instance per run; rollback executes within the same process; no cross-run state. |
| No schedule fixture on demo stand. | Schedules deferred to 5F (admin / time-zone surface). |
| Layout cell editing produces complex nested protobuf shapes. | The MCP accepts an opaque `body: dict[str, Any]` for `update_layout`; partners author full layouts in the desktop client first, then `update_layout` modifies fields the LLM is reasoning over. We do not attempt schema validation of cell positions in 5D. |

## 10. Out of scope

- `LayoutImagesManager.UploadLayoutImage` and `DownloadLayoutImage` (streaming chunked RPCs — defer to a binary-handling phase, possibly 6A).
- `MapService.ConfigureMapProviders` (admin-shaped; logical fit with 5F).
- `UserDataCleanup` on LayoutManager and MapService (admin maintenance; defer to 5F).
- Schedule authoring (no fixture; defer to 5F).
- Real videowall-device discovery (separate from `VideowallService` — that's a client-side process). The MCP's videowall surface stays bounded to the four `VideowallService` RPCs.

## 11. Self-review

- **Placeholders:** none. All tool names, RPC mappings, payload shapes, normalizers, file paths, and acceptance criteria are concrete.
- **Internal consistency:** the 11 read tools + 11 operator workflows match the §3 inventory exactly; the §5 class shape lists 11 methods; the §8.1 test list covers all 11 read tools plus 4 normalizers.
- **Scope:** sized as one implementation plan. Schedules deferred to 5F. Streaming image upload/download deferred. Layout cell-schema validation deferred. Map provider configuration deferred.
- **Ambiguity:**
  - "videowall change" verbed as a state mutate (re-pushing `data`), not as a config-tree edit — clarified in §3.2.
  - `update_map` and `delete_map` rollback semantics specified to snapshot the previous Map before apply.
  - `get_map_image` clarifies that bytes are not returned in tool response, only metadata.
- **Defaults vs. caps:** clarified that `LIST_LIMIT_CAP=200` and `MAP_IMAGE_BYTES_CAP=4 MiB` are upper bounds, not literal defaults.

Spec self-review complete. Ready for user review.
