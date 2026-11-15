# 판정 함수 계약 (2번 자격 판정 엔진 → 3번 프론트엔드 공유)

실제 판정은 `web/decision-engine.mjs`가 브라우저에서 수행한다. DOM, 브라우저 API,
프레임워크에 의존하지 않는 순수 모듈이다. 서버 판정 API는 없다.
Python `src/posting_validation/eligibility.py`는 오프라인 진단용이며 별도 판정기로
재구축하지 않는다.

## 함수 목록

| 함수 | 용도 |
|---|---|
| `judgeContest(contest, profile, settings?)` | 공고 1건의 3상태 판정. 웹(`web/app.mjs`)이 사용하는 진입점 |
| `judgeAll(contests, profile, settings?)` | 공고 목록 일괄 판정. `{ contest, decision }` 배열 반환 |
| `evaluateSection(section, profile, settings?)` | 부문 1개의 판정. `judgeContest` 내부에서 부문별로 호출 |
| `validateDecisionEvidence(decision)` | `ineligible` 판정의 근거 일치 여부를 다시 검증한다. 근거가 불일치한 사유 목록 반환 |
| `DEFAULT_SETTINGS` | `{ confidenceThreshold: 0.7 }`. 웹은 `APP_CONFIG.confidenceThreshold`와 같은 0.7을 넘긴다 |

호출 형태(웹 기준):

```js
import { judgeContest } from "./decision-engine.mjs";
const decision = judgeContest(
  contest,
  { ...profile, selectedSectionId: selectedSections[contest.id] || "" },
  { confidenceThreshold: 0.7 },
);
```

## 입력 1: 공고(contest)

판정이 읽는 필드는 다음과 같다. 그 외 필드(`title`, `organizer`, `deadline` 등)는
판정에 쓰이지 않는다.

| 필드 | 형태 | 설명 |
|---|---|---|
| `id` | 문자열 | 공고 식별자 |
| `validation_status` | 문자열 | `"draft"`이면 부문 판정과 무관하게 전체 `needs_review` |
| `sections` | 배열 | 부문 목록. 비어 있으면 `needs_review` |

부문(section) 필드:

| 필드 | 형태 | 설명 |
|---|---|---|
| `id` | 문자열 | 부문 식별자. `possibleSections`와 `selectedSectionId` 대조에 쓰인다 |
| `name` | 문자열 또는 null | 부문 이름 |
| `age` | `{ min, max, basis_date }` | 연령 범위. `basis_date`가 있으면 기준일 확인이 필요해 `needs_review` |
| `status` | `{ allowed, excluded }` | 허용·제외 신분 목록. 빈 배열은 "제한 없음"으로 취급한다 |
| `major_scope` | 문자열 또는 배열 또는 null | 전공/소속 조건. 학교·학과를 함께 지정할 수 있다 |
| `region` | 문자열/객체 또는 null | 지역 조건. 객체면 `{ basis, regions }`, `basis`는 `residence`/`school`/`affiliation` |
| `nationality` | 문자열 또는 배열 또는 null | 국적 조건 |
| `business_reg` | `{ policy, years, name_restriction }` | `policy`는 `required`/`forbidden`/null |
| `entry_type` | `"individual"`/`"team"`/`"both"`/null | 참가 형태 |
| `team_size` | `{ min, max }` 또는 null | 팀 인원 범위. 프로필이 팀 참가일 때만 검사한다 |
| `other_conditions` | 문자열 배열 | 정규화되지 않은 추가 조건. 권고성 문장(시상식 필참, 1인 1작품, 보호자 동의 등)은 제외하고 나머지는 `needs_review` 사유가 된다 |
| `evidence` | 필드별 원문 발췌 | 근거 문장. 문자열 또는 문자열 배열. `ineligible` 판정은 본문 근거가 있어야 확정된다 |
| `evidence_source` | 필드별 출처 | `"body"`(본문) 또는 `"chip"`. 칩 출처 근거만으로는 `ineligible`이 확정되지 않는다 |
| `confidence` | 필드별 숫자 | 해석 신뢰도. 0.7 미만이면 `needs_review` 사유가 된다 |

참고: 데이터 파일에 있는 `chip_mismatch`·`chip_evidence` 필드는 엔진이 읽지 않는다.
칩 출처와 본문 출처의 우선순위는 `evidence_source`로만 판단한다.

## 입력 2: 프로필(profile)

`web/config.mjs`의 `EMPTY_PROFILE` 키를 그대로 쓴다. 판정 엔진이 읽는 키는
`skills`·`interests`를 제외한 전부다. (`skills`·`interests`는 관련성 엔진
`fit-engine.mjs` 전용이다.)

