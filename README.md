# 상담사별 주간보고 양식 도구

요청하신 내용에 맞춰, 각 상담사별로 **2024/2025/2026년 참여자 현황**을 매주 입력할 수 있습니다.

## 화면 입력(브라우저)
아래 명령으로 입력 화면을 실행하세요.

```bash
python app.py serve --host 0.0.0.0 --port 8000
```

브라우저에서 `http://localhost:8000` 접속 후 입력하면 바로 저장됩니다.

- 입력 필드: 상담사, 연도(2024/2025/2026), 주차 시작일
- 지표(12개): 모집, 수당신청, 배정, 이관배정, 신청취하, 알선취업, 본인취업, 미인정취업, 중단, 기간만료, 사후종료(중단), 성공금 지급완료건수
- 하단 표에서 저장된 주간보고를 바로 확인 가능

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
