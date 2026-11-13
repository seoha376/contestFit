# 배포·API 키 설정 가이드 (GitHub Actions → Vercel + Supabase)

ContestFit은 GitHub Actions만으로 테스트·배포·실호출 점검을 한다. 모든 키는 **GitHub 저장소 Secret에만** 넣는다. 코드·채팅·노션·브라우저에 키를 붙여넣지 않는다.

```text
push(main) ─▶ CI (단위 테스트 + 녹화된 API 응답 E2E)
           └▶ Deploy: Supabase 마이그레이션 → Vercel 운영 배포 → 헬스 체크
                    └▶ Live check: 공식 API 실호출 점검 + 배포 사이트 E2E(데스크톱·모바일)
매일 06:17 KST ─▶ Live check (API 키 만료·응답 형식 변경 감지, Supabase 비활성 중지 방지)
```

| 구성 | 무료 범위 | 역할 |
| --- | --- | --- |
| GitHub Actions | 공개 저장소 무료 | 테스트, 마이그레이션, 배포, 실호출 점검 |
| Vercel Hobby | 무료 | 정적 웹(`web/`) + Python API 함수(`api/index.py`) |
| Supabase Free | DB 500MB, 7일 미사용 시 일시중지 | 사용자 추가 공고, 익명 의견, API 응답 캐시 |

공식 API 공고는 **요청 시 실시간 호출**하고, Supabase에는 만료 시각이 있는 캐시만 둔다(기본 30분, 원문 분석 24시간). 프로필·이름·연락처·공고 전문은 저장하지 않는다.

## 0. 포크 저장소 준비 (1회)

1. <https://github.com/seoha376/contestFit/fork> 에서 내 계정으로 포크한다. "Copy the main branch only"는 해제한다.
2. 포크의 **Actions** 탭에서 "I understand my workflows, go ahead and enable them"을 누른다. 포크는 기본적으로 워크플로가 꺼져 있다.
3. 팀 저장소에 반영할 때는 포크의 `feature/full-service` 브랜치에서 `seoha376/contestFit`의 `main`으로 Pull Request를 연다. 팀 저장소에서 배포하려면 소유자(seoha376)가 같은 Secret을 팀 저장소에 등록해야 한다(개인 저장소는 소유자만 Secret을 관리할 수 있다).

## 1. Vercel (배포)

1. <https://vercel.com/signup> 에서 GitHub 계정으로 가입한다 (Hobby).
2. 우측 상단 프로필 → **Account Settings → Tokens** → Create Token. 이름 `contestfit-actions`, Scope는 개인 계정, 만료는 팀 일정에 맞게 선택.
3. 표시된 토큰을 GitHub Secret `VERCEL_TOKEN`에 넣는다. 프로젝트는 첫 배포 때 `contestfit` 이름으로 자동 생성된다(다른 이름은 저장소 Variable `VERCEL_PROJECT_NAME`).

## 2. Supabase (무료 DB)

1. <https://supabase.com/dashboard> → New project. Region은 **Northeast Asia (Seoul)**, DB 비밀번호는 비밀번호 관리자에 보관.
2. **Project Settings → API**
   - Project URL → Secret `SUPABASE_URL`
   - `service_role` 키(Reveal) → Secret `SUPABASE_SERVICE_ROLE_KEY` (서버만 사용, 브라우저로 나가지 않음)
3. 상단 **Connect → Session pooler** 연결 문자열(`postgresql://postgres.<ref>:<비밀번호>@aws-0-...pooler.supabase.com:5432/postgres`)에 비밀번호를 채워 Secret `SUPABASE_DB_URL`에 넣는다. GitHub 러너는 IPv4만 지원하므로 Direct connection이 아니라 Session pooler를 쓴다.
4. 테이블은 배포 워크플로가 `supabase/migrations/*.sql`로 만든다. 모든 테이블은 RLS가 켜져 있고 공개 정책이 없다.

## 3. 공식 API 키 발급

