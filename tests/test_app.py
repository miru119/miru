import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import (
    CSV_HEADERS,
    YEARS,
    WeeklyReport,
    build_html_page,
    create_weekly_form_csv,
    fetch_weekly_reports,
    import_weekly_form_csv,
    upsert_weekly_report,
    validate_year,
)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE weekly_reports (
                counselor TEXT NOT NULL,
                year INTEGER NOT NULL,
                week_start TEXT NOT NULL,
                recruit INTEGER NOT NULL DEFAULT 0,
                allowance_apply INTEGER NOT NULL DEFAULT 0,
                assign INTEGER NOT NULL DEFAULT 0,
                transfer_assign INTEGER NOT NULL DEFAULT 0,
                withdraw INTEGER NOT NULL DEFAULT 0,
                mediated_employment INTEGER NOT NULL DEFAULT 0,
                self_employment INTEGER NOT NULL DEFAULT 0,
                unrecognized_employment INTEGER NOT NULL DEFAULT 0,
                suspended INTEGER NOT NULL DEFAULT 0,
                expired INTEGER NOT NULL DEFAULT 0,
                aftercare_end_suspended INTEGER NOT NULL DEFAULT 0,
                success_payment_completed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (counselor, year, week_start)
            )
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_create_weekly_form_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "form.csv"
            create_weekly_form_csv("2024-01-01", ["홍길동", "김상담"], output)
            with output.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))

        self.assertEqual(rows[0], CSV_HEADERS)
        self.assertEqual(len(rows) - 1, 2 * len(YEARS))

    def test_import_weekly_form_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "form.csv"
            create_weekly_form_csv("2025-02-03", ["홍길동"], output)

            with output.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

            rows[0]["모집"] = "10"
            rows[0]["배정"] = "5"

            with output.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writeheader()
                writer.writerows(rows)

            saved = import_weekly_form_csv(self.conn, output)

        self.assertEqual(saved, len(YEARS))
        result = list(fetch_weekly_reports(self.conn, "2025-02-03"))
        self.assertEqual(result[0]["recruit"], 10)
        self.assertEqual(result[0]["assign"], 5)

    def test_upsert_weekly_report(self):
        upsert_weekly_report(self.conn, WeeklyReport("김상담", 2024, "2024-01-01", {"recruit": 3}))
        upsert_weekly_report(self.conn, WeeklyReport("김상담", 2024, "2024-01-01", {"recruit": 7, "assign": 2}))

        rows = list(fetch_weekly_reports(self.conn, "2024-01-01"))
        self.assertEqual(rows[0]["recruit"], 7)
        self.assertEqual(rows[0]["assign"], 2)

    def test_build_html_page_contains_ui_text(self):
        page = build_html_page([])
        self.assertIn("상담사 주간보고 입력 화면", page)
        self.assertIn("성공금 지급완료건수", page)

    def test_validate_year_rejects_unsupported_year(self):
        with self.assertRaises(ValueError):
            validate_year(2027)


if __name__ == "__main__":
    unittest.main()
