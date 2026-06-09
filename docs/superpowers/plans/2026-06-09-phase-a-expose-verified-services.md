# Phase A — Expose the verified-but-no-tool services

**Date:** 2026-06-09
**Status:** Ready to build
**Roadmap phase:** A (see `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md` §5)
**Workflow:** repo-task-proof-loop (`init` → freeze spec → build TDD → evidence → fresh verify → fix)

---

## 1. Goal

Turn the **10 services whose RPCs already pass live but have no dedicated MCP tool** into
LLM-callable tool groups, so an assistant can invoke them by intent. Pure upside: no fixtures,
no infra, no destructive operations. All 20 in-scope RPCs are `read`-class except one
(`SharedKVStorageService.Commit`, which is gated).

After Phase A, `STATUS.md` §3 should have **zero bold "verified-but-no-tool" rows** and the
"services with a dedicated tool group" count should move from 33/51 toward 43/51.

### Explicitly out of scope (per the user, 2026-06-09)

These stay untouched in Phase A — they need a test endpoint or destructive go-ahead:

- **Need a test endpoint:** GSMNotifier `SendSMS`, EMailNotifier `SendEMail`,
  DomainNotifier/NodeNotifier `PushDiagnosticEvents`, InstallationPackageProvider
  `DownloadInstallerPackage`.
- **Destructive (need explicit go-ahead + throwaway targets):** LicenseService
  `DistributeLicenseKey`/`DropLicenseKey`/`CreateLicenseDocument`, BackupSourceService ×3,
  ConfigurationManager `RestoreBackup`/`SetRevision`, DomainManager
  `AddNode`/`DropNode`/`ProclaimDomain`, CloudService ×3.

> Note: `InstallationPackageProvider.CheckPackageAvailability` (read) **is** in scope; only its
> `DownloadInstallerPackage` sibling is excluded. Same for `ConfigurationManager` — the
> `GetRevisionInfo`/`CollectBackup` reads are in scope, the restore/set-revision writes are not.
> `DomainManager.EnumerateNodes` (read) is in scope; the three topology mutations are not.

---

## 2. The exact RPCs to expose (20 RPCs, 10 services)

Verified from `api_methods.json` + the protos. `class` is the corpus `safety_class`.

| New group | Module | RPCs (proto) | class | Notes |
| --- | --- | --- | --- | --- |
| `devices_catalog` | `axxon_mcp_devices_catalog.py` | `ListVendors`, `ListVendorsV2`, `ListDevices`, `ListDevicesV2`, `GetDevice` | read | the camera-driver catalog; `GetDevice` needs `vendor` + `model` |
| `filesystem_browser` | `axxon_mcp_filesystem_browser.py` | `ListDirectory`, `GetFileInfo`, `GetSpace` | read | byte/entry-capped listing; `node_name`/`path` optional |
| `shared_kv` | `axxon_mcp_shared_kv.py` | `ListRecords`, `BatchGetRecords`, `GetRecordsStream`, `Commit` | read ×3 + review ×1 | `Commit` is the only mutating tool → confirmation token + `AXXON_SHARED_KV_APPROVE` |
| `statistics` | `axxon_mcp_statistics.py` | `GetStatistics` | read | server/stream health metrics |
| `config_revisions` | `axxon_mcp_config_revisions.py` | `GetRevisionInfo`, `CollectBackup` | read | `CollectBackup` is server-streaming → byte/time cap |
| `event_taxonomy` | `axxon_mcp_event_taxonomy.py` | `GetEventGroupingTags` | read | event grouping tags for filter building |
| `domain_topology` | `axxon_mcp_domain_topology.py` | `EnumerateNodes` | read | node enumeration only (mutations excluded) |
| `scene_description` | `axxon_mcp_scene_description.py` | `ListSceneDescription` | read | scene geometry for analytics |
| `package_availability` | `axxon_mcp_package_availability.py` | `CheckPackageAvailability` | read | update/package availability check |
| `global_tracker` | `axxon_mcp_global_tracker.py` | `GetProfile` | read | one verified read; the other 6 GlobalTracker RPCs stay fixture-gated |