| Secret 이름 | 발급처 | 절차 |
| --- | --- | --- |
| `DATA_GO_KR_SERVICE_KEY` | [공공데이터포털](https://www.data.go.kr) | 로그인 → [창업진흥원 K-Startup 조회서비스](https://www.data.go.kr/data/15125364/openapi.do) **활용신청**(자동승인) → 마이페이지 → 개발계정 → **일반 인증키(Decoding)**. 같은 키로 [전국대학별학과정보](https://www.data.go.kr/data/15107737/standard.do)도 활용신청한다(학과 목록 갱신용). |
| `KOCCA_SERVICE_KEY` | [한국콘텐츠진흥원 OPEN API](https://www.kocca.kr/kocca/subPage.do?menuNo=204796&gubun=tab01) | 공공데이터포털 키와 **다른 키**다. 콘텐츠진흥원 회원 로그인 → OPEN API → 활용신청 → API 키조회. |
| `KCTF_API_KEY` | [K-CTF](https://k-ctf.org/api/docs) | 회원가입 → 마이페이지 → API 키 발급. 발급 순간에만 보이므로 바로 Secret에 넣는다. |
| `KAGGLE_USERNAME`, `KAGGLE_KEY` | [Kaggle](https://www.kaggle.com/settings) | Settings → API → Create New Token → 내려받은 `kaggle.json`의 `username`, `key` 값을 각각 넣는다. |
| `WORK24_AUTH_KEY` | [고용24 OPEN-API](https://www.work24.go.kr/cm/e/a/0110/selectOpenApiSvcInfo.do) | 로그인 → 채용정보 API 신청 → 승인 후 인증키(authKey). 승인까지 시간이 걸릴 수 있다. |
| `CAREERNET_API_KEY` | [커리어넷 Open API](https://www.career.go.kr/cnet/front/openapi/openApiMajorCenter.do) | 인증키 신청 → 관리자 발급 후 신청 현황에서 확인. |

키가 없는 출처는 화면에 "키 미설정"으로 표시되고 나머지는 정상 동작한다. 서울시 공모전 목록과 Codeforces는 키가 필요 없다.

## 4. GitHub Secret 등록

포크 저장소 → **Settings → Secrets and variables → Actions → New repository secret**에서 아래 이름 그대로 등록한다.

```text
VERCEL_TOKEN
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_DB_URL
DATA_GO_KR_SERVICE_KEY
KOCCA_SERVICE_KEY
KCTF_API_KEY
KAGGLE_USERNAME
KAGGLE_KEY
WORK24_AUTH_KEY
CAREERNET_API_KEY
```

선택: Variables 탭에 `PRODUCTION_URL`(운영 주소)을 넣으면 매일 점검이 Vercel API 조회 없이 그 주소를 쓴다.

## 5. 배포와 확인

1. **Actions → Deploy → Run workflow** (또는 `main`에 push).
2. 실행 요약(Summary)에서 확인한다.
   - `Deploy to Vercel`: 배포 주소
   - `Official API calls`: 출처별 상태·건수·응답 시간 표
   - `Live E2E`: 데스크톱·모바일 결과, `e2e-report-live` 아티팩트(스크린샷, 출처·필터·프로필별 결과 JSON)
3. 실패하면 표의 오류 문구로 원인을 찾는다. `HTTP 401/403`은 키·활용신청 승인, `연결 실패`는 일시 장애, `형식이 예상과 다릅니다`는 API 응답 형식 변경이다.

## 로컬 실행

```bash
# 녹화된 공식 API 응답으로 전체 화면 확인 (네트워크·키 불필요)
CONTESTFIT_SOURCE_MODE=fixture PYTHONPATH=src python -m posting_validation.service
# 실제 API 호출 (필요한 키를 환경변수로 넣은 셸에서)
CONTESTFIT_SOURCE_MODE=live PYTHONPATH=src python -m posting_validation.service
# API 실호출 점검표
PYTHONPATH=src python -m posting_validation.sources.check
# E2E (fixture)
npm ci && npx playwright install chromium && npx playwright test
```
