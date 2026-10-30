# AGENTS.md

이 파일은 ContestFit 저장소에서 작업하는 자동화 도구와 코딩 에이전트를 위한 지침이다.

## 우선순위

1. 현재 동작과 저장된 데이터 경로를 보존한다.
2. 실제 코드와 테스트를 문서보다 우선한다.
3. 요청 범위 밖의 아키텍처 변경을 하지 않는다.
4. 변경 후 관련 테스트와 전체 표준 검사를 실행한다.

## 구조와 경계

- Python 코드는 `src/posting_validation/`에 있다.
- 정적 웹은 `web/`에 있다.
- `web/decision-engine.mjs`는 DOM, 브라우저 API, 프레임워크에 의존하지 않는 순수 판정 모듈로 유지한다.
- `web/app.mjs`만 DOM과 localStorage를 다룬다.
- 웹은 `web/data/seed.json`을 사용한다.
- Python 추출 결과에서 웹 스키마로의 변환은 `web_seed.py`가 담당한다.

## 금지 사항

- 명시적 요청 없이 외부 사이트에 접속하거나 수집기를 실행하지 않는다.
- 외부 LLM API, 로그인 우회, 인증정보를 추가하지 않는다.
- `raw/` 또는 `raw2/` 내용을 커밋 대상으로 만들지 않는다.
- 기존 데이터, 보고서, 회귀 테스트를 임의로 삭제하거나 기대값을 편의상 변경하지 않는다.
- 새 DB, 서버 프레임워크, 번들러, 패키지 관리 체계를 필요 없이 도입하지 않는다.
- 특정 개발자나 역할에 폴더·브랜치를 고정하지 않는다.

## 변경 규칙

- 추출 규칙 변경: `extractor.py`와 Python 회귀 테스트를 함께 수정한다.
- 웹 seed 스키마 변경: `web_seed.py`, `seed.json`, 판정 엔진, UI 소비 코드와 테스트를 함께 확인한다.
- 판정 규칙 변경: 먼저 `tests/web/decision-engine.test.mjs`에 회귀 사례를 추가한다.
- 근거 없는 값을 추측하지 않는다. 불명확한 조건은 `확인 필요`를 유지한다.
- 판정 사유와 evidence가 같은 조건을 설명하는지 검증한다.

## 표준 검사

```text
PYTHONPATH=src python -m unittest discover -s tests -v
node --test tests/web/decision-engine.test.mjs
python -m compileall -q src tests
node --check web/decision-engine.mjs
node --check web/config.mjs
node --check web/app.mjs
```

Windows PowerShell에서는 `PYTHONPATH=src` 대신 `$env:PYTHONPATH='src'`를 사용한다.

## 데이터 안전

- 새 산출물을 커밋하기 전에 비밀키, 이메일, 전화번호, 개인식별정보를 검색한다.
- 외부 원문 전문은 재배포하지 않는다.
- 데이터 출처, 생성 명령, 수집 시점을 PR에 기록한다.
