# 데이터·백엔드 담당 실행 가이드

2026-11-09 확인 기준. 13일 사용자 테스트 전에는 기존 JSON 경로와 API 응답 형태를 유지한다. 공고 후보, 검수된 공고, 검증 전 샘플은 서로 다른 상태다.

## 필요한 키와 발급 순서

### 전국 대학·학과 검색: 공공데이터포털 인증키 필요

1. [공공데이터포털](https://www.data.go.kr/)에 가입하거나 로그인한다.
2. [전국대학별학과정보표준데이터](https://www.data.go.kr/data/15107737/standard.do) 페이지에서 **오픈 API**와 **활용신청**을 선택한다. 해당 페이지는 개발단계 자동승인, 개발계정 트래픽 10,000을 안내한다.
3. 활용 목적에 ContestFit의 학교·학과명 검색 보조를 적고 신청한다. 승인 및 인증키 상태는 로그인한 계정의 활용신청 내역에서 확인한다. 포털 메뉴 이름은 변경될 수 있으므로 데이터 상세 페이지에서 신청 내역으로 이동한다.
4. 발급 화면에 인코딩/디코딩 인증키가 모두 있으면 **디코딩 인증키**를 사용한다. 현재 Python 코드는 URL 파라미터를 한 번 인코딩한다. 키를 코드, Git, 채팅, 브라우저 주소에 넣지 않는다.
5. 데이터 페이지의 실제 연도(`YR`)를 확인한다. 2026-11-09에 보이는 표 예시에는 2025년 행이 있다. 아래 명령의 `2025`는 예시이며 최신으로 제공되는 연도를 확인해 바꾼다.

PowerShell에서 저장소 루트로 이동한 뒤 실행한다. 키 입력은 화면에 표시되지 않고 현재 셸의 환경변수에만 들어간다.

```powershell
$secret = Read-Host '공공데이터포털 디코딩 인증키' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $env:DATA_GO_KR_SERVICE_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$env:PYTHONPATH = 'src'
python -m posting_validation.departments --year 2025
Remove-Item Env:DATA_GO_KR_SERVICE_KEY
```

전체 페이지를 못 받거나 지정 연도의 학과가 0건이면 기존 카탈로그를 보존한다. 성공하면 `web/data/departments.json`에 학교·학과·지역·계열, 기준연도, 동기화 시각, 중복 제거된 학교 목록이 저장된다. API는 `serviceKey`, `pageNo`, `numOfRows`(최대 1000), `type=json`, `YR`을 사용한다. 이 API는 공모전 목록이나 개인의 실제 재학 여부를 제공하지 않는다.

### 공모전 후보: 공통 API 키 없음

현재 연결한 전국 공모전 통합 API는 없다. 주최 기관의 공식 공고 URL을 찾아 **후보 메타데이터**만 등록한다. 공식 웹페이지 또는 PDF에서 제목·주최·마감일을 확인한 뒤 CSV 또는 JSON으로 입력한다. 후보 등록은 네트워크를 호출하지 않고 자격을 판정하지 않는다. 주최 기관별 API를 추가할 때도 원문 확인 전에는 후보 상태를 유지한다.

CSV 헤더:

```csv
source_url,title,organizer,deadline,category,source_name
```

```powershell
$env:PYTHONPATH = 'src'
python -m posting_validation.candidates import --input .\tmp\my-contests.csv
python -m posting_validation.candidates report
python -m posting_validation.candidates queue
```

중복 기준은 `source_url`이며, 동일 URL을 다시 가져오면 제목·마감일을 갱신하고 최초 발견 시각을 유지한다. 잘못된 행이 하나라도 있으면 파일을 교체하지 않는다. 후보 파일 `data/contest_candidates.json`은 웹 공개 폴더 밖에 있으며 제목·URL 같은 메타데이터만 저장한다. 2026-11-09 기준 공식 페이지에서 확인한 후보 12건의 주소가 이 파일에 있다. **후보 12건은 서비스에 게시된 실제 공고 12건이 아니다.**

서울시 공식 공모전 목록은 다음 명령으로 수동 갱신한다. 공개 목록 1페이지만 읽고, robots.txt를 확인한 뒤 마감이 지나지 않았으며 180일 이내인 항목의 제목·마감일·분야·공식 상세 URL만 후보로 저장한다. 페이지 구조가 바뀌어 0건을 얻으면 기존 파일을 유지한다. 서울시 목록은 전국 공모전 전체를 포괄하지 않으며 주최기관이 서울시가 아닌 항목도 있으므로 `organizer`는 빈 값으로 유지한다.

```powershell
$env:PYTHONPATH = 'src'
python -m posting_validation.seoul_feed --dry-run
python -m posting_validation.seoul_feed
python -m posting_validation.candidates report
python -m posting_validation.candidates queue
```

`queue`는 `tmp/contest_review_queue.csv`에 검수 인수 목록을 만든다. `deadline_state`는 `open`·`expired`·`undated`, `review_status`는 `pending`·`published`다. `published`는 `curated.json`에 같은 URL의 `verified` 공고가 있을 때만 표시된다. 이 CSV는 메타데이터만 담고 `tmp/`에 있어 Git에 포함되지 않는다. 2번 담당자에게 전달할 때는 마감이 가까운 `pending` 공고부터 원문을 확인한다.

### 문서화된 실제 공모전 API: K-CTF

[K-CTF 공식 API 문서](https://k-ctf.org/api/docs)는 접수 중인 정보보안 대회를 JSON으로 조회하는 `GET /api/v1/contests?status=registering`을 제공한다. ContestFit은 이 API의 **읽기 기능만** 사용하며 `apply_end_date`가 확인된 경우에만 후보의 마감일로 저장한다. 대회 종료일 `end_date`를 접수 마감일로 바꾸지 않는다. API 응답에 참가 자격이 없거나 불명확하면 그대로 검수 전 후보로 둔다. 정보보안 분야에 한정되어 전국 모든 전공의 공모전 API를 대체하지 않는다.

1. [K-CTF](https://k-ctf.org/) 회원가입 후 로그인한다.
2. 마이페이지에서 API 키를 발급한다. 키는 발급 순간에만 표시된다고 공식 문서가 안내하므로 안전한 비밀번호 관리자에 보관한다.
3. **기존 공공데이터포털 키와 다른 키**다. PowerShell에서 아래처럼 화면에 표시되지 않도록 입력한다.
4. `--dry-run` 결과를 확인한 뒤 동기화한다. 키를 파일·Git·채팅에 넣지 않는다.

```powershell
$secret = Read-Host 'K-CTF API 키' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $env:KCTF_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$env:PYTHONPATH = 'src'
python -m posting_validation.kctf_feed --dry-run
python -m posting_validation.kctf_feed
Remove-Item Env:KCTF_API_KEY
python -m posting_validation.candidates queue
```

K-CTF 목록은 최대 2페이지(페이지당 50건)만 조회한다. 이 명령은 브라우저에서 호출하지 않고 운영자가 수동 실행한다. 현재 계정 키가 없으므로 **실제 API 호출 성공 여부와 후보 수는 아직 검증되지 않았다.**

### 전국 분야 확대용 API 접근

[콘테스트코리아의 API 연동 안내](https://www.contestkorea.com/sub/banner_product_dn.php?str_gbn=2)는 캠페인 목록·상세 조회를 제공하지만, 신청 후 검토·승인·견적을 거쳐 API 명세와 키를 발급하는 절차다. 따라서 현재는 호출 주소·응답 필드·이용 조건을 알 수 없고, 임의로 연결 코드를 만들거나 사이트의 내부 API를 호출하지 않는다. 전국 분야를 확대하려면 운영자가 제휴 문의를 통해 **목록/상세 필드, 참가 자격과 마감일 포함 여부, 재배포 허용 범위, 비용, 호출 한도**를 먼저 확인해야 한다. 명세와 키가 제공되면 동일한 검수 전 후보 저장 경로에 어댑터를 추가한다.

## 후보에서 검수된 공고까지

1. 후보 URL을 2번 자격 판정 담당자에게 넘긴다. 공식 공고의 부문별 참가 조건과 짧은 원문 근거를 확인한다.
2. `POST /api/preview` 또는 화면의 단건 미리보기를 사용해 검수용 JSON을 만든다. PDF는 자동 열람하지 않으므로 제목과 참가 자격 문장을 직접 붙여넣는다.
3. 검수된 JSON만 `python -m posting_validation.curate --input <검수파일.json>`으로 게시한다. 게시 파일은 `web/data/curated.json`이며 같은 URL은 교체된다.
4. 4번 검증 담당자가 실제 원문과 판정 결과를 비교한다. 확인하지 않은 조건을 채우거나 후보를 `verified`로 표시하지 않는다.

## 저장 모델과 API 계약

| 데이터 | 현재 저장소 | 식별·관계 | 향후 DB로 옮길 때의 테이블 |
| --- | --- | --- | --- |
| 공식 공고 후보 | `data/contest_candidates.json` | 공식 URL 유일, URL 해시 ID | `contest_candidates` |
| 검수된 공고 | `web/data/curated.json` | 공식 URL 유일, 공고 ID | `contests` |
| 부문별 조건 | 공고의 `sections[]` | `contest_id` → `section.id` | `contest_sections` |
| 조건 근거 | `sections[].evidence` | 부문 ID + 조건 필드 | `condition_evidence` |
| 대학·학과 | `web/data/departments.json` | 기준연도 + 학교 + 학과 + 지역 | `departments`, `schools` |
| 기존 샘플 | `web/data/seed.json` | `is_sample=true` | 별도 시드 테이블 또는 파일 |

13일 시연 규모에서는 원자적 JSON 교체와 URL 중복 제거로 운영한다. 동시 편집·대규모 검색이 실제 문제가 되면 DB나 Elasticsearch를 도입하되 아래 응답 형태를 유지한다. Elasticsearch 연결이나 별도 키는 현재 필요하지 않다.

| 경로 | 응답/용도 |
| --- | --- |
| `GET /api/contests` | 기존 화면 계약. 검수 공고 뒤에 샘플을 붙여 반환 |
| `GET /api/contests?kind=real&deadline=open&q=AI&limit=20` | 선택적 서버 검색. `kind=real|sample|all`, `deadline=open|unknown|all` |
| `GET /api/schools?q=서울` | 학교명 제안. `schools: [{name, region}]`과 전체 학교 수 |
| `GET /api/departments?q=컴퓨터` | 학과명 제안. `departments: [...]`와 전체 학과 수 |
| `GET /api/data-status` | 샘플·검수 공고·학교·학과 건수와 동기화 연도·시각 |

조회 API는 웹과 같은 서버 주소를 사용한다. 기본 주소 `127.0.0.1`은 개발 PC에서만 열린다. 외부 10명 테스트에는 별도의 접근 가능한 HTTPS 운영 환경이 필요하며, 공개 배포 전에 사용자 입력 URL을 서버가 읽는 `/api/preview`와 의견 저장 API의 운영 범위를 팀에서 점검한다.

## 13일 전 인수 기준

- 대학·학과 동기화 성공 시 `GET /api/data-status`의 건수와 기준연도를 기록한다. 이후 키가 없어도 저장된 카탈로그로 검색할 수 있다.
- 2026-11-09 동기화 결과: 2025년 학과 29,359건, 학교명 1,970개. `GET /api/schools?q=서울`이 새 카탈로그를 반환하는 것을 확인했다.
- 공고 후보 URL·마감일을 2번 담당자에게 전달하고, 검수된 건만 실제 목록에 게시한다. 2026-11-09 후보 12건은 `tmp/contest_review_queue.csv`로 인수한다.
- 3번 담당자에게 위 API 형태와 샘플/실제/검수 전 상태를 전달한다.
- 4번 담당자에게 출처 URL, 확인 시각, 중복·만료 처리 결과를 전달한다.
- 원문 전문, 인증키, 이메일, 전화번호, 사용자 프로필은 데이터 산출물에 저장하지 않는다.
