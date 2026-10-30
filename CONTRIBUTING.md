# ContestFit 기여 가이드

## 기본 원칙

- `main`은 안정된 코드와 재현 가능한 테스트 상태를 유지한다.
- 담당자별 폴더나 고정 브랜치를 만들지 않는다.
- 한 사람이 Python, 웹, 데이터, 문서를 함께 수정해도 된다.
- 기존 자격 추출·판정 규칙과 회귀 테스트를 이유 없이 변경하지 않는다.
- 새 프레임워크, 데이터베이스, 외부 서비스는 합의된 요구사항이 생긴 뒤 도입한다.

## 작업 흐름

1. 최신 `main`을 받는다.
2. 작업별 브랜치를 만든다.
3. 범위가 작은 변경과 관련 테스트를 함께 작성한다.
4. 표준 검사를 실행한다.
5. 원격 브랜치에 push하고 Pull Request를 연다.
6. 리뷰와 CI를 통과한 뒤 `main`에 병합한다.

```bash
git switch main
git pull --ff-only
git switch -c feature/<short-description>
```

버그 수정은 `fix/<short-description>`, 문서만 수정할 때는 `docs/<short-description>`를 사용할 수 있다. 브랜치 이름은 업무를 설명해야 하며 사람 이름이나 역할명으로 고정하지 않는다.

## 변경 전 확인

- 웹 UI는 `web/data/seed.json`을 직접 읽는다.
- 판정 규칙은 `web/decision-engine.mjs`의 순수 함수로 유지한다.
- Python 추출 스키마를 바꾸면 `web_seed.py`, 웹 판정 엔진, 관련 테스트와 문서를 함께 확인한다.
- `raw/`와 `raw2/`는 외부 원문이므로 커밋하지 않는다.
- 생성 데이터에 이메일, 전화번호, 개인식별정보, API 키가 포함되지 않았는지 확인한다.
- 수집기 실행은 일반 개발 과정에 포함하지 않는다.

## PR 전 검사

macOS/Linux:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
node --test tests/web/decision-engine.test.mjs
python -m compileall -q src tests
node --check web/decision-engine.mjs
node --check web/config.mjs
node --check web/app.mjs
```

Windows PowerShell:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
node --test tests/web/decision-engine.test.mjs
python -m compileall -q src tests
node --check web/decision-engine.mjs
node --check web/config.mjs
node --check web/app.mjs
```

변경 범위에 따라 브라우저에서 다음도 확인한다.

- 프로필 변경 시 즉시 재판정되는가
- 새로고침 후 localStorage 값이 유지되는가
- 전체/가능/확인 필요/불가 필터와 상세 근거가 동작하는가
- 원문 링크와 검증 전 데이터 안내가 유지되는가

## 데이터 변경

- `web/data/seed.json`을 수정했다면 어떤 로컬 산출물과 명령에서 생성했는지 PR에 기록한다.
- 추출값과 근거 문장을 임의로 보정하지 않는다.
- 기존 데이터 파일을 이동하거나 삭제하지 않는다.
- `raw/`가 없는 팀원도 웹과 테스트를 실행할 수 있도록 필요한 검증용 `seed.json`은 유지한다.

## Pull Request

- 한 PR은 하나의 목적을 갖도록 한다.
- 변경 이유, 영향 범위, 실행한 테스트, 데이터 변경 여부를 적는다.
- 관련 없는 포맷 변경이나 대규모 리팩터링을 섞지 않는다.
- CI가 실패하면 원인을 해결한 뒤 리뷰를 요청한다.
- 병합 방식과 리뷰 승인 수는 GitHub 저장소 생성 후 팀 설정으로 결정한다.
