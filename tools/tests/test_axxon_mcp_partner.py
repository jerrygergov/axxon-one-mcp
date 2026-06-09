"""Phase 6B tests: PartnerKit scaffold_plugin / plugin_lint / plugin_package."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import zipfile


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


def make_corpus(root: Path) -> Path:
    corpus = root / "mcp-corpus"
    corpus.mkdir()
    (corpus / "api_methods.json").write_text(json.dumps({"methods": []}), encoding="utf-8")
    (corpus / "http_endpoints.json").write_text(json.dumps({"endpoints": []}), encoding="utf-8")
    (corpus / "safety_policies.json").write_text(json.dumps({"classes": {}}), encoding="utf-8")
    (corpus / "known_behaviors.json").write_text(json.dumps({}), encoding="utf-8")
    (corpus / "fixtures.json").write_text(json.dumps({}), encoding="utf-8")
    (corpus / "task_recipes.json").write_text(json.dumps({"recipes": []}), encoding="utf-8")
    return corpus


def load_kit(corpus: Path):
    gen_mod = importlib.import_module("axxon_mcp_generator")
    importlib.reload(gen_mod)
    mod = importlib.import_module("axxon_mcp_partner")
    importlib.reload(mod)
    return mod, mod.PartnerKit(generator=gen_mod.Generator(corpus_dir=corpus))


def write_repo(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


class ScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = make_corpus(Path(self.tmp.name))
        self.mod, self.kit = load_kit(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scaffold_python(self) -> None:
        """AC1: python scaffold returns the plugin_scaffold file set with README safety + env example."""
        result = self.kit.scaffold_plugin("acme-bridge", "python")
        self.assertEqual(result["status"], "ok")
        files = result["files"]
        self.assertIn("main.py", files)
        self.assertIn(".env.example", files)
        self.assertIn("Safety", files["README.md"])

    def test_scaffold_node(self) -> None:
        """AC1: node scaffold returns a TS entrypoint and package.json."""
        files = self.kit.scaffold_plugin("acme-bridge", "node")["files"]
        self.assertIn("src/index.ts", files)
        self.assertIn("package.json", files)

    def test_scaffold_bad_language(self) -> None:
        """AC2: unsupported language is refused."""
        result = self.kit.scaffold_plugin("acme-bridge", "rust")
        self.assertEqual(result["status"], "refused")
        self.assertIn("language", result["reason"] + result.get("detail", ""))


class LintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.corpus = make_corpus(self.root)
        self.mod, self.kit = load_kit(self.corpus)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _scaffold_repo(self, language: str = "python") -> Path:
        repo = self.root / "repo"
        files = self.kit.scaffold_plugin("acme-bridge", language)["files"]
        return write_repo(repo, files)

    def test_lint_clean_python(self) -> None:
        """AC3: a freshly scaffolded python repo lints clean."""
        result = self.kit.plugin_lint(self._scaffold_repo("python"))
        self.assertTrue(result["ok"], msg=str(result["findings"]))

    def test_lint_clean_node(self) -> None:
        """AC3: a freshly scaffolded node repo lints clean."""
        result = self.kit.plugin_lint(self._scaffold_repo("node"))
        self.assertTrue(result["ok"], msg=str(result["findings"]))

    def test_lint_flags_secret(self) -> None:
        """AC4: a committed secret is flagged."""
        repo = self._scaffold_repo("python")
        (repo / "leak.py").write_text("password = 'hunter2hunter2'\n", encoding="utf-8")
        result = self.kit.plugin_lint(repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("embedded_secret" in f for f in result["findings"]))

    def test_lint_flags_missing_env_example(self) -> None:
        """AC5: missing .env.example is flagged."""
        repo = self._scaffold_repo("python")
        (repo / ".env.example").unlink()
        result = self.kit.plugin_lint(repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("missing_env_example" in f for f in result["findings"]))

    def test_lint_flags_missing_test(self) -> None:
        """AC5: missing test file is flagged."""
        repo = self._scaffold_repo("python")
        (repo / "test_smoke.py").unlink()
        result = self.kit.plugin_lint(repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("missing_test" in f for f in result["findings"]))

    def test_lint_flags_missing_safety(self) -> None:
        """AC5: README without a Safety section is flagged."""
        repo = self._scaffold_repo("python")
        (repo / "README.md").write_text("# acme-bridge\n\nNo safety here.\n", encoding="utf-8")
        result = self.kit.plugin_lint(repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("missing_safety_section" in f for f in result["findings"]))


class PackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.corpus = make_corpus(self.root)
        self.mod, self.kit = load_kit(self.corpus)
        repo = self.root / "repo"
        write_repo(repo, self.kit.scaffold_plugin("acme-bridge", "python")["files"])
        self.repo = repo

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_package_zip(self) -> None:
        """AC1/AC3/AC5: zip package writes a versioned archive with prefixed members and embedded manifest."""
        out = self.root / "out.zip"
        result = self.kit.plugin_package(self.repo, "zip", out, version="1.2.3")
        self.assertEqual(result["status"], "ok")
        manifest = result["manifest"]
        self.assertEqual(manifest["format"], "zip")
        self.assertEqual(manifest["version"], "1.2.3")
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        self.assertTrue(out.exists())
        prefix = "repo-1.2.3"
        self.assertEqual(result["prefix"], prefix)
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            expected = {f"{prefix}/{rel}" for rel in manifest["files"]} | {f"{prefix}/manifest.json"}
            self.assertEqual(names, expected)
        for digest in manifest["files"].values():
            self.assertEqual(len(digest), 64)

    def test_package_targz(self) -> None:
        """AC3/AC5: tar.gz package writes a prefixed archive with embedded manifest."""
        out = self.root / "out.tar.gz"
        result = self.kit.plugin_package(self.repo, "tar.gz", out, version="2.0.0")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(out.exists())
        prefix = "repo-2.0.0"
        with tarfile.open(out, "r:gz") as tf:
            names = {m.name for m in tf.getmembers() if m.isfile()}
        expected = {f"{prefix}/{rel}" for rel in result["manifest"]["files"]} | {f"{prefix}/manifest.json"}
        self.assertEqual(names, expected)

    def test_package_embedded_manifest_matches(self) -> None:
        """AC1: the manifest.json inside the archive matches the returned file hashes."""
        out = self.root / "out.zip"
        result = self.kit.plugin_package(self.repo, "zip", out, version="1.0.0")
        prefix = result["prefix"]
        with zipfile.ZipFile(out) as zf:
            embedded = json.loads(zf.read(f"{prefix}/manifest.json"))
        self.assertEqual(embedded["files"], result["manifest"]["files"])
        self.assertEqual(embedded["version"], "1.0.0")
        self.assertNotIn("manifest.json", embedded["files"])

    def test_package_default_output_name_has_version(self) -> None:
        """AC3: omitting output yields a name-version filename."""
        result = self.kit.plugin_package(self.repo, "zip", None, version="3.4.5")
        self.assertTrue(result["archive"].endswith("repo-3.4.5.zip"))
        self.assertTrue(Path(result["archive"]).exists())

    def test_package_pins_python_deps(self) -> None:
        """AC2: requirements.txt deps are pinned/flagged in the manifest."""
        (self.repo / "requirements.txt").write_text(
            "grpcio==1.60.0\nprotobuf>=4.25\n# comment\nrequests\n", encoding="utf-8"
        )
        result = self.kit.plugin_package(self.repo, "zip", self.root / "out.zip")
        deps = result["manifest"]["dependencies"]
        self.assertEqual(deps["grpcio"], {"version": "1.60.0", "pinned": True})
        self.assertFalse(deps["protobuf"]["pinned"])
        self.assertFalse(deps["requests"]["pinned"])

    def test_package_pins_node_deps(self) -> None:
        """AC2: package.json dependencies are pinned/flagged in the manifest."""
        node_repo = self.root / "noderepo"
        write_repo(node_repo, self.kit.scaffold_plugin("node-bridge", "node")["files"])
        (node_repo / "package.json").write_text(
            json.dumps({"name": "node-bridge", "dependencies": {"a": "1.2.3", "b": "^4.5.6", "c": "*"}}),
            encoding="utf-8",
        )
        result = self.kit.plugin_package(node_repo, "zip", self.root / "node.zip")
        deps = result["manifest"]["dependencies"]
        self.assertTrue(deps["a"]["pinned"])
        self.assertFalse(deps["b"]["pinned"])
        self.assertFalse(deps["c"]["pinned"])

    def test_collect_dependencies_empty(self) -> None:
        """AC2: a repo with no requirements.txt or package.json yields an empty deps map."""
        plain = write_repo(self.root / "plain", {"main.py": "print('hi')\n"})
        rel_files = {p.relative_to(plain).as_posix(): p for p in self.mod._iter_repo_files(plain)}
        self.assertEqual(self.mod._collect_dependencies(rel_files), {})

    def test_package_bad_format(self) -> None:
        """AC4: unsupported format is refused."""
        result = self.kit.plugin_package(self.repo, "rar", self.root / "out.rar")
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "unsupported_format")

    def test_package_refuses_dirty_repo(self) -> None:
        """AC4: a repo that does not lint clean is refused and writes no archive."""
        (self.repo / "leak.py").write_text("password = 'hunter2hunter2'\n", encoding="utf-8")
        out = self.root / "out.zip"
        result = self.kit.plugin_package(self.repo, "zip", out)
        self.assertEqual(result["status"], "refused")
        self.assertIn("lint", result["reason"])
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
