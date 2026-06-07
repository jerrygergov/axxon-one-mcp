# Evidence: phase-43-misc-reads

Overall: PASS (all acceptance criteria PASS)

## AC1 — New cross-service module with reads + gated settings writes — PASS
`tools/axxon_mcp_misc_reads.py` defines `AxxonMcpMiscReads` with acquire_dynamic_parameters,
acquire_device_additional_data, probe_volume, ping_node, get_generic_settings (reads) and
save_generic_settings, remove_generic_settings (gated), plus connect helper / ensure_client /
_stub_and_pb2 / _write_gate. Approval env `AXXON_MISC_WRITE_APPROVE`, token
`CONFIRM-misc-write`. Each tool builds its own service stub via stub_from_proto.

## AC2 — Gate + input validation before any wire call — PASS
`tools/tests/test_axxon_mcp_misc_reads.py` GateTests: save env-off -> disabled, bad token ->
gap, empty context -> error; remove missing revision -> error; acquire/probe/get empty key ->
error; all assert `client.calls == []`. Live: gate env-off=disabled, bad-token=gap.

## AC3 — Server wiring via 6-edit pattern — PASS
`tools/axxon_mcp_server.py`: param `misc_reads`, conditional `register_misc_reads_tools`, the
register function with 8 `@server.tool` entries, `--enable-misc-reads` flag, flag-gated
instantiation, pass to create_server. Server smoke registered all 8 tools. Imports OK
(raw/build.txt).

## AC4 — Live evidence — PASS
raw/live-verify.txt (sanitized): acquire_dynamic_parameters + acquire_device_additional_data
-> result 0 (DONE); probe_volume -> NOT_A_VOLUME with error_details; ping_node -> responses 1;
save_generic_settings -> MODIFICATION_RESULT_OK; get_generic_settings -> value_count 1;
remove_generic_settings -> applied; post-remove GetSettings -> NOT_FOUND (REVERSIBLE OK). No
residual settings.

## AC5 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps AcquireDynamicParameters, AcquireDeviceAdditionalData,
ProbeVolume, NodeNotifier.Ping, GenericSettingsService GetSettings/SaveSettings/RemoveSettings
-> tested-pass. Dry-run after --write reports `0 method(s) restamped`. Coverage doc updated to
263 tested-pass / 61 pending / 37 fixture-warn; DynamicParametersService 2/2,
ArchiveVolumeService 1/1, GenericSettingsService 3/3, NodeNotifier 5/6.

## AC6 — Full suite green — PASS
raw/test-integration.txt: `930 passed` (916 prior + 14 new). Production module + server lint
clean (raw/lint.txt). Test-file E402 is the repo-wide sys.path baseline.
