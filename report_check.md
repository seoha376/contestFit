# 공모전 자격 판정 결과 점검

- 데이터: `web/data/seed.json` 30건
- 판정: 현재 `web/decision-engine.mjs`
- 프로필 ①: 만 24세, 서울 거주, 재학생, 대한민국 국적, 일반 전공, 사업자 없음, 개인 참가
- 이 보고서는 기존 값과 판정 결과를 그대로 사용했으며 새 수집, 값 보정, 재추출을 하지 않았다.

## 1. 프로필 ①의 지원 불가 공고 전체

### 1. [문화정원] 2026 (다시, 다리다) 유휴공간 활성화 아이디어 공모전

- 판정 사유: 거주 지역 조건을 충족하지 않습니다.
- 근거 문장: “- 전국 누구나 참여 가능 (개인 또는 팀)”

### 2. 2026 대구 대학(원) AI 드래프톤

- 판정 사유: 팀 참가만 가능합니다.
- 근거 문장: “같은 학교 학생 3~4인이 1팀”

### 3. 춘천MBC AI영상 공모전

- 판정 사유: 거주 지역 조건을 충족하지 않습니다.
- 근거 문장: “전국민 누구나”

### 4. 디지털 디톡스 챌린지

- 판정 사유: 허용된 신분/재학 상태에 해당하지 않습니다.
- 근거 문장: “기업형태기타참여대상직장인/일반인시상규모100만 원접수기간”

## 2. 프로필 ①의 지원 가능 공고 10건

분야와 주최가 서로 겹치지 않도록 사진·영상, 수필, 의료 슬로건, 음료 레시피, 정책 아이디어, 기업 AI, 데이터 분석, 금융 모의투자, 식품 AI, 연구논문 공모전에서 각각 1건을 골랐다.

### 1. [문화체육관광부] 2026년 충남 유교문화 사진·영상 공모전

- 비교 조건
  - `status`: `allowed=[]`, `excluded=[]`
- 근거 문장
  - `status`: “기업형태공공기관/공기업참여대상대상 제한 없음시상규모870만 원접수기간”
- 명시 없는 항목: `age`, `major_scope`, `region`, `nationality`, `business_reg`, `entry_type`, `team_size`

### 2. 제1회 꿈꾸미닷컴 꿈 수필 공모전

- 비교 조건
  - `age`: `min=14`, `max=null`, `basis_date=null`
  - `status`: `allowed=[]`, `excluded=[]`
- 근거 문장
  - `age`: “- 만 14세 이상 꿈꾸는 누구나”
  - `status`: “기업형태중소기업참여대상대상 제한 없음시상규모20만 원접수기간”
  - `status`: “- 학생, 직장인, 인생 2막을 준비하는 분 모두 환영합니다”
- 명시 없는 항목: `major_scope`, `region`, `nationality`, `business_reg`, `entry_type`, `team_size`

### 3. [건강보험심사평가원] 우리 동네 병원과 가까워지는 한마디 슬로건 공모전

- 비교 조건
  - `status`: `allowed=[]`, `excluded=[]`
- 근거 문장
  - `status`: “기업형태공공기관/공기업참여대상대상 제한 없음시상규모810만 원접수기간”
- 명시 없는 항목: `age`, `major_scope`, `region`, `nationality`, `business_reg`, `entry_type`, `team_size`

### 4. 텐퍼센트커피 커스텀 레시피 콘테스트

- 비교 조건
  - `status`: `allowed=[]`, `excluded=[]`
- 근거 문장
  - `status`: “기업형태중소기업참여대상대상 제한 없음시상규모1400만 원접수기간”
- 명시 없는 항목: `age`, `major_scope`, `region`, `nationality`, `business_reg`, `entry_type`, `team_size`

### 5. [국회미래연구원] 국회 미래세대 미래의제 공모전

- 비교 조건
  - `age`: `min=19`, `max=39`, `basis_date=null`
  - `status`: `allowed=["재학생","직장인","일반인"]`, `excluded=null`
  - `entry_type`: `both`
  - `team_size`: `min=1`, `max=1`
- 근거 문장
  - `age`: “- 공고일 현재 만 19세 이상 39세 이하의 개인 또는 팀”
  - `status`: “기업형태공공기관/공기업참여대상대학생, 직장인/일반인시상규모200만 원접수기간”
  - `entry_type`: “- 공고일 현재 만 19세 이상 39세 이하의 개인 또는 팀”
  - `team_size`: “1인(또는 팀)”
- 명시 없는 항목: `major_scope`, `region`, `nationality`, `business_reg`

### 6. LOTTE AX CHALLENGE 2026

- 비교 조건
  - `status`: `allowed=[]`, `excluded=[]`
