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
    "axxonsoft",
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


TEMPLATE_CATALOG: list[TemplateInfo] = [
    TemplateInfo(
        name="grpc_consumer",
        summary="Direct gRPC consumer for a single method (AuthenticateEx2 + one call).",
        required_params=["fqmn"],
        required_fixtures=[],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
    ),
    TemplateInfo(
        name="http_grpc_consumer",
        summary="HTTP /grpc consumer for a single method using Bearer auth.",
        required_params=["fqmn"],
        required_fixtures=[],
        required_env=["AXXON_HTTP_URL", "AXXON_USERNAME", "AXXON_PASSWORD"],
    ),
    TemplateInfo(
        name="legacy_http_consumer",
        summary="Legacy HTTP consumer for a verified path (Bearer or Basic).",
        required_params=["path"],
        required_fixtures=[],
        required_env=["AXXON_HTTP_URL", "AXXON_USERNAME", "AXXON_PASSWORD"],
    ),
    TemplateInfo(
        name="event_consumer",
        summary="Bounded detector-event consumer (DomainNotifier.PullEvents).",
        required_params=["subject"],
        required_fixtures=["event-supplier-subject"],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
    ),
    TemplateInfo(
        name="external_event_producer",
        summary="External event producer for a real DetectorEx.* fixture.",
        required_params=["access_point", "event_type"],
        required_fixtures=["detector-ex"],
        required_env=["AXXON_HTTP_URL", "AXXON_USERNAME", "AXXON_PASSWORD"],
    ),
    TemplateInfo(
        name="export_job",
        summary="Archive export job (start/poll/download/destroy) with cleanup.",
        required_params=["camera_ap", "begin", "end"],
        required_fixtures=["mm-export-agent"],
        required_env=["AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"],
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


def _render(template_text: str, values: dict[str, Any]) -> str:
    return Template(template_text).safe_substitute(values)


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
        body = _render(
            _read_template("grpc_consumer"),
            {
                "FQMN": fqmn,
                "PACKAGE": package,
                "SERVICE": service,
                "METHOD": method_name,
                "REQUEST_TYPE": request_type,
                "PROTO": proto,
                "DURATION": str(DEFAULT_DURATION_SECONDS),
            },
        )
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": _render(_read_aux_template("README.md.tmpl"), {"TITLE": fqmn, "TEMPLATE": "grpc_consumer"}),
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
        body = _render(
            _read_template("http_grpc_consumer"),
            {
                "FQMN": fqmn,
                "SERVICE_PATH": fqmn.rsplit(".", 1)[0],
                "METHOD": fqmn.rsplit(".", 1)[1],
                "DURATION": str(DEFAULT_DURATION_SECONDS),
                "BYTE_CAP": str(DEFAULT_HTTP_BYTE_CAP),
            },
        )
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": _render(_read_aux_template("README.md.tmpl"), {"TITLE": fqmn, "TEMPLATE": "http_grpc_consumer"}),
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
        body = _render(
            _read_template("legacy_http_consumer"),
            {
                "PATH": path,
                "VERB": verb,
                "AUTH_MODE": auth_mode,
                "DURATION": str(DEFAULT_DURATION_SECONDS),
                "BYTE_CAP": str(DEFAULT_HTTP_BYTE_CAP),
            },
        )
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": _render(_read_aux_template("README.md.tmpl"), {"TITLE": path, "TEMPLATE": "legacy_http_consumer"}),
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
        body = _render(
            _read_template("event_consumer"),
            {
                "SUBJECT": subject,
                "DURATION": str(duration),
                "COUNT": str(count),
                "APPDATA_HINT": "true" if notes else "false",
            },
        )
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": _render(_read_aux_template("README.md.tmpl"), {"TITLE": subject, "TEMPLATE": "event_consumer"}),
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
        body = _render(
            _read_template("external_event_producer"),
            {
                "ACCESS_POINT": ap,
                "EVENT_TYPE": event_type,
                "DURATION": str(DEFAULT_DURATION_SECONDS),
                "BYTE_CAP": str(DEFAULT_HTTP_BYTE_CAP),
            },
        )
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": _render(_read_aux_template("README.md.tmpl"), {"TITLE": ap, "TEMPLATE": "external_event_producer"}),
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
        body = _render(
            _read_template("export_job"),
            {
                "CAMERA_AP": camera,
                "BEGIN": begin,
                "END": end,
                "FORMAT": fmt,
                "BYTE_CAP": str(DEFAULT_EXPORT_BYTE_CAP),
                "WINDOW": str(window),
            },
        )
        return GeneratedBundle(
            template=request.template,
            files={
                "main.py": body,
                "README.md": _render(_read_aux_template("README.md.tmpl"), {"TITLE": camera, "TEMPLATE": "export_job"}),
                "requirements.txt": "grpcio>=1.60\nprotobuf>=4.25\n",
            },
            required_env=info.required_env,
            required_fixtures=info.required_fixtures,
        )


@dataclass
class VerificationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


class Verifier:
    """Static verifier for generated bundles."""

    REQUIRED_FILES = ("main.py", "README.md", "requirements.txt")

    def verify_bundle(self, files: dict[str, str]) -> VerificationResult:
        errors: list[str] = []
        for name in self.REQUIRED_FILES:
            if name not in files:
                errors.append(f"missing_file:{name}")
        for name, content in files.items():
            if not name.endswith(".py"):
                continue
            errors.extend(self._scan_python(name, content))
        for name, content in files.items():
            errors.extend(self._scan_secrets(name, content))
        return VerificationResult(ok=not errors, errors=errors)

    def verify_dir(self, path: Path) -> VerificationResult:
        files: dict[str, str] = {}
        for child in path.iterdir():
            if child.is_file():
                files[child.name] = child.read_text(encoding="utf-8")
        return self.verify_bundle(files)

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
