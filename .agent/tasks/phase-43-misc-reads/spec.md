# Task Spec: phase-43-misc-reads

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json
- tools/axxon_mcp_layout_manager.py (gated module idiom to mirror)

## Original task statement
Continue the API-coverage proof loop. Close a batch of serviceable methods across four small
services via one new module: DynamicParametersService (AcquireDynamicParameters,
AcquireDeviceAdditionalData), ArchiveVolumeService (ProbeVolume), GenericSettingsService
(GetSettings + reversible SaveSettings/RemoveSettings), NodeNotifier (Ping). Live-verify
reversibly.

## Live probe findings (2026-06-07, demo stand)
- AcquireDynamicParameters / AcquireDeviceAdditionalData (uid=hosts/Server/DeviceIpint.1):
  each returns status DONE (0). SERVICEABLE (read).
- ProbeVolume (volume_type LOCAL, node Server, bogus path): returns structured
  status_code NOT_A_VOLUME with error_details "ProbeVolume for block storage not
  implemented" -> RPC reachable and exercised. SERVICEABLE (read/probe).
- GenericSettingsService: context must be a real GUID. SaveSettings to a throwaway GUID
  context -> MODIFICATION_RESULT_OK; GetSettings returns the saved values; RemoveSettings ->
  OK; a follow-up GetSettings returns NOT_FOUND (context removed). Full reversible round-trip.
- NodeNotifier.Ping (deprecated): streaming, returns at least one response. SERVICEABLE.

## Message shapes (confirmed live)
- AcquireDynamicParametersRequest{uid}; AcquireDeviceAdditionalDataRequest{uid}; responses {status(EStatus), properties}.
- ProbeVolumeRequest{volume_type, connection_params(map), aes_key_hex, node_name}; ProbeVolumeResponse{status_code(EProbeResultCode), error_details}.
- GetSettingsRequest{context, scope}; SaveSettingsRequest{settings(Settings{info{context,revision}, values(Struct)}), scope}; RemoveSettingsRequest{to_remove(SettingsInfo{context,revision}), scope}.
- PingRequest{timeoutMs}; Ping returns stream PingResponse.

## Acceptance criteria
- AC1: New module tools/axxon_mcp_misc_reads.py exposes acquire_dynamic_parameters,
  acquire_device_additional_data, probe_volume, get_generic_settings, ping_node (reads) and
  save_generic_settings + remove_generic_settings (gated writes), with connect helper +
  ensure_client + _stub_and_pb2 + _write_gate matching the layout_manager idiom. Approval env
  AXXON_MISC_WRITE_APPROVE=1, confirmation token CONFIRM-misc-write.
- AC2: save_generic_settings/remove_generic_settings enforce the gate before any wire call:
  env-off -> disabled; bad token -> gap; missing required field -> error. The reads require
  their key argument (uid/context) else error. Unit tests assert client.calls==[] in each
  gated/empty case.
- AC3: Server wiring complete via the 6-edit pattern (param, conditional register,
  register_misc_reads_tools with @server.tool entries, --enable-misc-reads flag, flag-gated
  instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: the two acquire reads return DONE; probe_volume returns a structured
  result code; ping_node returns >=1 response; save/get/remove generic settings round-trip
  on a throwaway GUID context (saved values read back, then context removed -> NOT_FOUND).
  Raw transcript raw/live-verify.txt with host/creds sanitized.
- AC5: Corpus restamp marks AcquireDynamicParameters, AcquireDeviceAdditionalData,
  ProbeVolume, NodeNotifier.Ping, GenericSettingsService GetSettings/SaveSettings/RemoveSettings
  tested-pass. Dry-run after --write reports 0 restamped. Coverage doc updated; the four
  services advance (DynamicParametersService 2/2, ArchiveVolumeService 1/1,
  GenericSettingsService 3/3, NodeNotifier 5/6).
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- GenericSettings verification uses a throwaway GUID context that is created and removed;
  no residual settings.
- DynamicParameters/ProbeVolume verified against a real device / bogus volume path (no
  mutation). Ping is a read.
- Never fake live evidence; only restamp what the device services.
- .env gitignored and unstaged; sanitize demo host -> <demo-host>, creds -> <redacted>.
- Smallest defensible diff; reuse public_config_summary.

## Non-goals
- NodeNotifier.PushDiagnosticEvents (diagnostic-event push, out of scope).
- Real volume creation/format via ProbeVolume (probe only).

## Verification plan
- Build: import module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_misc_reads.py (reads, gate, no-leak).
- Integration: full suite.
- Lint: ruff on production module + server.
- Manual: live transcript + restamp dry-run clean.
