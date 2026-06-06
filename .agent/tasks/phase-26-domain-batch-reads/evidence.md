# Evidence Bundle: phase-26-domain-batch-reads

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — three batch-read client helpers — PASS
- `tools/axxon_api_client.py` gains `_domain_batch_read` (shared drain) plus
  `get_cameras_by_components`, `batch_get_archives_domain`, `search_maps`. Each
  builds `repeated ResourceLocator(access_point=...)`, drains the DomainService
  server stream, and returns items/maps + not_found_objects + unreachable_objects.
- Proof: helper + live (1 camera / 1 archive / 1 map locator).

## AC2 — three read-only view tools — PASS
- `tools/axxon_mcp_view.py` gains `get_cameras_by_components`,
  `batch_get_archives`, `search_maps` returning summarized {status, tool, count,
  items (access points/ids), not_found, unreachable}. Empty input -> gap, no wire
  call. URL/ids/metadata only, never media bytes.
- Proof: `DomainBatchReadTests` (summaries + empty-input gap + AP passthrough);
  live gap path for all three.

## AC3 — server registration — PASS
- The three tools registered inside the existing `register_view_tools` (no new
  flag/param).
- Proof: raw/test-unit.txt (server import OK).

## AC4 — unit + full suite green — PASS
- 4 new tests (17 in the view suite). Full suite `Ran 800 tests ... OK`
  (raw/test-unit.txt).

## AC5 — corpus restamp + coverage doc — PASS
- GetCamerasByComponents, BatchGetArchives, SearchMaps -> tested-pass. Coverage
  205 pass-class / 118 pending / 38 fixture-warn; DomainService 21/21 (complete);
  item 10m. Restamp dry-run reports 0 after --write.

## Stand hygiene
- Read-only: nothing on the stand was created, changed, or deleted. The tools
  return access points / ids and counts only, never media bytes. No proto/CA/PDF
  committed; secrets env-only; no biometric data.

## ACFA pivot note
- AcfaService PerformAction/DownloadData were probed first and rejected: the stand
  has only ACFA unit type definitions (no configured units), and PerformAction is
  a non-reversible physical access-control side effect. DomainService reads were
  the clean reversible-by-nature alternative.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`. Access points
  (hosts/Server/...) may stay.
