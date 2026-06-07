# Evidence: phase-37-archive-volume

Overall: PASS (all acceptance criteria PASS)

## AC1 — New module with read + gated write — PASS
`tools/axxon_mcp_archive_volume.py` defines `AxxonMcpArchiveVolume` with `list_volume_states`
(read), `resize_volume` (gated write), plus `archive_volume_connect_axxon_profile` /
`connect_axxon_profile` / `ensure_client` / `_stub_and_pb2` / `_write_gate`. Approval env
`AXXON_ARCHIVE_VOLUME_APPROVE`, token `CONFIRM-archive-resize`. Idiom matches
`tools/axxon_mcp_config_change.py`.

## AC2 — Gate enforced before any wire call — PASS
`tools/tests/test_axxon_mcp_archive_volume.py` GateTests: env off -> disabled, bad token
-> gap, missing volume_id -> error, zero new_size -> error; all assert `client.calls == []`.
Live: gate env-off=disabled, bad-token=gap (raw/live-verify.txt).

## AC3 — Server wiring via 6-edit pattern — PASS
`tools/axxon_mcp_server.py`: param `archive_volume`, conditional `register_archive_volume_tools`,
the register function with 3 `@server.tool` entries, `--enable-archive-volume` flag,
flag-gated instantiation, pass to create_server. Server smoke registered all 3 tools.
Imports OK (raw/build.txt).

## AC4 — Live reversible evidence — PASS
raw/live-verify.txt (sanitized): list_volume_states on
`hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage` -> ok, 1 volume
(4b025154-..., capacity 107374182400); resize_volume to that same capacity -> applied,
status_code 0 DONE; post-resize capacity unchanged (REVERSIBLE NO-OP OK).

## AC5 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps Resize -> tested-pass; ChangeBookmarks (deprecated
server-side), CreateReaderEndpoint, Seek, ClearInterval (CORBA INTERNAL / subsystem
unavailable) -> tested-warn-fixture-needed. Dry-run after --write reports `0 method(s)
restamped`. Coverage doc updated to 239 tested-pass / 91 pending / 31 fixture-warn;
ArchiveService 13/17.

## AC6 — Full suite green — PASS
raw/test-integration.txt: `871 passed` (863 prior + 8 new). Production module + server
lint clean (raw/lint.txt). Test-file E402 is the repo-wide sys.path baseline.
