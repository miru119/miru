# 빠른 교육 신청 접수 스크립트

`fast_register.py`는 교육신청 자동화 도구입니다.

- **실제 모드**: 로그인 + 오픈 시간 대기 + 접수 API 호출
- **테스트 모드**: 네트워크 없이 오픈 감지/재시도 흐름 시뮬레이션

## 테스트 버전(권장)

의존성 없이 바로 동작 확인할 수 있습니다.

```bash
python3 fast_register.py --test-mode
```

옵션 예시:

```bash
python3 fast_register.py --test-mode \
  --test-open-after-seconds 1 \
  --test-attempts 6 \
  --test-fail-attempts 3 \
  --test-delay-ms 50
```

## 실제 접수 모드

### 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests
```

### 준비

1. `register_config.example.json` 복사
2. 실제 사이트 기준으로 URL/payload/header 수정

```bash
cp register_config.example.json register_config.json
```

### 실행

```bash
python3 fast_register.py --config register_config.json
```

## 주의

- 서비스 약관/법규를 반드시 준수하세요.
- CAPTCHA/OTP/2차 인증이 있으면 자동화가 제한될 수 있습니다.
