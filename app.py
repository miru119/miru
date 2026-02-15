from __future__ import annotations

import argparse
import csv
import html
import sqlite3
from dataclasses import dataclass
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import urlopen

DB_PATH = Path("weekly_participant_stats.db")
YEARS = (2024, 2025, 2026)

METRIC_FIELDS: list[tuple[str, str]] = [
    ("recruit", "모집"),
    ("allowance_apply", "수당신청"),
    ("assign", "배정"),
    ("transfer_assign", "이관배정"),
    ("withdraw", "신청취하"),
    ("mediated_employment", "알선취업"),
    ("self_employment", "본인취업"),
    ("unrecognized_employment", "미인정취업"),
    ("suspended", "중단"),
    ("expired", "기간만료"),
    ("aftercare_end_suspended", "사후종료(중단)"),
    ("success_payment_completed", "성공금 지급완료건수"),
]
CSV_HEADERS = ["상담사", "연도", "주차시작일", *[label for _, label in METRIC_FIELDS]]


@dataclass(frozen=True)
class WeeklyReport:
    counselor: str
    year: int
    week_start: str
    values: dict[str, int]


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    columns = ",\n            ".join(f"{field} INTEGER NOT NULL DEFAULT 0" for field, _ in METRIC_FIELDS)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS weekly_reports (
            counselor TEXT NOT NULL,
            year INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            {columns},
            PRIMARY KEY (counselor, year, week_start)
        )
        """
    )
    return conn


def validate_year(year: int) -> None:
    if year not in YEARS:
        raise ValueError(f"지원되지 않는 연도입니다: {year}. 허용 연도: {list(YEARS)}")


def parse_week_start(value: str) -> str:
    return date.fromisoformat(value).isoformat()


def normalize_values(values: dict[str, int] | None = None) -> dict[str, int]:
    normalized = {field: 0 for field, _ in METRIC_FIELDS}
    if not values:
        return normalized
    for field, count in values.items():
        if field not in normalized:
            raise ValueError(f"지원되지 않는 항목 키입니다: {field}")
        normalized[field] = int(count)
    return normalized


def upsert_weekly_report(conn: sqlite3.Connection, report: WeeklyReport) -> None:
    validate_year(report.year)
    parse_week_start(report.week_start)
    values = normalize_values(report.values)

    field_names = [field for field, _ in METRIC_FIELDS]
    insert_columns = ["counselor", "year", "week_start", *field_names]
    placeholders = ", ".join(["?"] * len(insert_columns))
    updates = ", ".join([f"{field}=excluded.{field}" for field in field_names])

    conn.execute(
        f"""
        INSERT INTO weekly_reports ({", ".join(insert_columns)})
        VALUES ({placeholders})
        ON CONFLICT(counselor, year, week_start)
        DO UPDATE SET {updates}
        """,
        [report.counselor, report.year, report.week_start, *[values[field] for field in field_names]],
    )
    conn.commit()


def create_weekly_form_csv(week_start: str, counselors: list[str], output: Path) -> None:
    parse_week_start(week_start)
    counselors = [name.strip() for name in counselors if name.strip()]
    if not counselors:
        raise ValueError("상담사 목록이 비어 있습니다.")

    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        for counselor in counselors:
            for year in YEARS:
                writer.writerow([counselor, year, week_start, *([0] * len(METRIC_FIELDS))])


def import_weekly_form_csv(conn: sqlite3.Connection, csv_file: Path) -> int:
    with csv_file.open("r", newline="", encoding="utf-8-sig") as f:
        return import_weekly_form_reader(conn, csv.DictReader(f))


def import_weekly_form_reader(conn: sqlite3.Connection, reader: csv.DictReader) -> int:
    if not reader.fieldnames:
        raise ValueError("CSV 헤더를 읽을 수 없습니다.")

    required = set(CSV_HEADERS)
    missing = required.difference(set(reader.fieldnames))
    if missing:
        raise ValueError(f"CSV 헤더 누락: {sorted(missing)}")

    saved = 0
    for row in reader:
        values = {field: int(row[label]) for field, label in METRIC_FIELDS}
        report = WeeklyReport(
            counselor=row["상담사"],
            year=int(row["연도"]),
            week_start=parse_week_start(row["주차시작일"]),
            values=values,
        )
        upsert_weekly_report(conn, report)
        saved += 1
    return saved


def normalize_google_sheet_csv_url(url: str) -> str:
    parsed = urlparse(url)
    if "docs.google.com" not in parsed.netloc:
        return url
    if "/export" in parsed.path and "format=csv" in parsed.query:
        return url
    if "/edit" in parsed.path:
        base = url.split("/edit")[0]
        return f"{base}/export?format=csv"
    return url


def import_weekly_form_csv_url(conn: sqlite3.Connection, csv_url: str) -> int:
    normalized_url = normalize_google_sheet_csv_url(csv_url)
    with urlopen(normalized_url) as response:
        content = response.read().decode("utf-8-sig")
    reader = csv.DictReader(content.splitlines())
    return import_weekly_form_reader(conn, reader)


def fetch_weekly_reports(conn: sqlite3.Connection, week_start: str | None = None) -> Iterable[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM weekly_reports WHERE 1=1"
    params: list[object] = []
    if week_start:
        query += " AND week_start = ?"
        params.append(parse_week_start(week_start))
    query += " ORDER BY week_start DESC, counselor, year"
    return conn.execute(query, params).fetchall()


def build_html_page(rows: Iterable[sqlite3.Row], message: str = "") -> str:
    th = "".join(f"<th>{html.escape(label)}</th>" for _, label in METRIC_FIELDS)
    body_rows = []
    for row in rows:
        tds = "".join(f"<td>{row[field]}</td>" for field, _ in METRIC_FIELDS)
        body_rows.append(
            f"<tr><td>{html.escape(str(row['counselor']))}</td><td>{row['year']}</td><td>{html.escape(str(row['week_start']))}</td>{tds}</tr>"
        )
    table_body = "".join(body_rows) or "<tr><td colspan='15'>저장된 데이터가 없습니다.</td></tr>"
    safe_message = html.escape(message)

    inputs = "".join(
        f"<label>{html.escape(label)}<input type='number' name='{field}' min='0' value='0' required></label>"
        for field, label in METRIC_FIELDS
    )

    return f"""
