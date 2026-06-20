#!/usr/bin/env python3
"""Docs-only query layer for the planned Axxon One MCP server.

This module intentionally does not connect to an Axxon server. It serves the
sanitized Phase 0 corpus and returns explicit gaps for unknown APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import re
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_DIR = REPO_ROOT / "docs" / "api-audit" / "mcp-corpus"


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"\bconfiguration\b", "config", text, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def tokens(text: str) -> set[str]:
    return {token for token in normalize(text).split() if token}


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def score_text(query: str, haystack: str) -> int:
    query_norm = normalize(query)
    haystack_norm = normalize(haystack)
    if not query_norm or not haystack_norm:
        return 0
    score = 0
    if query_norm in haystack_norm:
        score += 20
    query_compact = compact(query)
    haystack_compact = compact(haystack)
    if query_compact and query_compact in haystack_compact:
        score += 15
    shared = tokens(query_norm) & tokens(haystack_norm)
    score += len(shared) * 5
    return score


def api_relevance_boost(query: str, method: dict[str, Any]) -> int:
    query_tokens = tokens(query)
    service = str(method.get("service", "")).lower()
    method_name = str(method.get("method", "")).lower()
    boost = 0
    if {"config", "camera"} & query_tokens and service == "configurationservice":
        boost += 8
    if "config" in query_tokens and method_name in {"changeconfig", "changeconfigstream"}:
        boost += 6
    return boost


def source_list(*values: str) -> list[str]:
    return [value for value in values if value]


@dataclass(frozen=True)
class AxxonMcpDocs:
    """Searchable view over the generated MCP corpus."""

    corpus_dir: Path
    api_methods: dict[str, Any]
    http_endpoints: dict[str, Any]
    legacy_http_endpoints: dict[str, Any]
    task_recipes: dict[str, Any]
    fixtures: dict[str, Any]
    safety_policies: dict[str, Any]
    known_behaviors: dict[str, Any]

    @classmethod
    def from_corpus_dir(cls, corpus_dir: Path = DEFAULT_CORPUS_DIR) -> "AxxonMcpDocs":
        corpus_dir = corpus_dir.resolve()
        return cls(
            corpus_dir=corpus_dir,
            api_methods=load_json(corpus_dir / "api_methods.json", {"methods": []}),
            http_endpoints=load_json(corpus_dir / "http_endpoints.json", {"endpoints": []}),
            legacy_http_endpoints=load_json(corpus_dir / "legacy_http_endpoints.json", {"endpoints": []}),
            task_recipes=load_json(corpus_dir / "task_recipes.json", {"recipes": [], "mutation_playbooks": []}),
            fixtures=load_json(corpus_dir / "fixtures.json", {"coverage_counts": {}, "fixture_needed": []}),
            safety_policies=load_json(corpus_dir / "safety_policies.json", {}),
            known_behaviors=load_json(corpus_dir / "known_behaviors.json", {"behaviors": []}),
        )

    def get_api_method(self, fqmn: str) -> dict[str, Any]:
        query_compact = compact(fqmn)
        matches = []
        for method in self.api_methods.get("methods", []):
            names = [
                str(method.get("fqmn", "")),
                f"{method.get('service', '')}.{method.get('method', '')}",
                str(method.get("method", "")),
            ]
            if any(compact(name) == query_compact for name in names):
                matches.append(method)
        if not matches:
            return self._gap("api_method", fqmn)
        method = matches[0]
        return {
            "found": True,
            "kind": "api_method",
            "method": method,
            "sources": source_list(str(self.api_methods.get("source", "")), str(method.get("proto", ""))),
        }

    def _iter_http_endpoints(self) -> list[tuple[dict[str, Any], str, str]]:
        endpoints: list[tuple[dict[str, Any], str, str]] = []
        for endpoint in self.http_endpoints.get("endpoints", []):
            endpoint = dict(endpoint)
            endpoint.setdefault("surface", "v1_http")
            endpoints.append((endpoint, str(self.http_endpoints.get("source", "")), "http_endpoint"))
        for endpoint in self.legacy_http_endpoints.get("endpoints", []):
            endpoint = dict(endpoint)
            endpoint.setdefault("surface", "legacy_web_http")
            endpoints.append((endpoint, str(self.legacy_http_endpoints.get("source", "")), "legacy_http_endpoint"))
        return endpoints

    def get_http_endpoint(self, path_or_topic: str) -> dict[str, Any]:
        query_compact = compact(path_or_topic)
        scored: list[tuple[int, dict[str, Any], str, str]] = []
        for endpoint, catalog_source, kind in self._iter_http_endpoints():
            haystack = " ".join(
                [
                    str(endpoint.get("verb", "")),
                    str(endpoint.get("path", "")),
                    str(endpoint.get("name", "")),
                    str(endpoint.get("id", "")),
                    str(endpoint.get("surface", "")),
                    str(endpoint.get("grpc_method", "")),
                    str(endpoint.get("safety_class", "")),
                ]
            )
            if compact(endpoint.get("path", "")) == query_compact:
                scored.append((100, endpoint, catalog_source, kind))
                continue
            score = score_text(path_or_topic, haystack)
            if score >= 10:
                scored.append((score, endpoint, catalog_source, kind))
        if not scored:
            return self._gap("http_endpoint", path_or_topic)
        scored.sort(key=lambda item: item[0], reverse=True)
        _, endpoint, catalog_source, kind = scored[0]
        return {
            "found": True,
            "kind": kind,
            "endpoint": endpoint,
            "sources": source_list(catalog_source, str(endpoint.get("source", ""))),
        }

    def search_api_docs(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for method in self.api_methods.get("methods", []):
            haystack = " ".join(str(method.get(key, "")) for key in method)
            score = score_text(query, haystack) + api_relevance_boost(query, method)
            if score:
                results.append(
                    {
                        "kind": "method",
                        "score": score,
                        "title": str(method.get("fqmn", "")),
                        "item": method,
                        "sources": source_list(str(self.api_methods.get("source", "")), str(method.get("proto", ""))),
                    }
                )
        for endpoint, catalog_source, kind in self._iter_http_endpoints():
            haystack = " ".join(str(endpoint.get(key, "")) for key in endpoint)
            score = score_text(query, haystack)
            if score:
                results.append(
                    {
                        "kind": kind,
                        "score": score,
                        "title": f"{endpoint.get('verb', '')} {endpoint.get('path', '')}",
                        "item": endpoint,
                        "sources": source_list(catalog_source, str(endpoint.get("source", ""))),
                    }
                )
        for recipe in self.task_recipes.get("recipes", []):
            score = score_text(query, f"{recipe.get('task', '')} {recipe.get('summary', '')}")
            if score:
                results.append(
                    {
                        "kind": "task_recipe",
                        "score": score,
                        "title": str(recipe.get("task", "")),
                        "item": recipe,
                        "sources": source_list(str(recipe.get("source", ""))),
                    }
                )
        for behavior in self.known_behaviors.get("behaviors", []):
            score = score_text(query, f"{behavior.get('topic', '')} {behavior.get('behavior', '')}")
            if score:
                results.append(
                    {
                        "kind": "known_behavior",
                        "score": score,
                        "title": str(behavior.get("topic", "")),
                        "item": behavior,
                        "sources": source_list(str(behavior.get("source", ""))),
                    }
                )
        results.sort(key=lambda item: (item["score"], item["kind"] == "method"), reverse=True)
        return {
            "query": query,
            "results": results[:limit],
            "status": "ok" if results else "gap",
        }

    def get_verified_example(self, topic: str) -> dict[str, Any]:
        scored: list[tuple[int, dict[str, Any]]] = []
        for behavior in self.known_behaviors.get("behaviors", []):
            score = score_text(topic, f"{behavior.get('topic', '')} {behavior.get('behavior', '')}")
            if score:
                scored.append((score, behavior))
        for recipe in self.task_recipes.get("recipes", []):
            score = score_text(topic, f"{recipe.get('task', '')} {recipe.get('summary', '')}")
            if score:
                scored.append((score, {"topic": recipe.get("task", ""), "behavior": recipe.get("summary", ""), "source": recipe.get("source", "")}))
        for playbook in self.task_recipes.get("mutation_playbooks", []):
            score = score_text(topic, f"{playbook.get('name', '')} {playbook.get('title', '')}")
            if score:
                scored.append((score, {"topic": playbook.get("name", ""), "behavior": playbook.get("title", ""), "source": playbook.get("source", "")}))
        if not scored:
            return self._gap("verified_example", topic)
        scored.sort(key=lambda item: item[0], reverse=True)
        example = scored[0][1]
        return {
            "found": True,
            "kind": "verified_example",
            "example": example,
            "sources": source_list(str(example.get("source", ""))),
        }

    def explain_task_recipe(self, task: str) -> dict[str, Any]:
        scored = []
        for recipe in self.task_recipes.get("recipes", []):
            score = score_text(task, f"{recipe.get('task', '')} {recipe.get('summary', '')}")
            if score:
                scored.append((score, recipe))
        if not scored:
            return self._gap("task_recipe", task)
        scored.sort(key=lambda item: item[0], reverse=True)
        recipe = scored[0][1]
        return {
            "found": True,
            "kind": "task_recipe",
            "recipe": recipe,
            "sources": source_list(str(recipe.get("source", ""))),
        }

    def list_remaining_gaps(self) -> dict[str, Any]:
        return {
            "found": True,
            "kind": "remaining_gaps",
            "coverage_counts": self.fixtures.get("coverage_counts", {}),
            "gaps": self.fixtures.get("fixture_needed", []),
            "sources": source_list(str(self.fixtures.get("source", ""))),
        }

    def _gap(self, kind: str, query: str) -> dict[str, Any]:
        return {
            "found": False,
            "kind": kind,
            "status": "gap",
            "query": query,
            "message": "No verified corpus entry matched this query. Treat it as unsupported until a source doc or live report is added.",
            "remaining_gaps": self.fixtures.get("fixture_needed", []),
            "sources": source_list(str(self.fixtures.get("source", ""))),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the docs-only Axxon One MCP corpus.")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)

    method = subparsers.add_parser("method")
    method.add_argument("fqmn")

    endpoint = subparsers.add_parser("endpoint")
    endpoint.add_argument("path_or_topic")

    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)

    example = subparsers.add_parser("example")
    example.add_argument("topic")

    recipe = subparsers.add_parser("recipe")
    recipe.add_argument("task")

    subparsers.add_parser("gaps")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    docs = AxxonMcpDocs.from_corpus_dir(args.corpus_dir)
    if args.command == "method":
        payload = docs.get_api_method(args.fqmn)
    elif args.command == "endpoint":
        payload = docs.get_http_endpoint(args.path_or_topic)
    elif args.command == "search":
        payload = docs.search_api_docs(args.query, limit=args.limit)
    elif args.command == "example":
        payload = docs.get_verified_example(args.topic)
    elif args.command == "recipe":
        payload = docs.explain_task_recipe(args.task)
    else:
        payload = docs.list_remaining_gaps()
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
