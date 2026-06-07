# Task Spec: phase-42-license-reads

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json (LicenseService rows)
- tools/axxon_mcp_layout_manager.py (module idiom to mirror; this module is read-only, no gate)

## Original task statement
Continue the API-coverage proof loop. Close the two serviceable read-only LicenseService
methods (LicenseKey, Restrictions) via a new read-only module. Live-verify. Document the
three license-mutation methods as out of scope (too risky on a shared stand).

## Live probe findings (2026-06-07, demo stand)
- LicenseKey: empty request, returns the current license key string (length 50992 on this
  stand). SERVICEABLE (read). The tool must NOT return the raw key (metadata-only:
  key_present boolean + key_length only).
- Restrictions: deprecated (option deprecated=true; the proto points to
  GetGlobalRestrictions/GetNodeRestrictions) but still serviceable; returns restrictions +
  available_restrictions. SERVICEABLE (read).
- DistributeLicenseKey / DropLicenseKey / CreateLicenseDocument: license mutations that would
  change the stand's licensing state -> OUT OF SCOPE, left pending (not exercised, not faked).

## Message shapes (confirmed live)
- LicenseKeyRequest{} (empty); LicenseKeyResponse{license_key}.
- RestrictionsRequest{} (empty, deprecated); RestrictionsResponse{restrictions, available_restrictions}.

## Acceptance criteria
- AC1: New read-only module tools/axxon_mcp_license_reads.py exposes get_license_key
  (metadata-only: returns key_present + key_length, never the raw key) and get_restrictions
  (returns restrictions_present + available_present and a small restrictions summary), with
  connect helper + ensure_client + _stub_and_pb2 matching the layout_manager idiom (no write
  gate: both are reads).
- AC2: Both tools return a well-formed dict; no raw license key bytes are ever returned. Unit
  tests assert the key value is absent from the output and that key_length matches the source.
- AC3: Server wiring complete via the 6-edit pattern (param, conditional register,
  register_license_reads_tools with @server.tool entries, --enable-license-reads flag,
  flag-gated instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: get_license_key returns key_present True with key_length 50992 (no raw
  key); get_restrictions returns restrictions_present True and available_present True. Raw
  transcript raw/live-verify.txt with host/creds sanitized and no license key value.
- AC5: Corpus restamp marks LicenseKey, Restrictions tested-pass. Dry-run after --write
  reports 0 restamped. Coverage doc updated; LicenseService 8/11.
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- Never return or log the raw license key (metadata-only: key_present + key_length).
- Both methods are reads; no mutation, no approval gate.
- Never fake live evidence; only restamp what the device services.
- .env gitignored and unstaged; sanitize demo host -> <demo-host>, creds -> <redacted>;
  do not commit the license key value.
- Smallest defensible diff; reuse public_config_summary.

## Non-goals
- DistributeLicenseKey / DropLicenseKey / CreateLicenseDocument (license mutations, out of
  scope on a shared stand).
- Re-implementing the already-passing license reads (GetGlobalRestrictions, etc.).

## Verification plan
- Build: import module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_license_reads.py (reads, no-key-leak).
- Integration: full suite.
- Lint: ruff on production module + server.
- Manual: live transcript + restamp dry-run clean.
