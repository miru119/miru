# 상담사별 주간보고 양식 도구

요청하신 내용에 맞춰, 각 상담사별로 **2024/2025/2026년 참여자 현황**을 매주 입력할 수 있습니다.

## 구글시트에서 입력해서 반영하기
1. `create-form`으로 초기 양식을 만들고 구글시트에 업로드해 공유합니다.
2. 구글시트에서 매주 수치를 입력합니다.
3. 아래 `submit-sheet` 명령으로 구글시트 값을 DB에 반영합니다.

```bash
python app.py submit-sheet --csv-url "https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit#gid=0"
```

- `edit` 링크를 넣어도 자동으로 `export?format=csv` 링크로 변환해서 읽습니다.
- 시트는 "링크가 있는 사용자 보기 가능" 이상으로 공개되어야 읽을 수 있습니다.

## 화면 입력(브라우저)
아래 명령으로 입력 화면을 실행하세요.

```bash
python app.py serve --host 0.0.0.0 --port 8000
```

브라우저에서 `http://localhost:8000` 접속 후 입력하면 바로 저장됩니다.

## CSV 양식 방식도 사용 가능

### 1) 주간보고 양식 생성
```bash
python app.py create-form --week-start 2024-01-01 --counselors "홍길동,김상담" --output weekly_report_2024-01-01.csv
```

### 2) 양식 작성 후 제출(저장)
```bash
python app.py submit-form --file weekly_report_2024-01-01.csv
```

### 3) 조회
```bash
python app.py view --week-start 2024-01-01
```

저장 데이터는 `weekly_participant_stats.db`(SQLite)에 누적됩니다.

## 테스트
```bash
python -m unittest discover -s tests
```
