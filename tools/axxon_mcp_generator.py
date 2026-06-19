#!/usr/bin/env python3
"""Phase 4 integration generator for the Axxon One MCP server.

Generates standalone Python integration bundles from the verified MCP corpus.
The generator is pure stdlib: it reads corpus JSON, renders string templates,
and returns a `GeneratedBundle` mapping. It never writes to disk directly;
the calling MCP tool decides the output directory.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_DIR = REPO_ROOT / "docs" / "api-audit" / "mcp-corpus"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

DEFAULT_DURATION_SECONDS = 30
DEFAULT_EVENT_COUNT = 500
DEFAULT_HTTP_BYTE_CAP = 1_048_576
DEFAULT_EXPORT_WINDOW_SECONDS = 3600
DEFAULT_EXPORT_BYTE_CAP = 50 * 1024 * 1024
DEFAULT_SCHEDULE_INTERVAL_SECONDS = 300
MIN_INTERVAL_SECONDS = 60
MAX_SCHEDULED_RUNS = 100
DEFAULT_SCHEDULED_RUNS = 12
MAX_PTZ_MAGNITUDE = 1.0
MAX_PTZ_HOLD_MS = 5000
DEFAULT_PTZ_HOLD_MS = 800

ALLOWED_IMPORTS = {
    "grpc",
    "requests",
    "os",
    "sys",
    "json",
    "time",
    "logging",
    "argparse",
    "dataclasses",
    "pathlib",
    "typing",
    "datetime",
    "re",
    "uuid",
    "unittest",
    "main",
    "axxonsoft",
    "google",
    "__future__",
}

SECRET_PATTERNS = [
    re.compile(r"AXXON_PASSWORD\s*=\s*['\"][^'\"<]+"),
    re.compile(r"password\s*[=:]\s*['\"][^'\"<]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
]


@dataclass
class GenerationRequest:
    template: str
    params: dict[str, Any] = field(default_factory=dict)
    allow_mutation: bool = False
    allow_large: bool = False
    language: str = "python"


@dataclass
class GeneratedBundle:
    template: str
    files: dict[str, str]
    required_fixtures: list[str] = field(default_factory=list)
    required_env: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class GenerationRefusal:
    template: str
    reason: str
    detail: str = ""


@dataclass
class TemplateInfo:
    name: str
    summary: str
    required_params: list[str]
    required_fixtures: list[str]
    required_env: list[str]
    languages: list[str] = field(default_factory=lambda: ["python"])


TEMPLATE_CATALOG: list[TemplateInfo] = [
    TemplateInfo(
        name="grpc_consumer",
        summary="Direct gRPC consumer for a single method (AuthenticateEx2 + one call).",
        required_params=["fqmn"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="http_grpc_consumer",
        summary="HTTP /grpc consumer for a single method using Bearer auth.",
        required_params=["fqmn"],
        required_fixtures=[],
        required_env=["AXXON_HTTP_URL", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="legacy_http_consumer",
        summary="Legacy HTTP consumer for a verified path (Bearer or Basic).",
        required_params=["path"],
        required_fixtures=[],
        required_env=["AXXON_HTTP_URL", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="event_consumer",
        summary="Bounded detector-event consumer (DomainNotifier.PullEvents).",
        required_params=["subject"],
        required_fixtures=["event-supplier-subject"],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="external_event_producer",
        summary="External event producer for a real DetectorEx.* fixture.",
        required_params=["access_point", "event_type"],
        required_fixtures=["detector-ex"],
        required_env=["AXXON_HTTP_URL", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="export_job",
        summary="Archive export job (start/poll/download/destroy) with cleanup.",
        required_params=["camera_ap", "begin", "end"],
        required_fixtures=["mm-export-agent"],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="webhook_bridge",
        summary="Forward bounded detector events to an external webhook URL.",
        required_params=["subject"],
        required_fixtures=["event-supplier-subject"],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD", "WEBHOOK_URL"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="inventory_sync",
        summary="One-shot inventory snapshot (ListCameras + ListUnits) to a JSON file.",
        required_params=["output_path"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="alarm_responder",
        summary="Bounded alarm responder: read a camera's active alerts, run BeginAlertReview -> CompleteAlertReview lifecycle.",
        required_params=["camera_ap"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="scheduled_exporter",
        summary="Bounded scheduled loop that polls ExportService.ListSessions for a camera every interval.",
        required_params=["camera_ap"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="ml_detector_bridge",
        summary="Bridge external ML inference results into Axxon via ExternalDetectorService.RaiseOccasionalEvent.",
        required_params=["access_point", "results_path"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="dashboard_backend",
        summary="Read-only dashboard snapshot (ListCameras + GetActiveAlerts + ReadEvents) to a JSON file.",
        required_params=["output_path"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="plugin_scaffold",
        summary="Runnable plugin repo skeleton (auth + ListCameras, retry, env loader, test, CI, README, LICENSE).",
        required_params=["name"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
    TemplateInfo(
        name="ptz_controller",
        summary="Bounded PTZ controller: acquire a telemetry session, read start position, do one bounded move, then restore the start position and release. Requires a PTZ-capable TelemetryControl access point.",
        required_params=["telemetry_ap"],
        required_fixtures=["ptz-telemetry-control"],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
        languages=["python", "node"],
    ),
]


def allow_in_repo_write(target: Path, allow: bool) -> bool:
    """Return True if generation may write to `target`.

    Writes inside the repo root are refused unless `allow` is True.
    """
    target = target.resolve()
    try:
        target.relative_to(REPO_ROOT)
    except ValueError:
        return True
    return allow


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _read_template(name: str) -> str:
    path = TEMPLATES_DIR / f"{name}.py.tmpl"
    return path.read_text(encoding="utf-8")


def _read_aux_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


def _read_ts_template(name: str) -> str:
    path = TEMPLATES_DIR / f"{name}.ts.tmpl"
    return path.read_text(encoding="utf-8")


def _ts_package_json(title: str) -> str:
    return json.dumps(
        {
            "name": re.sub(r"[^a-z0-9\-]", "-", title.lower())[:50],
            "version": "1.0.0",
            "description": f"Generated Axxon One integration: {title}",
            "main": "dist/src/index.js",
            "scripts": {
                "build": "tsc -p tsconfig.json",
                "test": "npm run build --silent && node dist/test/smoke.test.js",
                "start": "node dist/src/index.js",
            },
            "dependencies": {"@grpc/grpc-js": "^1.10.0", "@grpc/proto-loader": "^0.7.0"},
            "devDependencies": {"typescript": "^5.0.0", "@types/node": "^20.0.0"},
        },
        indent=2,
    ) + "\n"


def _tsconfig_json() -> str:
    return json.dumps(
        {
            "compilerOptions": {
                "target": "ES2022",
                "module": "CommonJS",
                "moduleResolution": "Node",
                "rootDir": ".",
                "outDir": "dist",
                "strict": True,
                "esModuleInterop": True,
                "skipLibCheck": True,
            },
            "include": ["src/**/*.ts", "test/**/*.ts"],
        },
        indent=2,
    ) + "\n"


def _readme(title: str, template: str, language: str) -> str:
    filename = "README.node.md.tmpl" if language == "node" else "README.md.tmpl"
    return _render(_read_aux_template(filename), {"TITLE": title, "TEMPLATE": template})


def _render(template_text: str, values: dict[str, Any]) -> str:
    return Template(template_text).safe_substitute(values)


def _env_example(env_names: list[str]) -> str:
    lines = ["# Copy to .env and fill in. Never commit real credentials."]
    placeholders = {
        "AXXON_HOST": "<host>:20109",
        "AXXON_TLS_CN": "Server",
        "AXXON_USERNAME": "<username>",
        "AXXON_PASSWORD": "<password>",
        "AXXON_HTTP_URL": "http://<host>",
        "AXXON_CA": "<path-to-ca.crt>",
    }
    lines.extend(f"{name}={placeholders.get(name, '<value>')}" for name in env_names)
    return "\n".join(lines) + "\n"


def _ci_workflow(name: str, language: str) -> str:
    if language == "node":
        steps = (
            "      - uses: actions/setup-node@v4\n"
            "        with:\n"
            "          node-version: '20'\n"
            "      - run: npm ci\n"
            "      - run: npm run build\n"
            "      - run: npm test\n"
        )
    else:
        steps = (
            "      - uses: actions/setup-python@v5\n"
            "        with:\n"
            "          python-version: '3.12'\n"
            "      - run: pip install -r requirements.txt\n"
            "      - run: python -m unittest discover\n"
        )
    return (
        f"name: {name}-ci\n"
        "on: [push, pull_request]\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        f"{steps}"
    )


def _license_placeholder() -> str:
    return (
        "Copyright (c) 2026 <copyright holder>\n\n"
        "Permission is hereby granted to use this generated scaffold. Replace this file with\n"
        "your chosen license before distribution.\n"
    )


class Generator:
    """Pure generator over the MCP corpus."""

    def __init__(self, corpus_dir: Path = DEFAULT_CORPUS_DIR) -> None:
        self.corpus_dir = corpus_dir
        self.methods = _load_json(corpus_dir / "api_methods.json", {"methods": []}).get("methods", [])
        self.endpoints = _load_json(corpus_dir / "http_endpoints.json", {"endpoints": []}).get("endpoints", [])
        self.known_behaviors = _load_json(corpus_dir / "known_behaviors.json", {})
        self.safety = _load_json(corpus_dir / "safety_policies.json", {})

    def list_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "name": info.name,
                "summary": info.summary,
                "required_params": info.required_params,
                "required_fixtures": info.required_fixtures,
                "required_env": info.required_env,
                "languages": info.languages,
            }
            for info in TEMPLATE_CATALOG
        ]

    def _find_method(self, fqmn: str) -> dict[str, Any] | None:
        for m in self.methods:
            if m.get("fqmn") == fqmn:
                return m
        return None

    def _find_endpoint(self, path: str) -> dict[str, Any] | None:
        for e in self.endpoints:
            if e.get("path") == path:
                return e
        return None

    def _info(self, name: str) -> TemplateInfo:
        for info in TEMPLATE_CATALOG:
            if info.name == name:
                return info
        raise KeyError(name)

    def plan(self, request: GenerationRequest) -> GeneratedBundle | GenerationRefusal:
        try:
            info = self._info(request.template)
        except KeyError:
            return GenerationRefusal(request.template, "unknown_template", request.template)
        missing = [p for p in info.required_params if p not in request.params]
        if missing:
            return GenerationRefusal(request.template, "missing_params", ", ".join(missing))
        if request.language not in info.languages:
            return GenerationRefusal(
                request.template,
                "unsupported_language",
                f"template {request.template!r} supports {info.languages}; got {request.language!r}",
            )
        return self._dispatch(request, info)

    def generate(self, request: GenerationRequest) -> GeneratedBundle | GenerationRefusal:
        return self.plan(request)

    def _dispatch(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        if request.template == "grpc_consumer":
            return self._build_grpc_consumer(request, info)
        if request.template == "http_grpc_consumer":
            return self._build_http_grpc_consumer(request, info)
        if request.template == "legacy_http_consumer":
            return self._build_legacy_http_consumer(request, info)
        if request.template == "event_consumer":
            return self._build_event_consumer(request, info)
        if request.template == "external_event_producer":
            return self._build_external_event_producer(request, info)
        if request.template == "export_job":
            return self._build_export_job(request, info)
        if request.template == "webhook_bridge":
            return self._build_webhook_bridge(request, info)
        if request.template == "inventory_sync":
            return self._build_inventory_sync(request, info)
        if request.template == "alarm_responder":
            return self._build_alarm_responder(request, info)
        if request.template == "scheduled_exporter":
            return self._build_scheduled_exporter(request, info)
        if request.template == "ml_detector_bridge":
            return self._build_ml_detector_bridge(request, info)
        if request.template == "dashboard_backend":
            return self._build_dashboard_backend(request, info)
        if request.template == "plugin_scaffold":
            return self._build_plugin_scaffold(request, info)
        if request.template == "ptz_controller":
            return self._build_ptz_controller(request, info)
        return GenerationRefusal(request.template, "unknown_template", request.template)

    def _build_grpc_consumer(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        fqmn = request.params["fqmn"]
        method = self._find_method(fqmn)
        if method is None:
            return GenerationRefusal(request.template, "unknown_method", fqmn)
        safety = method.get("safety_class", "")
        if safety not in {"safe-read", "read"} and not request.allow_mutation:
            return GenerationRefusal(
                request.template,
                "refused_mutation",
                f"{fqmn} safety_class={safety}; pass allow_mutation=True to override",
            )
        package = method.get("package", "")
        service = method.get("service", "")
        method_name = method.get("method", "")
        request_type = method.get("request", "")
        proto = method.get("proto", "")
        values = {
            "FQMN": fqmn,
            "PACKAGE": package,
            "SERVICE": service,
            "METHOD": method_name,
            "REQUEST_TYPE": request_type,
            "PROTO": proto,
            "DURATION": str(DEFAULT_DURATION_SECONDS),
        }
        readme = _readme(fqmn, "grpc_consumer", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("grpc_consumer"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(fqmn),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("grpc_consumer"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
        )

    def _build_http_grpc_consumer(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        fqmn = request.params["fqmn"]
        method = self._find_method(fqmn)
        if method is None:
            return GenerationRefusal(request.template, "unknown_method", fqmn)
        safety = method.get("safety_class", "")
        if safety not in {"safe-read", "read"} and not request.allow_mutation:
            return GenerationRefusal(
                request.template,
                "refused_mutation",
                f"{fqmn} safety_class={safety}; pass allow_mutation=True to override",
            )
        values = {
            "FQMN": fqmn,
            "SERVICE_PATH": fqmn.rsplit(".", 1)[0],
            "METHOD": fqmn.rsplit(".", 1)[1],
            "DURATION": str(DEFAULT_DURATION_SECONDS),
            "BYTE_CAP": str(DEFAULT_HTTP_BYTE_CAP),
        }
        readme = _readme(fqmn, "http_grpc_consumer", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("http_grpc_consumer"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(fqmn),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("http_grpc_consumer"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "requests>=2.31\n",
            },
            required_env=info.required_env,
        )

    def _build_legacy_http_consumer(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        path = request.params["path"]
        endpoint = self._find_endpoint(path)
        if endpoint is None:
            return GenerationRefusal(request.template, "unknown_endpoint", path)
        live_status = endpoint.get("live_status", "")
        if not live_status.startswith("tested-pass") and live_status != "verified":
            return GenerationRefusal(
                request.template,
                "unverified_endpoint",
                f"{path} live_status={live_status}",
            )
        verb = endpoint.get("verb", "GET")
        auth_mode = endpoint.get("auth_mode") or "bearer"
        values = {
            "PATH": path,
            "VERB": verb,
            "AUTH_MODE": auth_mode,
            "DURATION": str(DEFAULT_DURATION_SECONDS),
            "BYTE_CAP": str(DEFAULT_HTTP_BYTE_CAP),
        }
        readme = _readme(path, "legacy_http_consumer", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("legacy_http_consumer"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(path),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("legacy_http_consumer"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "requests>=2.31\n",
            },
            required_env=info.required_env,
        )

    def _build_event_consumer(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        subject = request.params["subject"]
        duration = int(request.params.get("duration", DEFAULT_DURATION_SECONDS))
        count = int(request.params.get("count", DEFAULT_EVENT_COUNT))
        if duration > DEFAULT_DURATION_SECONDS or count > DEFAULT_EVENT_COUNT:
            return GenerationRefusal(
                request.template,
                "cap_exceeded",
                f"duration<= {DEFAULT_DURATION_SECONDS}s, count<= {DEFAULT_EVENT_COUNT}",
            )
        notes: list[str] = []
        if "AVDetector." in subject and "AppDataDetector." not in subject:
            notes.append(
                "Subject is a parent AVDetector. Semantic analytics live on child AppDataDetector subjects; "
                "the generated script logs this recommendation at startup."
            )
        values = {
            "SUBJECT": subject,
            "DURATION": str(duration),
            "COUNT": str(count),
            "APPDATA_HINT": "True" if notes else "False",
        }
        readme = _readme(subject, "event_consumer", request.language)
        if request.language == "node":
            ts_values = dict(values)
            ts_values["APPDATA_HINT"] = "true" if notes else "false"
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("event_consumer"), ts_values),
                    "README.md": readme,
                    "package.json": _ts_package_json(subject),
                },
                required_env=info.required_env,
                required_fixtures=info.required_fixtures,
                notes=notes,
            )
        body = _render(_read_template("event_consumer"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
            required_fixtures=info.required_fixtures,
            notes=notes,
        )

    def _build_external_event_producer(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        ap = request.params["access_point"]
        event_type = request.params["event_type"]
        if event_type not in {"Event1", "Event2", "TargetList"}:
            return GenerationRefusal(request.template, "unknown_event_type", event_type)
        values = {
            "ACCESS_POINT": ap,
            "EVENT_TYPE": event_type,
            "DURATION": str(DEFAULT_DURATION_SECONDS),
            "BYTE_CAP": str(DEFAULT_HTTP_BYTE_CAP),
        }
        readme = _readme(ap, "external_event_producer", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("external_event_producer"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(ap),
                },
                required_env=info.required_env,
                required_fixtures=info.required_fixtures,
            )
        body = _render(_read_template("external_event_producer"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "requests>=2.31\n",
            },
            required_env=info.required_env,
            required_fixtures=info.required_fixtures,
        )

    def _build_export_job(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        camera = request.params["camera_ap"]
        begin = request.params["begin"]
        end = request.params["end"]
        window = int(request.params.get("window_seconds", DEFAULT_EXPORT_WINDOW_SECONDS))
        if window > DEFAULT_EXPORT_WINDOW_SECONDS and not request.allow_large:
            return GenerationRefusal(
                request.template,
                "window_too_large",
                f"window={window}s exceeds {DEFAULT_EXPORT_WINDOW_SECONDS}s; pass allow_large=True",
            )
        fmt = request.params.get("format", "mp4")
        if fmt not in {"mp4", "jpeg"}:
            return GenerationRefusal(request.template, "unsupported_format", fmt)
        values = {
            "CAMERA_AP": camera,
            "BEGIN": begin,
            "END": end,
            "FORMAT": fmt,
            "BYTE_CAP": str(DEFAULT_EXPORT_BYTE_CAP),
            "WINDOW": str(window),
        }
        readme = _readme(camera, "export_job", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("export_job"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(camera),
                },
                required_env=info.required_env,
                required_fixtures=info.required_fixtures,
            )
        body = _render(_read_template("export_job"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
            required_fixtures=info.required_fixtures,
        )

    def _build_webhook_bridge(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        subject = request.params["subject"]
        duration = int(request.params.get("duration", DEFAULT_DURATION_SECONDS))
        count = int(request.params.get("count", DEFAULT_EVENT_COUNT))
        if duration > DEFAULT_DURATION_SECONDS or count > DEFAULT_EVENT_COUNT:
            return GenerationRefusal(
                request.template,
                "cap_exceeded",
                f"duration<= {DEFAULT_DURATION_SECONDS}s, count<= {DEFAULT_EVENT_COUNT}",
            )
        values = {
            "SUBJECT": subject,
            "DURATION": str(duration),
            "COUNT": str(count),
        }
        readme = _readme(subject, "webhook_bridge", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("webhook_bridge"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(subject),
                },
                required_env=info.required_env,
                required_fixtures=info.required_fixtures,
            )
        body = _render(_read_template("webhook_bridge"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\nrequests>=2.31\n",
            },
            required_env=info.required_env,
            required_fixtures=info.required_fixtures,
        )

    def _build_inventory_sync(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        output_path = request.params["output_path"]
        values = {
            "OUTPUT_PATH": output_path,
            "BYTE_CAP": str(DEFAULT_EXPORT_BYTE_CAP),
        }
        readme = _readme(output_path, "inventory_sync", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("inventory_sync"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(output_path),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("inventory_sync"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
        )

    def _build_alarm_responder(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        if not request.allow_mutation:
            return GenerationRefusal(
                request.template,
                "refused_mutation",
                "alarm review lifecycle is mutating; pass allow_mutation=True to override",
            )
        camera = request.params["camera_ap"]
        operator = request.params.get("operator", "axxon-mcp")
        duration = int(request.params.get("duration", DEFAULT_DURATION_SECONDS))
        count = int(request.params.get("count", DEFAULT_EVENT_COUNT))
        if duration > DEFAULT_DURATION_SECONDS or count > DEFAULT_EVENT_COUNT:
            return GenerationRefusal(
                request.template,
                "cap_exceeded",
                f"duration<= {DEFAULT_DURATION_SECONDS}s, count<= {DEFAULT_EVENT_COUNT}",
            )
        values = {
            "CAMERA_AP": camera,
            "OPERATOR": operator,
            "DURATION": str(duration),
            "COUNT": str(count),
        }
        readme = _readme(camera, "alarm_responder", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("alarm_responder"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(camera),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("alarm_responder"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
        )

    def _build_ptz_controller(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        if not request.allow_mutation:
            return GenerationRefusal(
                request.template,
                "refused_mutation",
                "PTZ control moves a physical camera; pass allow_mutation=True to override",
            )
        ap = request.params["telemetry_ap"]
        pan = float(request.params.get("pan", 0.1))
        tilt = float(request.params.get("tilt", 0.0))
        hold_ms = int(request.params.get("hold_ms", DEFAULT_PTZ_HOLD_MS))
        if abs(pan) > MAX_PTZ_MAGNITUDE or abs(tilt) > MAX_PTZ_MAGNITUDE or hold_ms > MAX_PTZ_HOLD_MS:
            return GenerationRefusal(
                request.template,
                "cap_exceeded",
                f"|pan|,|tilt|<= {MAX_PTZ_MAGNITUDE}, hold_ms<= {MAX_PTZ_HOLD_MS}",
            )
        values = {"TELEMETRY_AP": ap, "PAN": str(pan), "TILT": str(tilt), "HOLD_MS": str(hold_ms)}
        readme = _readme(ap, "ptz_controller", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("ptz_controller"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(ap),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("ptz_controller"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
        )

    def _build_scheduled_exporter(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        camera = request.params["camera_ap"]
        interval = int(request.params.get("interval", DEFAULT_SCHEDULE_INTERVAL_SECONDS))
        max_runs = int(request.params.get("max_runs", DEFAULT_SCHEDULED_RUNS))
        if interval < MIN_INTERVAL_SECONDS or max_runs > MAX_SCHEDULED_RUNS:
            return GenerationRefusal(
                request.template,
                "cap_exceeded",
                f"interval>= {MIN_INTERVAL_SECONDS}s, max_runs<= {MAX_SCHEDULED_RUNS}",
            )
        values = {
            "CAMERA_AP": camera,
            "INTERVAL": str(interval),
            "MAX_RUNS": str(max_runs),
            "BYTE_CAP": str(DEFAULT_EXPORT_BYTE_CAP),
        }
        readme = _readme(camera, "scheduled_exporter", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("scheduled_exporter"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(camera),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("scheduled_exporter"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
        )

    def _build_ml_detector_bridge(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        if not request.allow_mutation:
            return GenerationRefusal(
                request.template,
                "refused_mutation",
                "raising detector events is mutating; pass allow_mutation=True to override",
            )
        access_point = request.params["access_point"]
        results_path = request.params["results_path"]
        duration = int(request.params.get("duration", DEFAULT_DURATION_SECONDS))
        count = int(request.params.get("count", DEFAULT_EVENT_COUNT))
        if duration > DEFAULT_DURATION_SECONDS or count > DEFAULT_EVENT_COUNT:
            return GenerationRefusal(
                request.template,
                "cap_exceeded",
                f"duration<= {DEFAULT_DURATION_SECONDS}s, count<= {DEFAULT_EVENT_COUNT}",
            )
        values = {
            "ACCESS_POINT": access_point,
            "RESULTS_PATH": results_path,
            "DURATION": str(duration),
            "COUNT": str(count),
        }
        readme = _readme(access_point, "ml_detector_bridge", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("ml_detector_bridge"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(access_point),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("ml_detector_bridge"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
        )

    def _build_dashboard_backend(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        output_path = request.params["output_path"]
        values = {
            "OUTPUT_PATH": output_path,
            "BYTE_CAP": str(DEFAULT_EXPORT_BYTE_CAP),
        }
        readme = _readme(output_path, "dashboard_backend", request.language)
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("dashboard_backend"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(output_path),
                },
                required_env=info.required_env,
            )
        body = _render(_read_template("dashboard_backend"), values)
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
        )

    def _build_plugin_scaffold(self, request: GenerationRequest, info: TemplateInfo) -> GeneratedBundle | GenerationRefusal:
        name = request.params["name"]
        values = {"NAME": name}
        readme = _readme(name, "plugin_scaffold", request.language)
        env_example = _env_example(info.required_env)
        license_text = _license_placeholder()
        if request.language == "node":
            return GeneratedBundle(
                template=request.template,
                files={
                    "src/index.ts": _render(_read_ts_template("plugin_scaffold"), values),
                    "test/smoke.test.ts": _render(_read_aux_template("plugin_scaffold.test.ts.tmpl"), values),
                    "README.md": readme,
                    "package.json": _ts_package_json(name),
                    "tsconfig.json": _tsconfig_json(),
                    ".env.example": env_example,
                    ".github/workflows/ci.yml": _ci_workflow(name, "node"),
                    "LICENSE": license_text,
                },
                required_env=info.required_env,
            )
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": _render(_read_template("plugin_scaffold"), values),
                "test_smoke.py": _render(_read_aux_template("plugin_scaffold.test.py.tmpl"), values),
                "README.md": readme,
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
                ".env.example": env_example,
                ".github/workflows/ci.yml": _ci_workflow(name, "python"),
                "LICENSE": license_text,
            },
            required_env=info.required_env,
        )


@dataclass
class VerificationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


TS_DISALLOWED_IMPORTS = re.compile(
    r"""(?:import\s.*?from\s+['"]|require\s*\(\s*['"])(child_process|shelljs|execa|cross-spawn)['"]"""
)
TS_DISALLOWED_PATTERNS = re.compile(r"""\beval\s*\(|\bnew\s+Function\s*\(""")


class Verifier:
    """Static verifier for generated bundles."""

    _PY_REQUIRED = ("main.py", "README.md", "requirements.txt")
    _TS_REQUIRED = ("src/index.ts", "README.md", "package.json")

    def _is_ts_bundle(self, files: dict[str, str]) -> bool:
        return any(n.endswith(".ts") for n in files)

    def verify_bundle(self, files: dict[str, str]) -> VerificationResult:
        errors: list[str] = []
        required = self._TS_REQUIRED if self._is_ts_bundle(files) else self._PY_REQUIRED
        for name in required:
            if name not in files:
                errors.append(f"missing_file:{name}")
        for name, content in files.items():
            if name.endswith(".py"):
                errors.extend(self._scan_python(name, content))
            elif name.endswith(".ts"):
                errors.extend(self._scan_typescript(name, content))
        for name, content in files.items():
            errors.extend(self._scan_secrets(name, content))
        return VerificationResult(ok=not errors, errors=errors)

    def verify_dir(self, path: Path) -> VerificationResult:
        files: dict[str, str] = {}
        for child in path.iterdir():
            if child.is_file():
                files[child.name] = child.read_text(encoding="utf-8")
        return self.verify_bundle(files)

    def _scan_typescript(self, name: str, content: str) -> list[str]:
        errors: list[str] = []
        if TS_DISALLOWED_IMPORTS.search(content):
            errors.append(f"disallowed_import:{name}:{TS_DISALLOWED_IMPORTS.pattern[:40]}")
        if TS_DISALLOWED_PATTERNS.search(content):
            errors.append(f"disallowed_import:{name}:eval/Function")
        return errors

    def _scan_python(self, name: str, content: str) -> list[str]:
        errors: list[str] = []
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return [f"syntax_error:{name}:{exc.msg}"]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in ALLOWED_IMPORTS:
                        errors.append(f"disallowed_import:{name}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root and root not in ALLOWED_IMPORTS:
                    errors.append(f"disallowed_import:{name}:{node.module}")
        return errors

    def _scan_secrets(self, name: str, content: str) -> list[str]:
        errors: list[str] = []
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(content):
                snippet = match.group(0)
                if "<" in snippet and ">" in snippet:
                    continue
                if snippet.replace(".", "").isdigit() and snippet in {"127.0.0.1", "0.0.0.0"}:
                    continue
                errors.append(f"secret_match:{name}:{pattern.pattern[:30]}")
                break
        return errors
