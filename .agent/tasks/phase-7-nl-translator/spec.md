# Task spec — phase-7-nl-translator

## Original task statement

Phase 7 of the Axxon One MCP full-coverage roadmap: NL -> plan translator and recipe assembler.

Deliver three read-only (non-executing) MCP tools that translate English intents into verified
operator-workflow plans, then expose rich previews. Recipe execution continues to use the
existing `apply_operator_plan` tool.

Source: `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md` lines 405-417.

---

## Scope

### New files

| File | Purpose |
|---|---|
| `tools/axxon_mcp_translator.py` | Module containing `AxxonMcpTranslator` dataclass and the three tool methods |
| `tools/tests/test_axxon_mcp_translator.py` | Unit tests for the translator module |

### Three tools

**1. `assemble_recipe(intent_text, context)`**

Translate an English intent string plus optional structured context dict into an ordered
list of workflow steps. Each step is a dict:

```python
{"workflow": str, "params": dict, "why": str}
```

Must handle at least 10 named reference intents (see AC2). When the intent maps to no known
operator workflow, return a structured gap result:

```python
{"status": "unsupported_intent", "intent_text": str, "reason": str, "known_workflows": list[str]}
```

Never invents workflow names or API shapes. Only references names present in `WORKFLOWS` in
`tools/axxon_mcp_operator.py`.

**2. `validate_recipe(recipe)`**

Accept the list of steps produced by `assemble_recipe`. For each step, call
`operator.plan(workflow, params)` (dry-run, no apply). Return an aggregated result:

```python
{
    "valid": bool,
    "steps": [
        {
            "workflow": str,
            "status": "planned" | "gap",
            "plan_id": str | None,
            "risk": str | None,
            "confirmation_token": str | None,
            "rollback_confirmation_token": str | None,
            "required_env_gates": list[str],   # e.g. ["AXXON_OPERATOR_APPROVE"] or archive maintenance env
            "message": str | None,
        },
        ...
    ],
    "risk_classes": list[str],           # deduplicated across steps
    "required_approvals": list[str],     # deduplicated env gate names
    "gaps": list[str],                   # workflow names whose step returned status=="gap"
}
```

`valid` is `True` only when every step status is `"planned"` (no gaps). No network calls; uses
the injected operator factory for dry-run only.

**3. `explain_recipe(recipe)`**

Accept the list of steps (pre- or post-validation). Return a human-readable string (or
structured dict with a `"text"` key) with:

- Per-step: intent summary (`why`), risk classification, rollback strategy note.
- An estimated wall-clock note per step (static lookup by risk class; no network).
- A footer summarizing required confirmations and env gates.

Pure formatting; zero network calls.

---

## Module conventions

Follows the established naming pattern in this repo:

- Dataclass `AxxonMcpTranslator` with `operator_factory: Callable[[], OperatorRegistry]`.
- Registration function `register_translator_tools(server, translator)`.
- CLI flag `--enable-translator` in `build_parser()`.
- `create_server` parameter `translator: Any | None = None`.
- Server wires `if translator is not None: register_translator_tools(server, translator)`.
- Instantiation in `main()` under `if args.enable_translator:`.

---

## Reference intent catalogue (for AC2)

The following 10 intents must be handled. "Handled" means `assemble_recipe` returns a non-empty
`steps` list referencing only known workflow names.

| # | Intent phrase (representative) | Expected workflow(s) |
|---|---|---|
| I-1 | Add a camera at `<ip>` | `create_camera` |
| I-2 | Add AV detector to camera `<uid>` | `create_av_detector_full` |
| I-3 | Add AppData detector to camera `<uid>` | `create_appdata_detector_full` |
| I-4 | Set camera archive to 14 days | `archive_policy_update` |
| I-5 | Create export schedule macro for camera `<uid>` | `create_macro` |
| I-6 | Create layout named `<name>` | `create_layout` |
| I-7 | Add camera to existing layout | `update_layout` |
| I-8 | Create map named `<name>` | `create_map` |
| I-9 | Place camera marker on map | `update_markers` |
| I-10 | Inject external alarm event | `external_event_inject` |

