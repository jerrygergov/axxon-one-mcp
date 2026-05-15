from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/api-audit/pdf-gap-coverage-matrix.json"


class PdfGapCoverageTests(unittest.TestCase):
    def test_matrix_rows_have_required_fields(self) -> None:
        rows = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 24)
        required = {
            "pdf_area",
            "pages",
            "status",
            "risk",
            "tooling",
            "report",
            "next_step",
        }
        for row in rows:
            with self.subTest(area=row.get("pdf_area")):
                self.assertTrue(required.issubset(row))
                self.assertIn(
                    row["status"],
                    {
                        "verified",
                        "partial",
                        "fixture-needed",
                        "not-verified",
                        "unsafe",
                    },
                )
                self.assertIn(
                    row["risk"],
                    {
                        "safe-read",
                        "bounded-stream",
                        "fixture-heavy",
                        "mutation",
                        "external-client",
                    },
                )

    def test_book_links_matrix(self) -> None:
        book = (ROOT / "docs/AXXON_ONE_API_BOOK.md").read_text(encoding="utf-8")
        self.assertIn("pdf-gap-coverage-matrix.md", book)
