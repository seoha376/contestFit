# ContestFit

ContestFit은 공모전 자격 조건을 추출하고 사용자의 프로필과 명시 조건을 비교해 `지원 가능`, `확인 필요`, `지원 불가`를 보여주는 웹서비스 뼈대다.

현재 저장소는 다음 두 부분으로 구성된다.

- Python 3.11+ 표준 라이브러리 기반 추출·평가·단건 미리보기 API
- 빌드 도구와 프레임워크가 없는 HTML/CSS/JavaScript 정적 웹 UI

외부 LLM API, 데이터베이스, 로그인은 사용하지 않는다. 프로필은 브라우저 `localStorage`에만 저장된다. URL 미리보기는 요청 시 공식 공고 1건만 열람하며 자동 추출 결과는 검수 전으로 표시된다. 전국 학과 API 동기화에 필요한 키는 운영자가 환경변수로만 제공한다.

## 빠른 시작

필요한 도구:

- Python 3.11 이상
- Node.js 20 이상(테스트 실행용)
- Git

별도의 Python·Node 패키지 설치는 필요하지 않다.

Windows PowerShell:

```powershell
cd C:\Users\song\Documents\GitHub\contestFit
$env:PYTHONPATH='src'
python -m posting_validation.service
```

macOS/Linux: `PYTHONPATH=src python -m posting_validation.service`. 브라우저에서 <http://127.0.0.1:8000>을 연다. HTML 파일 직접 열기 또는 단순 정적 서버에서는 API 기능이 동작하지 않는다.

### 공고 등록과 사용자 테스트

1. 주최 기관의 공식 공고 URL을 입력한다. 자동 열람이 허용되지 않거나 PDF라면 공고의 제목·자격 문장을 함께 붙여넣는다. 타사 공고 모음 사이트의 URL은 처리하지 않는다.
2. 미리보기 결과는 브라우저에만 임시 표시되며 항상 `확인 필요`다. 검수용 JSON을 내려받아 원문의 각 자격 값과 짧은 근거 문장을 대조·수정한다.
3. 검수한 파일을 게시한다. Windows에서는 `$env:PYTHONPATH='src'; python -m posting_validation.curate --input <검수파일.json>`을 실행한다. macOS/Linux에서는 `PYTHONPATH=src python -m posting_validation.curate --input <검수파일.json>`을 실행한다. 이 명령은 `web/data/curated.json`에 공고를 추가하거나 같은 URL의 공고를 교체한다. 서버를 새로고침하면 실제 공고로 보인다. 검수 여부는 팀이 원문과 대조한 경우에만 표시한다.
4. 테스트 참여자는 프로필 입력 → 공고 검색 → 판정 이유·원문 확인 후 화면 아래의 익명 의견을 제출한다. 서버는 과제 완료, 이유 이해, 편의성 점수와 시각만 `tmp/feedback.jsonl`에 기록한다. 이름·프로필은 보내거나 저장하지 않는다.

프로필에 역량과 관심 주제를 입력하면 공고 제목의 주제 키워드 및 검수된 공고의 명시 역량 문장과 비교해 관계를 설명한다. 이는 자격 판정과 분리되어 있으며 키워드가 다르다고 지원 불가로 처리하지 않는다. 실제 공고 JSON에는 검수자가 `topic_tags`와 `skill_signals: [{"name":"영상 편집","evidence":"원문 짧은 근거"}]`를 추가할 수 있다.

대학명은 두 글자부터 입력하면 공식 학과 카탈로그에 포함된 대학명을 자동 제안한다. 대학을 고르면 소재지도 채운다. 역량과 관심 주제는 분야별 버튼을 여러 개 선택할 수 있고 목록에 없는 값은 직접 추가할 수 있다. 이전에 브라우저에 저장된 입력 값도 유지한다. 선택 역량과 공고 제목의 주제 연결은 탐색 힌트이며 해당 역량이 공모전의 필수 조건이라는 뜻은 아니다.

전국 학과 검색을 연결하려면 [공공데이터포털의 전국대학별학과정보표준데이터](https://www.data.go.kr/data/15107737/standard.do) 활용신청 후, 확인한 공시 연도를 지정해 동기화한다. 예를 들어 PowerShell에서 `$env:DATA_GO_KR_SERVICE_KEY='<발급키>'; $env:PYTHONPATH='src'; python -m posting_validation.departments --year 2025`를 실행한다. 키는 파일이나 Git에 저장하지 않는다. 결과는 `web/data/departments.json`에 학교·학과·지역·계열만 저장한다. 동기화하지 않아도 학과명을 직접 입력할 수 있다. 학과 API는 공모전 목록을 제공하지 않는다.

공모전 공급원 조사와 세 담당자의 구현 경계는 [데이터 공급원 및 작업 인계](docs/data-sources-and-handoff.md)에 정리했다.

분야 필터는 검수 JSON의 `category`에 팀이 확인한 분야를 기입한 공고에만 나타난다. 빈 분야를 추측해 채우지 않는다. 정확도 평가는 `[{"contest_id":"...","profile":{...},"expected":"eligible"}]` 형태의 수기 정답 파일을 만든 뒤 `node scripts/evaluate.mjs <수기정답.json>`으로 실행한다. 결과에는 전체 정확도와 잘못된 `지원 가능` 건수·비율이 함께 나온다. 정답 120건은 실제 원문과 대표 프로필을 확인하며 팀이 작성해야 한다.

`GET /api/contests`는 검수된 공고와 기존 샘플을 함께 반환한다. `GET /api/departments?q=학과명`과 `GET /api/schools?q=대학명`은 동기화된 학과 카탈로그에서 검색 제안을 반환한다. `POST /api/preview`는 `{source_url, text?}`를 받아 임시 공고를 반환하고, `POST /api/feedback`은 `{task_completed, reason_clear, ease}`를 받는다. 이후 공식 공모전 API의 실제 응답 형식이 확인되면 출처별 어댑터를 이 공고 스키마에 연결한다.

이 서비스는 기본적으로 로컬 주소에만 연결된다. 다른 기기에서 테스트하려면 접근 가능한 환경에 배포해야 하며, 배포 전 공식 URL 접근 정책과 서버의 공개 API 운영 조건을 확인한다. 현재 `curated.json`과 전국 학과 카탈로그는 비어 있고 기존 30건은 모두 검증 전 샘플이다. 실제 사용 결과를 주장하기 전에 공식 원문 검수와 사용 기록이 필요하다.

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
  departments.py              공식 전국 학과 API 동기화·검색
  service.py                  정적 웹·단건 미리보기·익명 의견 API
  curate.py                   원문 대조 후 실제 공고 게시
  cli.py                      파이프라인 CLI
web/                          정적 웹 프로토타입
  decision-engine.mjs         프레임워크 비의존 순수 판정 함수
  fit-engine.mjs              역량·관심 주제 관계 설명
  config.mjs                  프로필·필터·임계값 설정
  app.mjs                     DOM, localStorage, 화면 렌더링
  data/seed.json              웹 실행에 사용하는 검증 전 샘플 30건
  data/curated.json           팀이 검수해 게시한 실제 공고
  data/departments.json       공식 학과 카탈로그 검색용 축약 데이터
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

DB 선택, 배포 환경, 상시 자동 수집은 아직 확정하지 않았다. 실제 사용과 공식 공급원 계약이 정해진 뒤 결정한다.