Multi-step combinations (e.g. "add a camera with face detection and 7-day archive") must
produce multiple ordered steps, each referencing a single known workflow.

---

## Acceptance criteria

**AC1 — Module and three methods exist**

`tools/axxon_mcp_translator.py` defines class `AxxonMcpTranslator` with methods
`assemble_recipe(intent_text, context)`, `validate_recipe(recipe)`, and
`explain_recipe(recipe)`. The file is importable with no side effects from a clean Python
environment (no live server required).

**AC2 — assemble_recipe maps >= 10 reference intents to known-workflow step sequences**

For each of the 10 intents in the reference catalogue above, calling
`translator.assemble_recipe(intent_text, context)` returns a dict containing a `"steps"` key
whose value is a non-empty list. Every `step["workflow"]` value in every returned list is a
key in `WORKFLOWS` (imported from `axxon_mcp_operator`). No fabricated workflow names appear.

**AC3 — assemble_recipe returns a structured gap for unsupported intents**

Given an intent that references a concept with no matching operator workflow (e.g. a PTZ
preset command, a user/role assignment, a permission change), `assemble_recipe` returns a
dict with `"status": "unsupported_intent"`, a non-empty `"reason"` string, and a
`"known_workflows"` list. It does not raise an exception and does not fabricate a workflow name.

**AC4 — validate_recipe dry-runs via operator.plan and aggregates gaps/approvals/risk**

`validate_recipe` calls `operator.plan(workflow, params)` for each step with no network
connection (operator injected via factory; tests use a stub). The returned dict contains
`"valid"`, `"steps"`, `"risk_classes"`, `"required_approvals"`, and `"gaps"` keys. When all
steps plan successfully, `valid` is `True` and `gaps` is empty. When any step returns
`status=="gap"`, `valid` is `False` and that workflow name appears in `gaps`.

**AC5 — explain_recipe renders risk, rollback, and time preview with no network**

`explain_recipe` returns a non-empty string or a dict with a `"text"` key. The output
contains each step's `why`, risk classification word, and a rollback note. A wall-clock
estimate appears for each step (static; not fetched). No network I/O occurs; the method must
work on a fully offline machine against a stub operator.

**AC6 — MCP tools registered behind --enable-translator with server test**

`tools/axxon_mcp_server.py` gains:
- Parameter `translator: Any | None = None` in `create_server`.
- `if translator is not None: register_translator_tools(server, translator)` branch.
- `--enable-translator` argument in `build_parser()`.
- `if args.enable_translator:` block in `main()` that constructs `AxxonMcpTranslator`.

`tools/tests/test_axxon_mcp_server.py` (or a new server test file) gains a test named
`test_create_server_registers_translator_tools_only_when_enabled` that asserts the three
translator tool names appear when `translator` is non-None and do not appear when it is None.

**AC7 — Unit tests added and full suite grows beyond 629 and stays green**

`tools/tests/test_axxon_mcp_translator.py` exists and contains unit tests covering at minimum:
- All 10 reference intents (AC2).
- At least 2 unsupported-intent gap cases (AC3).
- validate_recipe with a fully planned recipe (AC4 happy path).
- validate_recipe with a partially gapped recipe (AC4 error path).
- explain_recipe on a valid recipe (AC5).
- explain_recipe on a gapped recipe (AC5, should not raise).

Running `python3.12 -m unittest discover -s tools/tests` from the repo root must exit 0 with
a count strictly greater than 629. No previously passing test may regress.

**AC8 — Live verification: >= 3 ephemeral recipes round-trip on the demo stand**

Against `<demo-host>` (credentials from env), at least 3 ephemeral (reversible) reference
recipes must complete the full cycle:

```
assemble_recipe -> validate_recipe -> apply_operator_plan (per step) -> rollback_operator_plan (per step) -> verify_operator_plan
```

All applied steps must rollback cleanly. Evidence must be sanitized before committing (no
host IPs, credentials, or UIDs). Persistent or destructive recipes (archive format, archive
reindex) are validated via `validate_recipe` but NOT applied live.

---

## Constraints

