#!/usr/bin/env python3
"""Phase 6B partner SDK kit for the Axxon One MCP server.

Provides three offline capabilities built on the existing generator and verifier:
- scaffold_plugin: emit a complete runnable plugin repo (reuses the plugin_scaffold template).
- plugin_lint: run the static Verifier plus repo-level checks (env example, test, README safety).
- plugin_package: produce a versioned distributable archive with an embedded SHA-256 manifest
  (pinned dependencies, name-version/ layout), only for clean repos.

The kit is pure stdlib and never connects to a server; the scaffolded plugin is what connects.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from axxon_mcp_generator import (
    GenerationRefusal,
    GenerationRequest,
    Generator,
    Verifier,
)

SUPPORTED_LANGUAGES = ("python", "node")
SUPPORTED_FORMATS = ("zip", "tar.gz")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist", ".venv"}
MANIFEST_NAME = "manifest.json"
DEFAULT_VERSION = "0.0.0"
_PINNED_PY = re.compile(r"^([A-Za-z0-9._-]+)==([^=;,\s]+)$")
_REQ_NAME = re.compile(r"^([A-Za-z0-9._-]+)")


def _iter_repo_files(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            files.append(path)
    return files


def _parse_python_deps(text: str) -> dict[str, dict[str, str | bool]]:
    """Parse requirements.txt lines into name -> {version, pinned} entries."""
    deps: dict[str, dict[str, str | bool]] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        pinned = _PINNED_PY.match(line)
        if pinned:
            deps[pinned.group(1)] = {"version": pinned.group(2), "pinned": True}
        else:
            name = _REQ_NAME.match(line)
            if name:
                deps[name.group(1)] = {"version": line[name.end():].strip(), "pinned": False}
    return deps


def _parse_node_deps(text: str) -> dict[str, dict[str, str | bool]]:
    """Parse package.json dependencies into name -> {version, pinned} entries."""
    raw_deps = json.loads(text).get("dependencies", {})
    deps: dict[str, dict[str, str | bool]] = {}
    for name, spec in raw_deps.items():
        pinned = bool(re.match(r"^\d+\.\d+\.\d+", spec)) and not re.search(r"[\^~*x><|\s-]|\.x", spec)
        deps[name] = {"version": spec, "pinned": pinned}
    return deps


def _collect_dependencies(rel_files: dict[str, Path]) -> dict[str, dict[str, str | bool]]:
    """Extract pinned dependencies from a python or node repo, empty if neither present."""
    for rel, path in rel_files.items():
        name = Path(rel).name
        if name == "requirements.txt":
            return _parse_python_deps(path.read_text(encoding="utf-8", errors="replace"))
        if name == "package.json":
            return _parse_node_deps(path.read_text(encoding="utf-8", errors="replace"))
    return {}


class PartnerKit:
    """Offline partner-plugin scaffolder, linter, and packager."""

    def __init__(self, generator: Generator | None = None) -> None:
        self.generator = generator or Generator()
        self.verifier = Verifier()

    def scaffold_plugin(self, name: str, language: str = "python") -> dict[str, Any]:
        """Generate a runnable plugin repo for `name` in `language`."""
        if language not in SUPPORTED_LANGUAGES:
            return {
                "status": "refused",
                "reason": "unsupported_language",
                "detail": f"language must be one of {SUPPORTED_LANGUAGES}; got {language!r}",
            }
        result = self.generator.generate(
            GenerationRequest(template="plugin_scaffold", params={"name": name}, language=language)
        )
        if isinstance(result, GenerationRefusal):
            return {"status": "refused", **asdict(result)}
        return {"status": "ok", "name": name, "language": language, "files": result.files}

    def plugin_lint(self, path: str | Path) -> dict[str, Any]:
        """Run the static verifier plus repo-level checks on a plugin repo."""
        root = Path(path).expanduser().resolve()
        findings: list[str] = []
        rel_files = {p.relative_to(root).as_posix(): p for p in _iter_repo_files(root)}
        contents = {rel: p.read_text(encoding="utf-8", errors="replace") for rel, p in rel_files.items()}

        verdict = self.verifier.verify_bundle(contents)
        findings.extend(e.replace("secret_match", "embedded_secret") for e in verdict.errors)

        if not any(rel == ".env.example" or rel.endswith("/.env.example") for rel in rel_files):
            findings.append("missing_env_example")
        if not any(("test" in Path(rel).name.lower()) and rel.endswith((".py", ".ts")) for rel in rel_files):
            findings.append("missing_test")
        readme = next((c for rel, c in contents.items() if Path(rel).name.lower() == "readme.md"), "")
        if "Safety" not in readme:
            findings.append("missing_safety_section")

        return {"ok": not findings, "findings": findings, "files_scanned": len(rel_files)}

    def plugin_package(
        self,
        path: str | Path,
        fmt: str = "zip",
        output: str | Path | None = None,
        version: str = DEFAULT_VERSION,
    ) -> dict[str, Any]:
        """Package a clean plugin repo into a versioned archive with an embedded SHA-256 manifest."""
        if fmt not in SUPPORTED_FORMATS:
            return {
                "status": "refused",
                "reason": "unsupported_format",
                "detail": f"format must be one of {SUPPORTED_FORMATS}; got {fmt!r}",
            }
        root = Path(path).expanduser().resolve()
        lint = self.plugin_lint(root)
        if not lint["ok"]:
            return {"status": "refused", "reason": "lint_failed", "findings": lint["findings"]}

        prefix = f"{root.name}-{version}"
        out_path = (
            Path(output).expanduser().resolve()
            if output
            else root.parent / f"{prefix}.{fmt}"
        )
        rel_files = {p.relative_to(root).as_posix(): p for p in _iter_repo_files(root)}
        manifest_files = {
            rel: hashlib.sha256(p.read_bytes()).hexdigest() for rel, p in sorted(rel_files.items())
        }
        manifest = {
            "name": root.name,
            "version": version,
            "format": fmt,
            "file_count": len(manifest_files),
            "dependencies": _collect_dependencies(rel_files),
            "files": manifest_files,
        }
        manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")

        if fmt == "zip":
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for rel, p in rel_files.items():
                    zf.write(p, arcname=f"{prefix}/{rel}")
                zf.writestr(f"{prefix}/{MANIFEST_NAME}", manifest_bytes)
        else:
            with tarfile.open(out_path, "w:gz") as tf:
                for rel, p in rel_files.items():
                    tf.add(p, arcname=f"{prefix}/{rel}")
                info = tarfile.TarInfo(name=f"{prefix}/{MANIFEST_NAME}")
                info.size = len(manifest_bytes)
                info.mtime = int(time.time())
                tf.addfile(info, io.BytesIO(manifest_bytes))

        return {"status": "ok", "archive": str(out_path), "prefix": prefix, "manifest": manifest}