<!doctype html>
<html lang='ko'>
<head>
  <meta charset='utf-8'>
  <title>상담사 주간보고 입력</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; }}
    form {{ display: grid; gap: 8px; max-width: 1200px; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(200px, 1fr)); gap: 8px; }}
    label {{ display: flex; flex-direction: column; font-size: 14px; gap: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 13px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px; text-align: center; }}
    th {{ background: #f5f5f5; }}
    .message {{ color: #0b6; font-weight: 700; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <h1>상담사 주간보고 입력 화면</h1>
  <p>각 상담사/연도/주차의 12개 항목을 화면에서 바로 입력하세요.</p>
  <div class='message'>{safe_message}</div>
  <form method='post' action='/save'>
    <div class='grid'>
      <label>상담사<input name='counselor' required></label>
      <label>연도
        <select name='year'>
          <option>2024</option>
          <option>2025</option>
          <option>2026</option>
        </select>
      </label>
      <label>주차 시작일<input type='date' name='week_start' required></label>
    </div>
    <div class='grid'>{inputs}</div>
    <button type='submit'>저장</button>
  </form>

  <h2>입력된 주간보고</h2>
  <table>
    <thead><tr><th>상담사</th><th>연도</th><th>주차시작일</th>{th}</tr></thead>
    <tbody>{table_body}</tbody>
  </table>
</body>
</html>
"""


def run_server(host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            message = parse_qs(parsed.query).get("message", [""])[0]
            with get_connection() as conn:
                rows = fetch_weekly_reports(conn)
            page = build_html_page(rows, message)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/save":
                self.send_error(404)
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            form = parse_qs(body)
            try:
                values = {field: int(form.get(field, ["0"])[0]) for field, _ in METRIC_FIELDS}
                report = WeeklyReport(
                    counselor=form.get("counselor", [""])[0].strip(),
                    year=int(form.get("year", [""])[0]),
                    week_start=parse_week_start(form.get("week_start", [""])[0]),
                    values=values,
                )
                if not report.counselor:
                    raise ValueError("상담사 이름은 필수입니다.")
                with get_connection() as conn:
                    upsert_weekly_report(conn, report)
                message = "저장 완료"
            except Exception as exc:  # broad for user input feedback
                message = f"오류: {exc}"

            location = f"/?message={quote_plus(message)}"
            self.send_response(303)
            self.send_header("Location", location)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"화면 입력 서버 실행: http://{host}:{port}")
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="상담사 주간보고 양식 생성/입력 도구")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_form = subparsers.add_parser("create-form", help="주간보고 CSV 양식 생성")
    create_form.add_argument("--week-start", required=True, help="YYYY-MM-DD")
    create_form.add_argument("--counselors", required=True, help='쉼표 구분 상담사 목록. 예: "홍길동,김상담"')
    create_form.add_argument("--output", required=True, help="출력 CSV 경로")

    submit_form = subparsers.add_parser("submit-form", help="작성한 주간보고 CSV를 DB로 저장")
    submit_form.add_argument("--file", required=True, help="입력 CSV 경로")

    submit_sheet = subparsers.add_parser("submit-sheet", help="구글시트 CSV 링크를 읽어 DB로 저장")
    submit_sheet.add_argument("--csv-url", required=True, help="구글시트 CSV 공개 링크")

    view = subparsers.add_parser("view", help="저장된 주간보고 조회")
    view.add_argument("--week-start", help="YYYY-MM-DD (선택)")

    serve = subparsers.add_parser("serve", help="브라우저에서 입력하는 화면 서버 실행")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create-form":
        create_weekly_form_csv(args.week_start, args.counselors.split(","), Path(args.output))
        print(f"양식 생성 완료: {args.output}")
    elif args.command == "submit-form":
        with get_connection() as conn:
            count = import_weekly_form_csv(conn, Path(args.file))
        print(f"저장 완료: {count}건")
    elif args.command == "submit-sheet":
        with get_connection() as conn:
            count = import_weekly_form_csv_url(conn, args.csv_url)
        print(f"구글시트 저장 완료: {count}건")
    elif args.command == "view":
        with get_connection() as conn:
            rows = fetch_weekly_reports(conn, args.week_start)
        labels = [label for _, label in METRIC_FIELDS]
        print("\t".join(["상담사", "연도", "주차시작일", *labels]))
        for row in rows:
            payload = [row["counselor"], row["year"], row["week_start"], *[row[field] for field, _ in METRIC_FIELDS]]
            print("\t".join(map(str, payload)))
    elif args.command == "serve":
        run_server(args.host, args.port)


if __name__ == "__main__":
    main()