1. The translator composes known workflows only. It must never invent API shapes, field names,
   or workflow names. The authoritative workflow list is `WORKFLOWS.keys()` in
   `tools/axxon_mcp_operator.py`.
2. All credentials are env-only. No literal host, username, password, or secret may appear in
   source code or tests.
3. `AxxonMcpTranslator` must accept an `operator_factory: Callable[[], OperatorRegistry]`
   so unit tests can inject a stub without network access.
4. `validate_recipe` must not call `operator.apply` or `operator.rollback`. Dry-run via
   `operator.plan` only.
5. `explain_recipe` must produce output with zero network I/O. It may receive either the raw
   `assemble_recipe` output (steps list) or the `validate_recipe` output (enriched steps).
6. Live evidence files stored under `.agent/tasks/phase-7-nl-translator/raw/` must be
   sanitized before committing.
7. No changes to existing operator workflow builders or `WORKFLOWS` dict. Phase 7 is additive.
8. The full unittest suite must remain green throughout development.

---

## Non-goals / out-of-scope

- **PTZ control** — no PTZ workflow exists in `WORKFLOWS`; PTZ intents must produce a
  structured `unsupported_intent` gap, not a fabricated workflow.
- **User/role/permission management** — no role or permission workflow exists in `WORKFLOWS`;
  these intents must produce a structured gap.
- **New operator workflow builders** — Phase 7 does not add new entries to `WORKFLOWS`. If a
  gap is discovered, it is recorded and deferred to a future phase.
- **LLM-backed intent parsing** — the intent parser uses deterministic keyword/pattern
  matching or a local rule table. No external LLM API calls from within `assemble_recipe`.
- **Persistent or destructive live applies** — `archive_format_volume`, `archive_reindex`,
  `delete_*` workflows are validated but not applied in AC8.
- **Modifying existing tests** — existing passing tests must not be changed to accommodate
  the new module.

---

## Assumptions

- A1: `OperatorRegistry.plan()` is safe to call with arbitrary params in tests when backed by
  a stub that returns `{"status": "planned", "plan_id": "stub-1", ...}`. The dry-run contract
  is already established in the operator module.
- A2: The intent-to-workflow mapping table is defined as a module-level constant (dict or
  list of rules) inside `axxon_mcp_translator.py`, not loaded from an external file.
- A3: `explain_recipe` wall-clock estimates are static strings keyed by risk class (e.g.
  `"mutation"` -> `"~5-30 seconds per step"`). No per-workflow timing data is required.
- A4: The `context` argument to `assemble_recipe` is an optional dict used to supply
  fixture values (e.g. `{"camera_uid": "...", "host": "hosts/Server"}`). Absent context keys
  that are required by a workflow result in a gap, not an exception.
- A5: The three MCP tool names registered are `assemble_recipe`, `validate_recipe`, and
  `explain_recipe` (snake_case, matching the method names).

---

## Verification plan

| Step | Command / check | Pass condition |
|---|---|---|
| V1 | `python3.12 -c "from axxon_mcp_translator import AxxonMcpTranslator; print('ok')"` run from `tools/` | Exits 0, prints "ok" |
| V2 | `python3.12 -m unittest tools/tests/test_axxon_mcp_translator.py -v` | All tests pass |
| V3 | `python3.12 -m unittest discover -s tools/tests` | Exits 0, count > 629 |
| V4 | Grep `WORKFLOWS` keys against every `step["workflow"]` in assemble_recipe outputs for all 10 reference intents | No unknown workflow name found |
| V5 | Call `assemble_recipe("set PTZ preset 2 for camera X", {})` and `assemble_recipe("assign admin role to user Y", {})` | Both return `status=="unsupported_intent"` |
| V6 | Import `tools/axxon_mcp_server.py`; call `create_server(translator=None)` and verify tool names absent; call `create_server(translator=stub)` and verify tool names present | Assertion passes for both cases |
| V7 | Live: run the 3 ephemeral recipe round-trips against `<demo-host>` and capture stdout | All rollback steps return `status=="rolled_back"` or equivalent success; verify_operator_plan confirms absence |
| V8 | Review sanitized evidence files: no IP addresses, no credentials, no real UIDs | Manual review passes |