| 키 | 형태 | 설명 |
|---|---|---|
| `status` | 문자열 | 신분. `재학생`, `휴학생`, `대학원생`, `수료생`, `직장인`, `일반인`, `예비창업자` 중 하나 |
| `nationality` | 문자열 | `대한민국` 또는 `외국인` |
| `age` | 숫자 또는 빈 문자열 | 만 나이 |
| `affiliation` | 문자열 | 전공/소속. `major_scope` 대조에 학교명과 합쳐서 쓴다 |
| `school` | 문자열 | 학교명 |
| `region` | 문자열 | 거주 지역 |
| `schoolRegion` | 문자열 | 학교 소재지. 지역 조건의 기준이 `school`일 때 쓴다 |
| `affiliationRegion` | 문자열 | 소속 소재지. 지역 조건의 기준이 `affiliation`일 때 쓴다 |
| `businessStatus` | 문자열 | `none`, `prospective`, `registered` |
| `businessYears` | 숫자 또는 빈 문자열 | 창업 연차 |
| `entryType` | 문자열 | `individual` 또는 `team` |
| `teamSize` | 숫자 또는 빈 문자열 | 팀 인원 |
| `selectedSectionId` | 문자열 | 사용자가 고른 부문 id. 비어 있으면 전 부문 판정을 합친다 |

비어 있는 값(빈 문자열·`null`·키 없음)은 "입력 없음"으로 같다. 조건이 명시됐는데
해당 프로필 값이 없으면 `missing_profile` 사유로 `needs_review`가 된다.

## 출력: 판정(decision)

```jsonc
{
  "result": "eligible" | "needs_review" | "ineligible",
  "reasons": [ { "field": "…", "kind": "…", "message": "…", "evidence": "…" } ],
  "sections": [ /* 부문별 판정, evaluateSection 반환값 */ ],
  "possibleSections": ["<eligible인 부문 id>"],
  "missingFields": ["<조건도 근거도 없는 필드>"],
  "otherConditions": ["<부문들의 other_conditions 합집합>"]
}
```

부문별 판정(`evaluateSection` 반환값)은 다음과 같다.

```jsonc
{
  "sectionId": "…",
  "sectionName": "…" | null,
  "result": "eligible" | "needs_review" | "ineligible",
  "reasons": [ /* 해당 부문의 사유 목록 */ ],
  "specifiedFields": ["<명시된 조건 필드>"],
  "missingFields": ["<조건도 근거도 없는 필드>"],
  "otherConditions": ["…"]
}
```

`selectedSectionId`로 부문을 고르면 판정 결과는 고른 부문의 결과를 그대로 쓰되
`sections`와 `possibleSections`도 함께 반환한다.

## 판정 사유(reason) kind 목록

| kind | 의미 | 결과 |
|---|---|---|
| `matched` | 명시된 조건을 모두 충족 | `eligible` |
| `mismatch` | 조건 불충족. 본문 근거가 있고 근거 문구가 사유와 일치할 때만 확정 | `ineligible` |
| `missing_profile` | 조건은 있으나 비교할 프로필 값이 없음 | `needs_review` |
| `unclear_evidence` | 불충족인데 근거가 본문 조건과 명확히 일치하지 않음. `mismatch`를 격하시킨다 | `needs_review` |
| `unverified_import` | `validation_status: "draft"`인 공고 | `needs_review` |
| `section_divergence` | 부문별 판정이 달라 부문 선택이 필요 | `needs_review` |
| `unmodeled_condition` | 정규화되지 않은 추가 조건이 있음 | `needs_review` |
| `unmapped_evidence` | 근거는 있으나 정규화된 조건이 없음 | `needs_review` |
| `low_confidence` | 조건 해석 신뢰도가 0.7 미만 | `needs_review` |
| `ambiguous_enumeration` | 나열된 신분이 요건인지 예시인지 불분명 | `needs_review` |
| `contradiction` | 조건의 최소·최대 또는 허용·제외가 모순 | `needs_review` |
| `basis_date` | 연령 기준일에 맞춘 만 나이 확인이 필요 | `needs_review` |

## 3상태 결정 규칙 (보수적 설계)

- `ineligible`은 조건 불충족 + 본문 근거 + 근거 문구 일치 세 가지가 모두 갖춰질 때만
  확정된다. 하나라도 빠지면 `needs_review`로 격하된다.
- `needs_review`는 프로필 누락, 근거 누락·모호, 정규화되지 않은 조건, 부문 불일치,
  `draft` 상태 중 하나라도 해당하면 된다.
