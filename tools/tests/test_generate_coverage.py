import contextlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class GenerateCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("generate_coverage")

    def test_classify_status(self) -> None:
        self.assertEqual(self.module.classify_status("tested-pass"), "verified")
        self.assertEqual(
            self.module.classify_status("tested-pass-safe-record"), "verified"
        )
        self.assertEqual(
            self.module.classify_status("tested-warn-fixture-needed"),
            "fixture-blocked",
        )
        self.assertEqual(self.module.classify_status("pending"), "pending")

    def test_render_is_order_independent_and_totals_balance(self) -> None:
        methods = [
            {"service": "B", "live_status": "pending"},
            {"service": "A", "live_status": "tested-pass"},
            {"service": "A", "live_status": "tested-warn-fixture-needed"},
        ]

        first = self.module.render_coverage(methods)
        second = self.module.render_coverage(list(reversed(methods)))

        self.assertEqual(first, second)
        self.assertIn("| A | 1 | 1 | 0 | 2 |", first)
        self.assertIn("| B | 0 | 0 | 1 | 1 |", first)
        self.assertLess(first.index("| A |"), first.index("| B |"))
        self.assertIn("across 2 services", first)
        self.assertIn("| **Total** | **1** | **1** | **1** | **3** |", first)

    def test_services_sort_by_total_then_verified_then_name(self) -> None:
        methods = [
            {"service": "Zulu", "live_status": "pending"},
            {"service": "Zulu", "live_status": "pending"},
            {"service": "Alpha", "live_status": "tested-pass"},
            {"service": "Alpha", "live_status": "pending"},
            {"service": "Beta", "live_status": "tested-pass"},
            {"service": "Beta", "live_status": "pending"},
        ]

        rendered = self.module.render_coverage(methods)

        self.assertLess(rendered.index("| Alpha |"), rendered.index("| Beta |"))
        self.assertLess(rendered.index("| Beta |"), rendered.index("| Zulu |"))

    def test_check_mode_detects_stale_file_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "COVERAGE.md"
            output.write_text("stale\n", encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = self.module.check_output(output, "fresh\n")

            self.assertEqual(result, 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "stale\n")
            self.assertIn(str(output), stdout.getvalue())
            self.assertIn("stale", stdout.getvalue())

            output.write_text("fresh\n", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = self.module.check_output(output, "fresh\n")
            self.assertEqual(result, 0)
            self.assertIn("coverage is current", stdout.getvalue())

    def test_check_treats_crlf_bytes_as_stale_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "COVERAGE.md"
            output.write_bytes(b"fresh\r\n")
            original = output.read_bytes()

            result = self.module.check_output(output, "fresh\n")

            self.assertEqual(result, 1)
            self.assertEqual(output.read_bytes(), original)

    def test_write_output_is_byte_stable_and_uses_lf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "COVERAGE.md"
            rendered = "first\nsecond\n"

            self.module.write_output(output, rendered)
            first = output.read_bytes()
            self.module.write_output(output, rendered)
            second = output.read_bytes()

            self.assertEqual(first, second)
            self.assertEqual(second, b"first\nsecond\n")
            self.assertNotIn(b"\r\n", second)

    def test_tracked_corpus_totals_and_documentation_agree(self) -> None:
        methods = self.module.load_methods()
        services, totals = self.module.aggregate_methods(methods)

        self.assertEqual(len(services), 51)
        self.assertEqual(totals["total"], 361)
        self.assertEqual(totals["verified"], 286)
        self.assertEqual(totals["fixture-blocked"], 55)
        self.assertEqual(totals["pending"], 20)
        self.assertEqual(sum(row["total"] for row in services.values()), 361)

        coverage = (REPO_ROOT / "docs/COVERAGE.md").read_text(encoding="utf-8")
        self.assertEqual(coverage, self.module.render_coverage(methods))
        corpus_readme = (REPO_ROOT / "docs/api-audit/mcp-corpus/README.md").read_text(
            encoding="utf-8"
        )
        for row in (
            "| gRPC services | 51 |",
            "| gRPC RPCs | 361 |",
            "| RPCs live-verified | 286 |",
            "| RPCs fixture-blocked | 55 |",
            "| RPCs pending | 20 |",
        ):
            self.assertIn(row, corpus_readme)


class CorpusRestampCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("axxon_corpus_restamp")

    def _write_corpus(self, directory: str, *, status: str, evidence: str) -> Path:
        path = Path(directory) / "api_methods.json"
        path.write_text(
            json.dumps(
                {
                    "methods": [
                        {
                            "service": "StateControlService",
                            "method": "SetState",
                            "live_status": status,
                            "evidence": evidence,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_check_reports_drift_and_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self._write_corpus(tmp, status="pending", evidence="old")
            original = corpus.read_bytes()

            result = self.module.main(["--check"], corpus_path=corpus)

            self.assertEqual(result, 1)
            self.assertEqual(corpus.read_bytes(), original)

    def test_check_is_current_after_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self._write_corpus(tmp, status="pending", evidence="old")

            self.assertEqual(self.module.main(["--write"], corpus_path=corpus), 0)
            self.assertEqual(self.module.main(["--check"], corpus_path=corpus), 0)
            method = json.loads(corpus.read_text(encoding="utf-8"))["methods"][0]
            self.assertTrue(method["live_status"].startswith("tested-pass"))
            self.assertIn("reversible", method["evidence"])

    def test_write_and_check_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            self.module.main(["--write", "--check"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