**Streaming RPCs** (`ListVendorsV2`, `ListDevicesV2`, `GetRecordsStream`, `CollectBackup`,
`GetProfile`) must enforce the existing bounded-stream pattern: entry cap + byte cap + time cap,
with partial-result reporting matching `subscribe_events_bounded`.

### Proto request shapes (confirmed from the gitignored protos)

- `ListVendorsRequest{ category, filter, node_name }` — all optional.
- `ListDevicesRequest{ category, vendor, …, node_name }` — all optional.
- `GetDeviceRequest{ vendor, model, node_name }` — **vendor + model required.**
- `ListDirectoryRequest{ node_name, path }` — empty path = root.
- `GetFileInfoRequest{ node_name, path }` / `GetSpaceRequest{ node_name, path }`.
- `ListRecordsRequest{ prefix, view }`.
- `SharedKVCommitRequest{ prefix, set[], removed[] }` — the mutating one.

---

## 3. The repo pattern every group follows (confirmed from `axxon_mcp_license_reads.py`)

Each read-only group is a small, self-contained module plus 6 wiring touchpoints in
`axxon_mcp_server.py`. The plan replicates this exactly — no new architecture.

### 3a. Module shape (`axxon_mcp_<group>.py`)

```python
PROTO = "axxonsoft/bl/config/DevicesCatalog.proto"
PB2   = "axxonsoft.bl.config.DevicesCatalog_pb2"
<GROUP>_TOOL_NAMES = ("<group>_connect_axxon_profile", "<rpc_tool_1>", ...)

def default_config_factory() -> AxxonClientConfig: ...   # from_env(repo_root=...)
def default_client_factory(config) -> AxxonApiClient: ...

@dataclass
class AxxonMcp<Group>:
    client_factory = default_client_factory
    config_factory = default_config_factory
    client = None; profile_name = None

    def <group>_connect_axxon_profile(self, profile="env") -> dict: ...
    def connect_axxon_profile(self, profile="env"): return self.<group>_connect_axxon_profile(profile)
    def ensure_client(self): ...
    def _stub_and_pb2(self): client.authenticate_grpc(); return stub, pb2

    def <rpc_tool>(self, ...args...) -> dict:
        stub, pb2 = self._stub_and_pb2()
        resp = stub.<Rpc>(pb2.<Req>(...), timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "tool": "<rpc_tool>", ...summarized fields, never raw secrets...}
```

- **Reuse `AxxonApiClient`** via `stub_from_proto(PROTO, ServiceName)` + `import_module(PB2)`.
  No new transport code.
- **Streaming RPCs** wrap the iterator with the existing bounded helper (entry/byte/time caps);
  return `{status, items, truncated, reason}`.
- **`shared_kv.commit_record`** is the one mutation: require a `confirm` token, gate on
  `AXXON_SHARED_KV_APPROVE`, return a plan-style result. Reuse the existing confirmation-token
  helper used by other mutating groups (study `axxon_mcp_config_change.py` for the token shape).

### 3b. Server wiring (6 touchpoints per group, in `axxon_mcp_server.py`)

1. **`CAPABILITY_GROUPS`** entry: `"<group>": ("<desc>", ("<example tool>",), "--enable-<group>")`.
2. **`create_server` factory param**: `<group>: Any | None = None`.
3. **enabled-groups tuple** (the `("auth_sessions", auth_sessions), ...` list): add `("<group>", <group>)`.
4. **Conditional register** in `create_server`: `if <group> is not None: register_<group>_tools(server, <group>)`.
5. **`register_<group>_tools(server, <group>)`** function: one `@server.tool(name=...)` per RPC,
   delegating to the module method.
6. **`main()`**: add `--enable-<group>` to `build_parser()`; instantiate
   `if args.enable_<group>: from axxon_mcp_<group> import AxxonMcp<Group>; <group> = AxxonMcp<Group>()`;
   pass `<group>=<group>` into `create_server(...)`.

