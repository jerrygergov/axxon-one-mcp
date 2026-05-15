# Axxon One API Comprehensive Test Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion before reporting completion.

**Goal:** Build and run a repeatable gRPC/HTTP API probe against the local Axxon One test server.

**Architecture:** Use generated Python gRPC stubs from the local proto bundle and HTTP calls through the web server. Keep credentials in environment variables, sanitize secrets from reports, and write a Markdown test report under `arm64-docker/docs/api-test-runs`.

**Tech Stack:** Python, grpcio, grpcio-tools, Axxon One local proto files, HTTP `/grpc`, REST-transcoded endpoints.

---

## Tasks

### Task 1: Reusable Probe

**Files:**
- Create: `arm64-docker/tools/axxon_api_probe.py`
- Create output directory: `arm64-docker/docs/api-test-runs`

**Steps:**

1. Generate Python stubs from `arm64-docker/docs/grpc-proto-files` into `/tmp/axxon-grpc-py` if they do not already exist.
2. Connect to direct TLS gRPC on `127.0.0.1:20109` with CN override `F4E66972EC19`.
3. Authenticate with `AuthenticationService.AuthenticateEx2`.
4. Run read-only gRPC probes for domain, configuration, archive, metadata, export, license, statistics, and event history.
5. Run a safe write/read/remove probe through `SharedKVStorageService`.
6. Run HTTP `/grpc` and REST-transcoded endpoint probes through `http://127.0.0.1:8000`.
7. Write sanitized JSON and Markdown reports.

### Task 2: Execute Against Local Server

**Commands:**

```bash
AXXON_USERNAME=root AXXON_PASSWORD='...' /tmp/axxon-grpc-venv/bin/python \
  arm64-docker/tools/axxon_api_probe.py
```

Expected:

- Container remains healthy.
- Direct gRPC authentication passes.
- HTTP `/grpc` authentication passes.
- Metadata stream returns object tracklets from `AVDetector.2`.
- SharedKV write/read/remove passes.
- Report is written under `arm64-docker/docs/api-test-runs`.

### Task 3: Verify

**Commands:**

```bash
test -s arm64-docker/docs/api-test-runs/latest.md
test -s arm64-docker/docs/api-test-runs/latest.json
docker inspect -f '{{.State.Health.Status}}' axxon-one-arm64
```

Expected:

- Report files exist.
- Container health is `healthy`.
- Any failed or warning cases are explained in the report.