- `eligible`은 명시된 조건을 모두 충족할 때만 나온다. 명시된 조건이 하나도 없으면
  확인할 대상이 없어 `eligible`이 되므로, 조건이 비어 있는 실제 공고는 검수 단계에서
  걸러야 한다.

## 상태별 응답 예시

아래는 `web/data/seed.json` 실데이터에 예시 프로필
(재학생·23세·대한민국·ITM·서울과학기술대학교·서울·개인 참가)을 넣은 실제 출력이다.
`settings`는 `{ confidenceThreshold: 0.7 }`이다.

### 지원 가능 — 제1회 꿈꾸미닷컴 꿈 수필 공모전

```json
{
  "result": "eligible",
  "reasons": [
    { "field": "all", "kind": "matched", "message": "명시된 조건을 모두 충족합니다.", "evidence": null }
  ],
  "sections": [
    {
      "sectionId": "31018040a0476696-section-1",
      "sectionName": null,
      "result": "eligible",
      "reasons": [
        { "field": "all", "kind": "matched", "message": "명시된 조건을 모두 충족합니다.", "evidence": null }
      ],
      "specifiedFields": ["age", "status"],
      "missingFields": ["major_scope", "region", "nationality", "business_reg", "entry_type", "team_size"],
      "otherConditions": []
    }
  ],
  "possibleSections": ["31018040a0476696-section-1"],
  "missingFields": ["major_scope", "region", "nationality", "business_reg", "entry_type", "team_size"],
  "otherConditions": []
}
```

### 확인 필요 — 2026 데이터+AI 혁신 챌린지 데이터 문제해결 부문 경진대회

```json
{
  "result": "needs_review",
  "reasons": [
    {
      "field": "other_conditions",
      "kind": "unmodeled_condition",
      "message": "정규화되지 않은 추가 자격 조건을 확인해야 합니다.",
      "evidence": "참여 대상: 2026년 데이터 문제해결 부문 경진대회 참가 신청자"
    }
  ],
  "sections": [
    {
      "sectionId": "20bba634f2e9bbfd-section-1",
      "sectionName": null,
      "result": "needs_review",
      "reasons": [
        {
          "field": "other_conditions",
          "kind": "unmodeled_condition",
          "message": "정규화되지 않은 추가 자격 조건을 확인해야 합니다.",
          "evidence": "참여 대상: 2026년 데이터 문제해결 부문 경진대회 참가 신청자"
        }
      ],
      "specifiedFields": [],
      "missingFields": ["age", "status", "major_scope", "region", "nationality", "business_reg", "entry_type", "team_size"],
      "otherConditions": ["참여 대상: 2026년 데이터 문제해결 부문 경진대회 참가 신청자"]
    }
  ],
  "possibleSections": [],
  "missingFields": ["age", "status", "major_scope", "region", "nationality", "business_reg", "entry_type", "team_size"],
  "otherConditions": ["참여 대상: 2026년 데이터 문제해결 부문 경진대회 참가 신청자"]
}
```

### 지원 불가 — 2026 대구 대학(원) AI 드래프톤

```json
{
  "result": "ineligible",
  "reasons": [
    {
      "field": "entry_type",
      "kind": "mismatch",
      "message": "팀 참가만 가능합니다.",
      "evidence": "같은 학교 학생 3~4인이 1팀"
    }
  ],
  "sections": [
    {
      "sectionId": "cdd42e0d01944f9d-section-1",
      "sectionName": null,
      "result": "ineligible",
      "reasons": [
        {
          "field": "entry_type",
          "kind": "mismatch",
          "message": "팀 참가만 가능합니다.",
          "evidence": "같은 학교 학생 3~4인이 1팀"
        }
      ],
      "specifiedFields": ["age", "status", "entry_type", "team_size"],
      "missingFields": ["major_scope", "region", "nationality", "business_reg"],
      "otherConditions": []
    }
  ],
  "possibleSections": [],
  "missingFields": ["major_scope", "region", "nationality", "business_reg"],
  "otherConditions": []
}
```

## 경계

- 이 계약은 자격 판정 전용이다. 주제 관련성은 `web/fit-engine.mjs`의
  `evaluateFit`이 담당하며 판정 결과와 섞지 않는다.
- 검수 상태(`is_sample`, `validation_status`) 표시는 프론트 담당이다. 엔진은
  `draft` 게이트만 적용하고, `unverified` 샘플도 조건을 충족하면 `eligible`을
  반환한다. 검증 결과와 판단 근거는 `docs/role2-judgment-verification-2026-11-12.md`를
  참조한다.