**Open-by-default is automatic.** `apply_enable_all` and `apply_default_open` both iterate every
`enable_*` arg, so each new `--enable-<group>` flag is turned on by the no-flag default and by
`--enable-all`, and disabled by `--read-only` only for mutations. The **only** new approval var is
`AXXON_SHARED_KV_APPROVE`, added to `APPROVE_ENV_VARS` so default-open sets it to `"1"`.

### 3c. Test shape (`tools/tests/test_axxon_mcp_<group>.py`)

Mirror `test_axxon_mcp_license_reads.py`:
- `FakeConfig` + fake stub returning canned protos; **no live connection in unit tests.**
- Assert each tool returns `{status: "ok", tool: "..."}` with summarized fields.
- **Secret-leak assertions**: feed a sentinel secret into config/responses and assert it never
  appears in any tool output (the repo's standing redaction rule).
- **Cap enforcement** for streaming tools: assert `truncated=True` + partial results when the
  cap is hit.
- **`shared_kv.commit_record`**: assert it refuses without a valid `confirm` token and without
  `AXXON_SHARED_KV_APPROVE`.

---

## 4. Step-by-step build sequence

Run under the proof loop. Commit after each logical step (the user's rule). Build the simplest
group first to lock the pattern, then fan out.

### Step 0 — Freeze the spec
`init phase-a-expose-services`; freeze `.agent/tasks/phase-a-expose-services/spec.md` with
acceptance criteria AC1–AC8 below. Symlink the gitignored proto dir into the worktree for live
runs; **remove the symlink before any commit.**

### Step 1 — `statistics` (smallest: 1 unary read) — lock the pattern
- Module `axxon_mcp_statistics.py`: `get_statistics()` → `StatisticService.GetStatistics`.
- Unit test with fake stub + secret-leak assertion.
- Wire the 6 server touchpoints.
- TDD: write the test first (fails), implement, green.
- Commit: `feat: expose StatisticService GetStatistics as MCP tool`.

### Step 2 — `event_taxonomy`, `scene_description`, `package_availability`, `domain_topology`
Four more single-unary-read groups, same pattern as Step 1. One commit per group.
- `event_taxonomy.get_event_grouping_tags` → `EventDescription.GetEventGroupingTags`.
- `scene_description.list_scene_description` → `NgpNodeService.ListSceneDescription`.
- `package_availability.check_package_availability` → `InstallationPackageProvider.CheckPackageAvailability`.
- `domain_topology.enumerate_nodes` → `DomainManager.EnumerateNodes`.

### Step 3 — `config_revisions` (1 unary + 1 server-stream with cap)
- `get_revision_info` (unary) + `collect_backup` (server-stream → **byte/time cap**, return
  `{bytes_seen, truncated}`; never write the backup blob to disk in the tool, just report).
- Test the cap path explicitly.
- Commit.

### Step 4 — `filesystem_browser` (3 unary reads, path args)
- `list_directory(node_name="", path="")`, `get_file_info(path)`, `get_space(path)`.
- Cap directory listing entry count; redact nothing-but ensure no absolute host paths leak
  beyond what the API returns (these are server-side paths, acceptable to return).
- Commit.

### Step 5 — `devices_catalog` (5 RPCs incl. 2 streaming) — the headline group
- `list_vendors(category="", filter="", node_name="")` (unary).
- `list_vendors_v2(...)` (server-stream → cap).
- `list_devices(category="", vendor="", node_name="")` (unary).
- `list_devices_v2(...)` (server-stream → cap).
- `get_device(vendor, model, node_name="")` — **vendor + model required**; validate args, return
  `gap` status with a clear message if missing.
- This group feeds the camera-add recipe; expose enough device metadata (vendor, model,
  supported drivers/params) for the NL translator (Phase E) to consume later.
- Commit.

### Step 6 — `global_tracker` (1 verified server-stream read)
- `get_profile(...)` → `GlobalTrackerService.GetProfile`, bounded-stream capped.
- The other 6 GlobalTracker RPCs are fixture-blocked: do **not** add them; note in the module
  docstring that they ship in Phase B once a tracker fixture exists.
- Commit.

### Step 7 — `shared_kv` (3 reads + 1 gated mutation)
- `list_records(prefix="", view=...)`, `get_records(keys)` (`BatchGetRecords`),
  `get_records_stream(...)` (server-stream → cap).
- `commit_record(prefix, set, removed, confirm)` — **mutating**: confirmation token +
  `AXXON_SHARED_KV_APPROVE` gate; reuse the existing token helper; return plan-style result.
- Add `AXXON_SHARED_KV_APPROVE` to `APPROVE_ENV_VARS`.
- Test both the read path and the refuse-without-token / refuse-without-approve paths.
- Commit.

### Step 8 — One smoke script for the whole phase
- `tools/axxon_phase_a_smoke.py`: connect to the stand, call one read from each of the 10 groups,
  print `PASS/WARN/FAIL` per call (retry up to 3× on transient `urlopen`/`DEADLINE_EXCEEDED`,
  per the stand note). `shared_kv.commit_record` writes a `codex-*`-prefixed key and rolls it
  back (delete via `removed`) so the smoke is reversible.
- Run it against `<demo-host>` via a Sonnet sub-agent (per the project rule for verifying live
  tools), capture sanitized evidence to `docs/api-audit/phase-a-expose-services-smoke-latest.md`.
- Commit the evidence (sanitized: host→`<demo-host>`, etc.).

### Step 9 — Update the corpus + docs
- `api_methods.json`: the 20 RPCs are already `tested-pass`; no status flip needed, but add the
  `mcp_tool` linkage if the schema tracks it (check `generate_api_catalog.py` / corpus README).
- `safety_policies.json`: one entry per new tool (read tools = read class; `commit_record` =
  review, caps, `AXXON_SHARED_KV_APPROVE`, rollback strategy).
- `STATUS.md` §3: flip the 10 services' `tool group?` to `yes`; update the "33/51" and tool count
  numbers; regenerate the table with the §3 command.
- `docs/COVERAGE.md`: regenerate if it tracks tool exposure.
- `README.md`: bump the tool count and add the new groups to the layer table if it enumerates them.
- Commit: `docs: Phase A — 10 services exposed, status refreshed`.

### Step 10 — Fresh verification pass (offline + full live)
- Fresh-session verifier judges current code + current command output (not chat claims).
- **Offline gate:** `python3.12 -m unittest discover -s tools/tests` **and** `python3.12 -m pytest tools/tests/ -q`
  both green; `--help` lists the 10 new flags; `list_capabilities` reports the 10 new groups.
- **Full live gate (every new tool, not just one-read-per-group like Step 8):** exercise **all 31
  new Phase A tools** against the real stand and record a PASS/WARN/FAIL per tool. This is the gate
  that turns unit-correct into verified-live: live proto field shapes, the dotted-proto
  `Node.Ancillary` stub resolving at runtime, `GetDevice` needing a real vendor/model that exists,
  `collect_backup_probe`/`get_records_stream`/V2 streams actually streaming, and the
  `shared_kv.commit_record` round-trip.
  - Run via a Sonnet sub-agent with the live env (`AXXON_HOST`, `AXXON_HTTP_URL`, `AXXON_USERNAME`,
    `AXXON_PASSWORD`, `AXXON_TLS_CN=Server`, `AXXON_CA`, `AXXON_PROTO_DIR`). Reads work over HTTP
    `/grpc` with no CA; direct-gRPC tools need the gitignored CA + protos symlinked into the run
    location. **Symlink in, run, then REMOVE the symlink before any commit** — it must never be
    committed.
  - Retry transient `urlopen`/`DEADLINE_EXCEEDED` up to 3× before judging FAIL (stand is remote).
  - Mutations are reversible only: `shared_kv.commit_record` uses a `codex-*` key set then removed
    (rollback verified by re-reading). No other new tool mutates.
  - A tool that the stand cannot exercise (e.g. `get_profile` with no tracker fixture, `get_device`
    with no matching model) is recorded `WARN: fixture-needed` with the precise missing object, not
    FAIL.
  - Capture sanitized evidence to `docs/api-audit/phase-a-live-verification-latest.md`
    (host→`%3Cdemo-host%3E`, user→`%3Cdemo-user%3E`, CA/tokens/passwords→`%3Credacted%3E`;
    `AXXON_TLS_CN=Server` may stay; `hosts/Server/...` UIDs may stay).
- If not PASS (offline or live) → `problems.md`, smallest safe fix, reverify. A documented
  `WARN: fixture-needed` is not a FAIL.

---

## 5. Acceptance criteria

| ID | Criterion | How verified |
| --- | --- | --- |
| AC1 | 10 new tool groups exist, each with a `*_connect_axxon_profile` + per-RPC tools (20 RPCs total). | grep tool names; `list_capabilities` |
| AC2 | All 10 `--enable-<group>` flags appear in `--help` and are on under no-flag default and `--enable-all`. | run `--help`; assert `apply_default_open` enables them |
| AC3 | Every new read tool returns `{status:"ok", tool:...}` with summarized fields and **no raw secrets**. | unit tests with sentinel-secret assertions |
| AC4 | Streaming tools (`ListVendorsV2`, `ListDevicesV2`, `GetRecordsStream`, `CollectBackup`, `GetProfile`) enforce entry/byte/time caps with partial-result reporting. | cap-path unit tests |
| AC5 | `shared_kv.commit_record` refuses without a valid `confirm` token and without `AXXON_SHARED_KV_APPROVE`; is reversible. | unit tests + smoke rollback |
| AC6 | Step-8 smoke calls one read from each of the 10 groups against the stand and reports PASS/WARN/FAIL; sanitized evidence committed. | `axxon_phase_a_smoke.py` run |
| AC7 | Full offline suite green (`unittest` + `pytest`), tool count and `STATUS.md` §3 updated and self-consistent. | both test runners; regenerate STATUS §3 table |
| AC8 | No proto / CA / secret committed; no symlink committed; evidence sanitized. | `git status`; `git check-ignore`; grep evidence for host/user/secret |
| AC9 | **All 31 new Phase A tools** exercised against the real stand in Step 10, each PASS or documented `WARN: fixture-needed` (zero FAIL); `commit_record` round-trip reverted; sanitized live evidence committed; symlink removed before commit. | Step-10 live run via Sonnet sub-agent; `docs/api-audit/phase-a-live-verification-latest.md` |

---

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| `GetDevice` needs valid vendor+model the stand may not have. | Validate args; return `status:"gap"` with the vendor list from `list_vendors` so the caller can pick a real pair. Smoke uses a vendor/model discovered from `list_vendors`/`list_devices` at runtime, not hardcoded. |
| `CollectBackup` streams a large blob. | Hard byte/time cap; the tool reports `bytes_seen`/`truncated` and never persists the blob — it is a "backup is collectible" probe, not a backup tool (the real backup is the excluded destructive set). |
| `shared_kv.commit_record` could clobber real plugin state. | `codex-*`-prefixed keys only in the smoke; confirmation token + approve gate; rollback via `removed`. |
| New group breaks the duplicate-tool-name guard. | Prefix connect tools with the group name (existing convention); run the AST dup-name check from STATUS §1 before committing. |
| Stand transient timeouts. | Retry up to 3× on `urlopen`/`DEADLINE_EXCEEDED` before judging FAIL (per the stand note). |

---

## 7. Definition of done

All AC1–AC8 PASS on a fresh verification pass; 10 services move to `tool group? = yes` in
`STATUS.md` §3; offline suite green; sanitized live evidence committed; nothing copyrighted or
secret committed. Next: Phase B (fixtures) or Phase E (NL translator depth) can consume
`devices_catalog` for the camera-add recipe.
