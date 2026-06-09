# Phase E — NL→plan translator depth (live verification)

**Date:** 2026-06-09
**Target:** `%3Cdemo-host%3E` (HTTP `/grpc` bridge; reads need no CA)
**Module:** `tools/axxon_mcp_translator.py` (the `translator` group)
**Scope:** three sequenced sub-features — devices_catalog wiring, broadened intents, end-to-end
`run_recipe`. Live run via a Sonnet sub-agent; **no mutations** (`run_recipe` apply=False / refused).

## What shipped

1. **`resolve_device(vendor, model)`** — validates a vendor/model pair against the live
   `devices_catalog` (`ok` / `gap`+suggestions / `virtual`). Suggestions prefer fuzzy matches and
   fall back to the vendor's real model list.
2. **`assemble_recipe` device resolution** — a camera intent naming a vendor/model resolves it at
   assemble time: a known pair flows the validated vendor/model into the `create_camera` step; an
   unknown pair returns `status: device_unresolved` with suggestions (no silent Virtual fallback).
   Camera intents with no vendor/model keep the prior Virtual-default behavior.
3. **Broadened intents** — new rules: "schedule an export every night" → `create_macro`;
   "raise a … alarm/event …" → `external_event_inject`. New rules reference only registered
   workflows.
4. **`run_recipe(intent, context, confirmation, apply=False)`** — assemble → validate → optional
   gated apply. Default dry (zero mutations); apply requires `confirmation=CONFIRM-run-recipe`,
   refuses on any gap step, and surfaces rollback tokens per applied step.

## Live verification — 9/9 PASS

Real (vendor, model) discovered at runtime: `("3S", "N1011")`.

| Check | Verdict | Detail |
| --- | --- | --- |
| resolve_device(3S, N1011) | PASS | status=ok; traits returned |
| resolve_device(3S, ZZZ-9999) | PASS | status=gap; suggestions = vendor's real models (N1011, N1031, N1072, …) |
| resolve_device(NotARealVendor, x) | PASS | status=gap; fuzzy vendor suggestion from 318-vendor catalog |
| resolve_device("", "") | PASS | status=virtual |
| assemble_recipe (known device) | PASS | create_camera step carries vendor=3S, model=N1011 |
| assemble_recipe (unknown model) | PASS | status=device_unresolved + suggestions |
| validate_recipe (assembled) | PASS | valid=True, step planned |
| run_recipe(apply=False) | PASS | mode=dry, zero mutations |
| run_recipe(apply=True, confirmation="") | PASS | refused (status=gap), no mutation |

**No camera or object was created on the stand.** The live `devices_catalog` response shapes match
what `resolve_device` expects (no shape mismatch observed).

## Sanitization

Host → `%3Cdemo-host%3E`, credentials → `%3Credacted%3E`. `AXXON_TLS_CN=Server` retained. No
proto / CA / credentials / symlink committed.
