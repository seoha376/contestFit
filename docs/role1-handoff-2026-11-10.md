# 1번 데이터·백엔드 인수 메모 (2026-11-10)

## 확인한 저장소 상태

- `main`의 `444fa91` 기준으로 학교·학과 동기화, 공고 후보 저장, 검수 공고 저장, 조회 API가 이미 구현돼 있다. PDF의 11월 9일 상태 표보다 현재 파일을 우선한다.
- `web/data/departments.json`: 2025년 학과 29,359건, 학교 1,970개. 운영자가 2026-11-10에 키를 입력해 재동기화했으며 저장 시각은 `2026-11-10T01:14:09.561693+00:00`이다. 기존 동기화와 건수·내용은 같고 저장 시각만 바뀌었다. 저장된 데이터 조회에는 키가 필요 없다.
- `web/data/seed.json`: 검증 전 샘플 30건. `web/data/curated.json`: 검수 완료 실제 공고 0건. `data/contest_candidates.json`: 공식 URL 후보 12건. 후보는 웹 공고 조회 결과에 포함되지 않는다.
- 2026-11-10 기준 후보 마감일은 접수 중 11건, 만료 1건이다. 11월 10일 마감 후보도 포함된 수치이므로 실제 접수 시각은 원문에서 다시 확인해야 한다.

## 프론트엔드에 전달할 조회 계약

같은 서버 주소에서 `GET /api/contests`를 호출하면 `{schema_version, contests}`를 받는다. 검수 공고가 앞에, 샘플이 뒤에 온다. 각 공고의 핵심 필드는 `id`, `title`, `organizer`, `deadline`, `category`, `source_url`, `collected_at`, `is_sample`, `validation_status`, `sections`다. 현재 `GET /api/contests?kind=real`은 공고 0건을 반환한다. 샘플은 `is_sample: true`, `validation_status: "unverified"`이므로 실제 공고로 표시하면 안 된다.

선택적 조회 조건은 `kind=real|sample|all`, `deadline=open|unknown|all`, `q=<제목 또는 주최 검색어>`, `limit=1..200`이다. `GET /api/schools?q=서울`은 `{schools: [{name, region}], count, source, reference_year, coverage_note}`를, `GET /api/departments?q=컴퓨터`는 `{departments: [{school, major, region, family, year}], count, source, reference_year, coverage_note}`를 반환한다. 두 제안 API 모두 두 글자 이상부터 결과를 준다. `GET /api/data-status`는 다음처럼 현재 저장 데이터의 건수와 동기화 시점을 준다.

```json
{
  "sample_contests": 30,
  "verified_contests": 0,
  "departments": 29359,
  "schools": 1970,
  "reference_year": 2025,
  "synced_at": "2026-11-10T01:14:09.561693+00:00"
}
```

`tests/test_service.py`의 HTTP 계약 테스트는 실제 로컬 서버에 요청해 검수 공고 우선 순서, 샘플/실제 구분, 학교·학과 조회, 상태 응답 및 후보 비공개를 확인한다. 브라우저의 판정은 `web/decision-engine.mjs`가 수행하므로 서버가 자격 판정 결과를 확정해 주는 계약으로 해석하지 않는다.

## 공식 원문 확인 후 만든 검수 전 초안

- [용산글로벌교육지원센터의 개관 1주년 기념 애칭 공모전](https://www.yglobal.or.kr/program/list.php?idx=38&mode=view) 공식 HTML 공고를 2026-11-10에 확인했다. 공고에는 응모 대상 `누구나(지역·연령 제한 없음)`, 마감일 2026-11-20, 만 14세 미만 보호자 동의서 제출 안내가 있다. 후자는 서류 제출 조건이며 나이 제한으로 바꾸지 않았다.
- 짧은 자격 문장만 `preview_contest`에 전달해 `tmp/yglobal-preview-2026-11-10.json`을 만들었다. 이 파일은 `validation_status: "draft"`이고 Git에서 제외된다. 원문 전문을 복제하지 않았다.
- [서울특별시 행정서식 개선 아이디어 공모전](https://mediahub.seoul.go.kr/gongmo/2000785) 공식 HTML 공고도 2026-11-10에 확인했다. 원문은 개인 참가만 허용하고, 행정서식 이용 경험 및 이전 수상 취소 이력을 조건으로 둔다. 현재 프로필 필드로 확정할 수 없는 두 조건은 `other_conditions`에 남긴 검수 전 초안 `tmp/seoul-admin-form-preview-2026-11-10.json`을 만들었다. 마감일은 2026-11-20이다.
- 이 공고의 `2026. 10. 13. ~ 11. 20.` 형식에서 추출기가 시작일을 마감일로 오인하는 오류를 재현했다. `extractor.py`가 같은 연도의 축약된 종료일을 선택하도록 수정하고 회귀 테스트를 추가했다. 연도가 넘어갈 수 있는 축약 범위는 추측하지 않고 마감일을 비운다.
- 2번 담당자는 부문·조건·근거를 다시 대조하고, 4번 담당자는 실제 원문과 프로필별 판정을 검토한다. 확인 후에만 `curate` 명령으로 게시한다. 현재 실제 검수 공고 수는 계속 0건이다.

## 11일 연결과 12일 검증

1. 2번 담당자에게 `tmp/contest_review_queue.csv`를 전달한다. 이 파일은 `PYTHONPATH=src python -m posting_validation.candidates queue`로 재생성한다. 마감이 가까운 `pending` 후보부터 공식 원문, 부문별 자격, 짧은 근거를 대조한다. 후보 URL만으로 `verified`를 부여하지 않는다.
2. 검수된 공고 JSON을 받은 뒤 `PYTHONPATH=src python -m posting_validation.curate --input <검수파일.json>`으로 게시한다. 그제서야 `GET /api/contests?kind=real`에 나타난다.
3. 3번 담당자는 위 조회 계약과 `is_sample`/`validation_status`를 사용해 실제·샘플 표시를 연결한다. 검수 전 후보를 결과 목록에 섞지 않는다.
4. 4번 담당자는 실제 원문과 검수 JSON의 자격 값·근거 일치, 마감 여부, 프로필별 판정을 확인한다. 12일에는 프로필 변경, 목록 검색, 근거 표시, 새로고침, 모바일 흐름을 함께 점검한다.

학교·학과 카탈로그는 이미 있으므로 현재 작업에 API 키가 필요 없다. 공시 연도를 새로 확인해 갱신할 때만 운영자가 `DATA_GO_KR_SERVICE_KEY`를 실행 시점에 입력한다. 키를 파일, 커밋, 채팅에 넣지 않는다.
