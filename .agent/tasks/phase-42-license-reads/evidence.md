# Evidence: phase-42-license-reads

Overall: PASS (all acceptance criteria PASS)

## AC1 — New read-only module — PASS
`tools/axxon_mcp_license_reads.py` defines `AxxonMcpLicenseReads` with `get_license_key`
(metadata-only) and `get_restrictions`, plus connect helper / connect_axxon_profile /
ensure_client / _stub_and_pb2. No write gate (both are reads). Idiom mirrors
`tools/axxon_mcp_layout_manager.py` minus the gate.

## AC2 — No raw key returned — PASS
`tools/tests/test_axxon_mcp_license_reads.py`: get_license_key returns key_present +
key_length; tests assert the raw key string is absent from the output and key_length matches
the source. get_restrictions returns restrictions_present + available_present. No-config-leak
test passes.

## AC3 — Server wiring via 6-edit pattern — PASS
`tools/axxon_mcp_server.py`: param `license_reads`, conditional `register_license_reads_tools`,
the register function with 3 `@server.tool` entries, `--enable-license-reads` flag,
flag-gated instantiation, pass to create_server. Server smoke registered all 3 tools. Imports
OK (raw/build.txt).

## AC4 — Live evidence — PASS
raw/live-verify.txt (sanitized): get_license_key -> key_present True, key_length 50992 (no
raw key in output); get_restrictions -> restrictions_present True, available_present True.

## AC5 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps LicenseKey, Restrictions -> tested-pass. Dry-run
after --write reports `0 method(s) restamped`. Coverage doc updated to 256 tested-pass / 67
pending / 38 fixture-warn; LicenseService 8/11.

## AC6 — Full suite green — PASS
raw/test-integration.txt: `916 passed` (912 prior + 4 new). Production module + server lint
clean (raw/lint.txt). Test-file E402 is the repo-wide sys.path baseline.
