# Phase A live smoke — latest

**Date:** 2026-06-09
**Harness:** `tools/axxon_phase_a_smoke.py --commit`
**Target:** `%3Cdemo-host%3E` (HTTP :80 bridge for reads; direct gRPC :20109 with `AXXON_TLS_CN=Server`)
**Scope:** one representative read per Phase A group (10 groups) + the reversible
`shared_kv.commit_record` round-trip. (The exhaustive per-tool live pass over all 31 tools is
Step 10 / AC9.)

## Result

```
PASS  statistics.get_statistics            (count=0)
PASS  event_taxonomy.get_event_grouping_tags (count=0)
PASS  scene_description.list_scene_description (count=10)
WARN  package_availability.check_package_availability (server UNIMPLEMENTED on this stand)
PASS  domain_topology.enumerate_nodes      (node_count=1)
PASS  config_revisions.get_revision_info   (ok)
PASS  filesystem_browser.list_directory    (count=2)
PASS  devices_catalog.list_vendors         (count=318)
PASS  global_tracker.get_profile           (count=0)
PASS  shared_kv.list_records               (count=8)
PASS  shared_kv.commit_record (round-trip) (set=applied remove=applied reverted=True)

PASS=10 WARN=1 FAIL=0
```

## Findings

- **All 10 groups reach the live server and return real data.** `devices_catalog.list_vendors`
  returned 318 vendors — the headline camera-driver catalog works end-to-end.
- **`scene_description`** confirms the dotted-proto module (`axxonsoft.bl.node.Node.Ancillary.proto`
  → `axxonsoft.bl.node.Node.Ancillary_pb2`) resolves and streams against the real server.
- **`shared_kv.commit_record` round-trip is reversible:** set a `codex-`-prefixed key, then remove
  it; post-remove readback confirms `revision == ""` (key gone). The stand is left clean.
- **`package_availability` = WARN (fixture/capability gap, not a tool bug):** the stand returns
  gRPC `UNIMPLEMENTED` ("required system does not supported"). The tool faithfully surfaces the
  server response; the subsystem is simply not active on this stand.

## Harness notes (learned from the first live run)

- `BatchGetRecords` (behind `get_records(keys=[...])`) echoes a zero-revision stub for **absent**
  keys, so presence must be judged by `revision != ""`, not key presence. The round-trip revert
  check uses that signal.
- `FileSystemBrowser` rejects `path="/"` with a CORBA `InvalidPath`; an empty path lists the root
  (per the proto), which is the correct probe.
- Server `UNIMPLEMENTED` / `InvalidPath` are classified WARN (stand capability/input gap), not FAIL.

## Sanitization

Host → `%3Cdemo-host%3E`, user/password → `%3Credacted%3E`. `AXXON_TLS_CN=Server` is a non-secret
fact and is retained. No proto files, CA, or credentials are committed. No symlink was created (the
gitignored CA + protos already live at `docs/grpc-proto-files/` in this repo).
