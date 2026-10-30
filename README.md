# ContestFit

ContestFit은 저장된 공모전 본문에서 자격 조건을 추출하고, 사용자의 프로필과 명시 조건을 비교해 `지원 가능`, `확인 필요`, `지원 불가`를 보여주는 로컬 검증 프로토타입이다.

현재 저장소는 다음 두 부분으로 구성된다.

- Python 3.11+ 표준 라이브러리 기반 수집·정제·추출·평가 코드
- 빌드 도구와 프레임워크가 없는 HTML/CSS/JavaScript 정적 웹 UI

외부 LLM API, 데이터베이스, 로그인, 런타임 비밀키는 사용하지 않는다. 웹 프로토타입의 프로필은 브라우저 `localStorage`에만 저장된다.

## 빠른 시작

필요한 도구:

- Python 3.11 이상
- Node.js 20 이상(테스트 실행용)
- Git

별도의 Python·Node 패키지 설치는 필요하지 않다.

```bash
git clone <REPOSITORY_URL>
cd contestFit
python -m http.server 8000 --directory web
```

브라우저에서 <http://127.0.0.1:8000>을 연다. HTML 파일을 직접 열면 ES 모듈과 `seed.json` 로딩이 차단될 수 있으므로 로컬 서버를 사용한다.

### 운영체제별 참고

- Windows에서 `python`이 Microsoft Store를 열거나 실행되지 않으면 Python 3.11 이상을 설치한 뒤 `py -3` 또는 설치된 `python.exe` 경로를 사용한다.
- PowerShell의 `$env:PYTHONPATH='src'`는 현재 터미널 세션에만 적용된다. 새 터미널에서는 다시 설정한다.
- macOS/Linux에서는 `python` 명령이 없고 `python3`만 제공될 수 있다. 이 경우 아래 명령의 `python`을 `python3`으로 바꾼다.
- 경로 구분자는 문서 예시처럼 명령을 실행하는 셸에 맞춘다. 프로젝트 코드와 CI는 저장소 상대 경로를 사용한다.

## 표준 검사 명령

### macOS / Linux

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
node --test tests/web/decision-engine.test.mjs
python -m compileall -q src tests
node --check web/decision-engine.mjs
node --check web/config.mjs
node --check web/app.mjs
```

### Windows PowerShell

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
node --test tests/web/decision-engine.test.mjs
python -m compileall -q src tests
node --check web/decision-engine.mjs
node --check web/config.mjs
node --check web/app.mjs
```

## 프로젝트 구조

```text
src/posting_validation/       Python 추출·평가 파이프라인
  collector.py                robots.txt·요청 간격·예산을 지키는 수집기
  parser.py                   HTML/XML/날짜 파싱
  extractor.py                본문 기반 속성·자격 조건 추출
  eligibility.py              Python 규칙 기반 대표 프로필 판정
  evaluator.py                근거 일치·채움률·판정 보고서 생성
  diagnosis.py                null 원인 진단
  web_seed.py                 추출 결과를 웹 seed 스키마로 변환
  cli.py                      파이프라인 CLI
web/                          정적 웹 프로토타입
  decision-engine.mjs         프레임워크 비의존 순수 판정 함수
  config.mjs                  프로필·필터·임계값 설정
  app.mjs                     DOM, localStorage, 화면 렌더링
  data/seed.json              웹 실행에 사용하는 30건 검증 데이터
tests/                        Python unittest와 Node 내장 테스트
raw/                          외부 원문 로컬 사본; Git 업로드 금지
manifest*.json                수집 시점·URL·raw 파일 참조 기록
extracted*.json               추출 결과와 근거 발췌
metrics*.json                 평가 집계
report*.md                    실험·진단·판정 보고서
```

## 데이터 흐름

```text
raw 본문 + manifest
        ↓ extractor.py
extracted_eligibility.json
        ↓ web_seed.py
web/data/seed.json
        ↓ decision-engine.mjs
브라우저 판정 결과
```

`raw/`는 원문 HTML과 전문을 포함하며 재배포하지 않는다. Git으로 clone한 환경에서는 기존 `web/data/seed.json`으로 웹과 테스트를 실행할 수 있지만, `raw/` 없이 전체 재추출은 할 수 없다. 현재 JSON 산출물에서는 비밀키와 일반적인 이메일·전화번호 패턴이 발견되지 않았으나, 데이터 갱신 시 다시 검토해야 한다.

## 로컬 데이터 재변환

이미 존재하는 `extracted_eligibility.json`을 웹 데이터로 다시 변환할 때만 다음 명령을 사용한다. 네트워크를 사용하지 않는다.

```bash
PYTHONPATH=src python -m posting_validation.cli --web-seed-only
```

PowerShell에서는 먼저 `$env:PYTHONPATH='src'`를 설정한다.

기본 CLI와 `--eligibility` 실행은 기존 수집기를 호출해 외부 사이트에 요청할 수 있다. 일반적인 개발·테스트·웹 실행에는 필요하지 않으며, 데이터 수집 권한과 정책을 확인한 경우에만 사용한다.

## 환경변수와 비밀정보

현재 필수 환경변수는 없다. `PYTHONPATH=src`는 로컬 소스 경로 설정일 뿐 비밀정보가 아니다. 향후 비밀값이 필요해지면 실제 `.env`는 커밋하지 않고 변수 이름과 설명만 `.env.example`에 추가한다.

## 협업

- `main`은 항상 실행·테스트 가능한 상태로 유지한다.
- 작업마다 `feature/<짧은-설명>` 브랜치를 만든다.
- 변경은 Pull Request로 병합하고 관련 테스트 결과를 기록한다.
- 폴더나 브랜치를 특정 팀원 또는 역할에 고정하지 않는다.
- 한 사람이 여러 영역을 함께 수정할 수 있다.

자세한 절차는 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고한다. 자동화 도구와 코딩 에이전트는 [AGENTS.md](AGENTS.md)를 먼저 읽는다.

## 현재 범위 밖

프론트엔드·백엔드 역할 분배, 서버 API, 데이터베이스, 배포 환경, 인증, 운영용 데이터 수집 방식은 아직 확정하지 않는다. 실제 요구사항이 정해진 뒤 별도 설계로 결정한다.
