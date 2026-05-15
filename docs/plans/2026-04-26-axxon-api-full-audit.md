# Axxon API Full Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Audit every Axxon One gRPC and HTTP API one by one, with live checks where safe, so plugin and vertical integration work has reliable reference docs.

**Architecture:** Treat local proto files as the source of truth, generate machine-readable catalogs, then audit services in staged passes. Direct gRPC is the primary live-test path; HTTP `/grpc` and annotated `/v1/...` endpoints are tested for parity where practical. Mutating/destructive APIs are not executed until a dedicated fixture and rollback procedure exist.

**Tech Stack:** Python 3.12, `grpcio`, `grpcio-tools`, generated protobuf stubs, local Axxon One Docker container, Markdown/CSV docs.

---

## Scope

- gRPC proto files: `arm64-docker/docs/grpc-proto-files/axxonsoft/**/*.proto`
- Converted API PDF: `arm64-docker/docs/integration-apis-3.0`
- HTTP annotations: `google.api.http` options in local protos
- HTTP wrapper: `POST /grpc`
- REST-style HTTP endpoints under `/v1/...`
- Current live test server: `127.0.0.1:8000` and `127.0.0.1:20109`

## Audit Phases

### Phase 1: Source-Of-Truth Catalog

**Files:**
- Create: `arm64-docker/tools/generate_api_catalog.py`
- Create: `arm64-docker/docs/api-audit/README.md`
- Create: `arm64-docker/docs/api-audit/grpc-api-catalog.md`
- Create: `arm64-docker/docs/api-audit/grpc-api-catalog.csv`
- Create: `arm64-docker/docs/api-audit/http-endpoints-catalog.md`

**Steps:**

1. Parse all Axxon proto files.
2. Extract package, service, method, request, response, streaming direction, and proto path.
3. Extract HTTP annotations from `google.api.http`.
4. Heuristically classify each RPC as `read`, `stream_read`, `mutating`, or `review`.
5. Mark already live-tested methods from existing probe/event-search work.
6. Generate Markdown and CSV outputs.
7. Verify counts against `SERVICE_INDEX.md`.

### Phase 2: Existing Live-Test Coverage Map

**Files:**
- Modify: `arm64-docker/docs/api-audit/grpc-api-catalog.md`
- Modify: `arm64-docker/docs/api-audit/README.md`
- Read: `arm64-docker/docs/api-test-runs/latest.json`
- Read: `arm64-docker/docs/api-test-runs/event-search-latest.json`

**Steps:**

1. Map comprehensive probe methods to full gRPC method names.
2. Map event-search methods to full gRPC method names.
3. Record pass/empty/safe-record states.
4. Document every live-tested method and the command that tests it.

### Phase 3: Read-Only gRPC Sweep

**Files:**
- Create: `arm64-docker/tools/axxon_readonly_sweep.py`
- Create: `arm64-docker/docs/api-audit/live-readonly-sweep-latest.json`
- Modify: `arm64-docker/docs/api-audit/grpc-api-catalog.md`

**Steps:**

1. Build a registry of safe request constructors for read-only methods.
2. Run service-by-service read-only tests.
3. Record response shape, item counts, errors, empty results, and unavailable services.
4. Skip methods that need external fixtures or long-lived streams unless the test can time-box cleanly.
5. Update docs with live status.

### Phase 4: HTTP `/grpc` Parity Sweep

**Files:**
- Create: `arm64-docker/tools/axxon_http_grpc_sweep.py`
- Create: `arm64-docker/docs/api-audit/http-grpc-sweep-latest.json`
- Modify: `arm64-docker/docs/api-audit/grpc-api-catalog.md`

**Steps:**

1. Authenticate through HTTP `/grpc`.
2. For each read-only request fixture from Phase 3, execute the same method through `/grpc`.
3. Parse JSON, multipart, and `text/event-stream` responses.
4. Compare status, response shape, and key counts with direct gRPC.
5. Record wrapper-specific quirks.

### Phase 5: REST `/v1/...` Endpoint Sweep

**Files:**
- Create: `arm64-docker/tools/axxon_http_v1_sweep.py`
- Create: `arm64-docker/docs/api-audit/http-v1-sweep-latest.json`
- Modify: `arm64-docker/docs/api-audit/http-endpoints-catalog.md`

**Steps:**

1. Use the HTTP endpoint catalog from proto annotations.
2. Execute safe GET endpoints with minimal parameters only where a valid fixture exists.
3. Execute safe POST read endpoints only where request body is known and non-mutating.
4. Do not execute mutating endpoints by default.
5. Record status codes, response types, auth requirements, and missing-parameter behavior.

### Phase 6: Mutating API Fixture Design

**Files:**
- Create: `arm64-docker/docs/api-audit/mutating-api-fixtures.md`

**Steps:**

1. Group mutating methods by risk: safe temporary object, reversible config, irreversible/destructive.
2. Define isolated fixtures for bookmarks, SharedKV, maps/layouts if possible.
3. Define pre/post snapshots and rollback steps.
4. Require explicit user approval before running destructive tests.

### Phase 7: Integration Playbooks

**Files:**
- Create: `arm64-docker/docs/api-audit/integration-playbooks.md`

**Steps:**

1. Write plugin patterns for authentication, inventory, events, media, metadata, archive, export, PTZ, security, and configuration.
2. For each vertical integration, list recommended APIs and avoid-list APIs.
3. Document known local-server quirks and production considerations.

## Current First Pass Status

- Catalog generator created.
- Existing live-tested gRPC methods are seeded into the catalog from current probe/event-search knowledge.
- Full live read-only sweep is still pending.
- Mutating API tests are intentionally gated.
