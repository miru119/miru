#!/usr/bin/env python3
"""교육 신청 접수 자동화 스크립트.

기본 모드: 실제 사이트 로그인/접수 요청 수행
테스트 모드: 네트워크 호출 없이 동작 흐름만 검증
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

try:
    import requests
except ModuleNotFoundError:
    requests = None  # type: ignore[assignment]


@dataclass(slots=True)
class RegisterConfig:
    login_url: str
    register_url: str
    username: str
    password: str
    login_payload: dict[str, Any]
    register_payload: dict[str, Any]
    headers: dict[str, str]
    open_time: datetime
    before_open_poll_ms: int = 10
    after_open_attempts: int = 8
    timeout_seconds: float = 2.0


@dataclass(slots=True)
class TestConfig:
    open_after_seconds: float = 1.5
    attempts: int = 5
    fail_attempts: int = 2
    delay_ms: int = 80


def parse_config(path: str) -> RegisterConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    required = {
        "login_url",
        "register_url",
        "username",
        "password",
        "login_payload",
        "register_payload",
        "headers",
        "open_time",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise ValueError(f"config 누락 키: {', '.join(missing)}")

    return RegisterConfig(
        login_url=raw["login_url"],
        register_url=raw["register_url"],
        username=raw["username"],
        password=raw["password"],
        login_payload=raw["login_payload"],
        register_payload=raw["register_payload"],
        headers=raw["headers"],
        open_time=datetime.fromisoformat(raw["open_time"]),
        before_open_poll_ms=int(raw.get("before_open_poll_ms", 10)),
        after_open_attempts=int(raw.get("after_open_attempts", 8)),
        timeout_seconds=float(raw.get("timeout_seconds", 2.0)),
    )


def build_session(cfg: RegisterConfig):
    if requests is None:
        raise RuntimeError(
            "requests 패키지가 없어 실제 모드를 실행할 수 없습니다. "
            "테스트는 --test-mode 로 실행하세요."
        )
    session = requests.Session()
    session.headers.update(cfg.headers)
    return session


def server_now(session, url: str, timeout_seconds: float) -> datetime:
    response = session.head(url, timeout=timeout_seconds)
    response.raise_for_status()
    date_header = response.headers.get("Date")
    if not date_header:
        raise RuntimeError("서버 Date 헤더를 가져오지 못했습니다.")
    return parsedate_to_datetime(date_header)


def wait_until_open(session, cfg: RegisterConfig) -> None:
    interval = max(cfg.before_open_poll_ms, 1) / 1000.0
    print(f"[INFO] 접수 오픈 시각까지 대기: {cfg.open_time.isoformat()}")

    while True:
        now = server_now(session, cfg.register_url, cfg.timeout_seconds)
        if now >= cfg.open_time.astimezone(now.tzinfo):
            print(f"[INFO] 오픈 감지: {now.isoformat()}")
            return
        time.sleep(interval)


def login(session, cfg: RegisterConfig) -> None:
    payload = dict(cfg.login_payload)
    payload.setdefault("username", cfg.username)
    payload.setdefault("password", cfg.password)

    res = session.post(
        cfg.login_url,
        data=payload,
        headers=cfg.headers,
        timeout=cfg.timeout_seconds,
    )
    res.raise_for_status()
    print("[INFO] 로그인 요청 성공")


def try_register(session, cfg: RegisterConfig) -> bool:
    for attempt in range(1, cfg.after_open_attempts + 1):
        started = time.perf_counter()
        res = session.post(
            cfg.register_url,
            data=cfg.register_payload,
            headers=cfg.headers,
            timeout=cfg.timeout_seconds,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        ok = 200 <= res.status_code < 300
        print(f"[TRY {attempt:02d}] status={res.status_code} elapsed={elapsed_ms:.1f}ms success={ok}")
        if ok:
            print("[SUCCESS] 접수 요청이 성공 상태코드를 반환했습니다.")
            return True

    print("[FAIL] 지정한 횟수 내에 접수 성공 응답을 받지 못했습니다.")
    return False


def run_test_mode(cfg: TestConfig) -> int:
    now = datetime.now(timezone.utc).astimezone()
    open_time = now + timedelta(seconds=cfg.open_after_seconds)
    print("[TEST] 네트워크 호출 없이 접수 흐름을 시뮬레이션합니다.")
    print(f"[TEST] 가상 오픈 시각: {open_time.isoformat()}")

    while datetime.now(open_time.tzinfo) < open_time:
        time.sleep(0.05)

    print("[TEST] 오픈 감지 완료")

    for attempt in range(1, cfg.attempts + 1):
        started = time.perf_counter()
        time.sleep(max(cfg.delay_ms, 0) / 1000.0)
        success = attempt > cfg.fail_attempts
        status = 200 if success else 429
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(f"[TEST TRY {attempt:02d}] status={status} elapsed={elapsed_ms:.1f}ms success={success}")
        if success:
            print("[TEST SUCCESS] 테스트 접수 성공")
            return 0

    print("[TEST FAIL] 테스트 접수 실패")
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="교육 접수 자동화 도구")
    parser.add_argument("--config", default="register_config.json", help="설정 JSON 경로")
    parser.add_argument("--test-mode", action="store_true", help="실제 호출 없이 시뮬레이션 실행")
    parser.add_argument("--test-open-after-seconds", type=float, default=1.5)
    parser.add_argument("--test-attempts", type=int, default=5)
    parser.add_argument("--test-fail-attempts", type=int, default=2)
    parser.add_argument("--test-delay-ms", type=int, default=80)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.test_mode:
        tcfg = TestConfig(
            open_after_seconds=args.test_open_after_seconds,
            attempts=args.test_attempts,
            fail_attempts=args.test_fail_attempts,
            delay_ms=args.test_delay_ms,
        )
        return run_test_mode(tcfg)

    cfg = parse_config(args.config)
    with build_session(cfg) as session:
        login(session, cfg)
        wait_until_open(session, cfg)
        success = try_register(session, cfg)
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        if requests is not None and isinstance(exc, requests.RequestException):
            print(f"[ERROR] 네트워크/HTTP 에러: {exc}")
            raise SystemExit(2)
        print(f"[ERROR] 실행 에러: {exc}")
        raise SystemExit(3)