- 근거 문장
  - `status`: “기업형태대기업참여대상대상 제한 없음시상규모2000만 원접수기간”
- 명시 없는 항목: `age`, `major_scope`, `region`, `nationality`, `business_reg`, `entry_type`, `team_size`

### 7. [한국과학기술정보연구원] 2026 DATA·AI 분석 경진대회

- 비교 조건
  - `status`: `allowed=[]`, `excluded=[]`
  - `entry_type`: `both`
- 근거 문장
  - `status`: “기업형태공공기관/공기업참여대상대상 제한 없음시상규모1300만 원접수기간”
  - `entry_type`: “- 문제해결 부문: 데이터 분석·활용에 관심 있는 개인 또는 팀(팀장1+팀원3)”
- 명시 없는 항목: `age`, `major_scope`, `region`, `nationality`, `business_reg`, `team_size`

### 8. 한국투자증권 대학생 모의투자대회 '한투모투배틀'

- 비교 조건
  - `status`: `allowed=["재학생"]`, `excluded=null`
- 근거 문장
  - `status`: “기업형태금융권참여대상대학생시상규모1830만 원접수기간”
  - `status`: “[한국투자증권 대학생 모의투자대회 '한투모투배틀' 오픈]”
- 명시 없는 항목: `age`, `major_scope`, `region`, `nationality`, `business_reg`, `entry_type`, `team_size`

### 9. [CJ제일제당] 햇반 30주년 AI 공모전 ‘갓 지은 AI디어’

- 비교 조건
  - `age`: `min=14`, `max=null`, `basis_date=null`
  - `status`: `allowed=[]`, `excluded=[]`
  - `entry_type`: `both`
  - `team_size`: `min=4`, `max=4`
- 근거 문장
  - `age`: “만 14세 이상 대한민국 거주자”
  - `status`: “기업형태대기업참여대상대상 제한 없음시상규모3000만 원접수기간”
  - `entry_type`: “개인 또는 팀(최대 4인) 참가 가능”
  - `team_size`: “개인 또는 팀(최대 4인) 참가 가능”
- 명시 없는 항목: `major_scope`, `region`, `nationality`, `business_reg`

### 10. 2026 소상공인 분야 연구논문 공모전

- 비교 조건
  - `status`: `allowed=[]`, `excluded=[]`
  - `entry_type`: `both`
  - `team_size`: `min=3`, `max=3`
- 근거 문장
  - `status`: “기업형태비영리단체/협회/재단참여대상대상 제한 없음시상규모800만 원접수기간”
  - `status`: “- 소상공인 및 지역상권 활성화 등 지역사회 현안에 관심있는 국내 대학(원)생(휴학생, 수료생 포함)”
  - `entry_type`: “- 개인 및 팀(최대 3인)′ 논문(15쪽 내외 A4 사이즈)”
  - `team_size`: “- 개인 및 팀(최대 3인)′ 논문(15쪽 내외 A4 사이즈)”
- 명시 없는 항목: `age`, `major_scope`, `region`, `nationality`, `business_reg`

## 3. 필드별 null 공고 수

30건 모두 부문이 1개이므로 공고의 해당 부문 값을 기준으로 집계했다. `age`는 `min`과 `max`가 모두 null일 때, `business_reg`는 `policy`와 `years`가 모두 null일 때 null로 셌다.

| 필드 | null 공고 수 |
|---|---:|
| `nationality` | 30 |
| `major_scope` | 30 |
| `age` | 26 |
| `region` | 28 |
| `business_reg` | 30 |

## 4. 회귀 테스트 3개 실제 결과

| 회귀 사례 | 실제 판정 결과 | 확인한 내용 | 테스트 |
|---|---|---|---|
| 꿈 수필 공모전 — 재학생 | 지원 가능 (`eligible`) | 명시된 조건을 모두 충족합니다. | 통과 |
| 꿈 수필 공모전 — 휴학생 | 지원 가능 (`eligible`) | 명시된 조건을 모두 충족합니다. | 통과 |
| 의성군 “사업자 명의 불가” — 사업자 보유자 | 확인 필요 (`needs_review`) | “사업자·창업 상태 근거는 있으나 정규화된 조건이 없습니다.” 사업자 보유 자체의 불충족으로 판정하지 않았다. | 통과 |
| “대학생, 예비창업자 등 누구나” | 확인 필요 (`needs_review`) | “나열된 신분이 요건인지 예시인지 확인이 필요합니다.” | 통과 |

회귀 테스트 실행 결과는 3개 사례 모두 통과했다. 꿈 수필 사례는 하나의 테스트에서 재학생과 휴학생 판정을 각각 검증한다.
