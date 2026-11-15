import test from "node:test";
import assert from "node:assert/strict";

import { DEFAULT_SETTINGS, judgeContest, validateDecisionEvidence } from "../../web/decision-engine.mjs";
import { evaluateFit, titleTopics } from "../../web/fit-engine.mjs";

const baseProfile = {
  status: "재학생",
  nationality: "대한민국",
  age: 24,
  affiliation: "일반 전공",
  region: "서울",
  businessStatus: "none",
  businessYears: null,
  entryType: "individual",
  teamSize: 1,
};

function contest(section) {
  return {
    id: "sample",
    title: "샘플 공모전",
    validation_status: "unverified",
    sections: [{
      id: "default",
      name: null,
      age: { min: null, max: null, basis_date: null },
      status: { allowed: null, excluded: null },
      major_scope: null,
      region: null,
      nationality: null,
      business_reg: { policy: null, years: null },
      entry_type: null,
      team_size: null,
      other_conditions: [],
      evidence: {},
      confidence: {},
      ...section,
    }],
  };
}

test("꿈 수필 공모전은 재학생과 휴학생을 직장인 전용으로 오판하지 않는다", () => {
  const dreamEssay = contest({
    age: { min: 14, max: null, basis_date: null },
    status: { allowed: [], excluded: [] },
    evidence: {
      age: "만 14세 이상 꿈꾸는 누구나",
      status: ["대상 제한 없음", "학생, 직장인, 인생 2막을 준비하는 분 모두 환영합니다"],
    },
    confidence: { age: 0.95, status: 0.95 },
  });

  assert.equal(judgeContest(dreamEssay, baseProfile, DEFAULT_SETTINGS).result, "eligible");
  assert.equal(judgeContest(dreamEssay, { ...baseProfile, status: "휴학생" }, DEFAULT_SETTINGS).result, "eligible");
});

test("사업자 명의 불가 문구는 사업자 보유자 자체를 배제하지 않는다", () => {
  const uiseong = contest({
    status: { allowed: [], excluded: [] },
    entry_type: "individual",
    business_reg: { policy: null, years: null },
    evidence: {
      status: "국민 누구나 개인 자격으로 참가 가능",
      entry_type: "국민 누구나 개인 자격으로 참가 가능, 법인·단체·사업자 명의 불가",
      business_reg: "국민 누구나 개인 자격으로 참가 가능, 법인·단체·사업자 명의 불가",
    },
    confidence: { status: 0.95, entry_type: 0.95, business_reg: null },
  });

  const result = judgeContest(uiseong, { ...baseProfile, businessStatus: "registered", businessYears: 4 }, DEFAULT_SETTINGS);
  assert.notEqual(result.result, "ineligible");
  assert.ok(result.reasons.every((reason) => reason.field !== "business_reg" || reason.kind !== "mismatch"));
});

test("등 누구나가 붙은 열거형 자격은 예시인지 요건인지 불명확해 확인 필요다", () => {
  const ambiguousEnumeration = contest({
    status: { allowed: ["대학생", "예비창업자"], excluded: [] },
    evidence: { status: "대학생, 예비창업자 등 누구나" },
    confidence: { status: 0.95 },
  });

  const result = judgeContest(ambiguousEnumeration, baseProfile, DEFAULT_SETTINGS);
  assert.equal(result.result, "needs_review");
  assert.ok(result.reasons.some((reason) => reason.kind === "ambiguous_enumeration"));
});

test("모든 부문에서 명시 조건을 어길 때만 지원 불가다", () => {
  const ageRestricted = contest({
    age: { min: null, max: 20, basis_date: null },
    evidence: { age: "만 20세 이하" },
    confidence: { age: 0.9 },
  });
  assert.equal(judgeContest(ageRestricted, baseProfile, DEFAULT_SETTINGS).result, "ineligible");

  ageRestricted.sections.push({
    ...ageRestricted.sections[0],
    id: "open",
    age: { min: 20, max: 30, basis_date: null },
    evidence: { age: "만 20세 이상 30세 이하" },
  });
  assert.equal(judgeContest(ageRestricted, baseProfile, DEFAULT_SETTINGS).result, "needs_review");
});

test("임계값보다 낮은 confidence와 누락된 프로필 값은 확인 필요다", () => {
  const lowConfidence = contest({
    region: "서울",
    evidence: { region: "서울 거주자" },
    confidence: { region: 0.6 },
  });
  assert.equal(judgeContest(lowConfidence, baseProfile, { confidenceThreshold: 0.7 }).result, "needs_review");

  const missingProfile = contest({
    nationality: "대한민국",
    evidence: { nationality: "대한민국 국민" },
    confidence: { nationality: 0.9 },
  });
  assert.equal(judgeContest(missingProfile, { ...baseProfile, nationality: "" }, DEFAULT_SETTINGS).result, "needs_review");
});

test("자동 추출 후 검수 전인 공고는 지원 가능으로 표시하지 않는다", () => {
  const draft = { ...contest({ status: { allowed: ["재학생"], excluded: [] }, evidence: { status: "재학생" } }), validation_status: "draft" };
  const result = judgeContest(draft, baseProfile, DEFAULT_SETTINGS);
  assert.equal(result.result, "needs_review");
  assert.equal(result.reasons[0].kind, "unverified_import");
});

test("공고가 별도 연령 기준일을 지정하면 현재 만 나이로 확정 판정하지 않는다", () => {
  const datedAge = contest({
    age: { min: null, max: 24, basis_date: "2026-12-31" },
    evidence: { age: "2026년 12월 31일 기준 만 24세 이하" },
  });
  assert.equal(judgeContest(datedAge, baseProfile, DEFAULT_SETTINGS).result, "needs_review");
  assert.equal(judgeContest(datedAge, { ...baseProfile, age: 25 }, DEFAULT_SETTINGS).result, "needs_review");
});

test("역량 관계는 지원 자격과 별도로 근거가 있는 키워드만 설명한다", () => {
  const item = { ...contest({}), title: "AI 영상 공모전", topic_tags: [], skill_signals: [{ name: "영상 편집", evidence: "영상 편집 결과물을 제출" }] };
  const fit = evaluateFit(item, { skills: ["영상 편집"], interests: ["인공지능"] });
  assert.equal(fit.level, "related");
  assert.deepEqual(fit.matchedSkills, ["영상 편집"]);
  assert.ok(fit.reasons.some((value) => value.includes("제목")));
  assert.equal(judgeContest(item, baseProfile).result, "eligible");
});

test("공고에 역량 정보가 없거나 키워드가 달라도 부적합으로 단정하지 않는다", () => {
  assert.equal(evaluateFit({ title: "새 공모전" }, { skills: ["Python"] }).level, "unknown");
  assert.equal(evaluateFit({ title: "AI 공모전" }, { skills: ["글쓰기"] }).level, "no_signal");
});

test("영문 역량 키워드는 대소문자를 구분하지 않는다", () => {
  const fit = evaluateFit({ title: "서비스 공모전", skill_signals: [{ name: "python", evidence: "Python 개발 결과물" }] }, { skills: ["Python"] });
  assert.deepEqual(fit.matchedSkills, ["python"]);
});

test("선택형 역량은 공고 제목의 주제와 분야 수준에서 연결된다", () => {
  const fit = evaluateFit({ title: "AI 활용 영상 공모전" }, { skills: ["AI 활용", "영상 편집"], interests: [] });
  assert.equal(fit.level, "related");
  assert.deepEqual(fit.matchedTopics, ["AI", "영상"]);
  assert.ok(fit.reasons.some((value) => value.includes("역량 분야")));
});

test("지자체 이름의 시를 글쓰기 주제로 해석하지 않는다", () => {
  assert.equal(titleTopics("광양시 AI 영상 공모전").includes("글쓰기"), false);
});

test("학교와 학과가 함께 지정된 조건은 둘 다 맞아야 한다", () => {
  const item = contest({ major_scope: "서울대학교 컴퓨터공학과", evidence: { major_scope: "서울대학교 컴퓨터공학과 재학생" } });
  const matching = { ...baseProfile, school: "서울대학교", affiliation: "컴퓨터공학과" };
  const otherMajor = { ...matching, affiliation: "기계공학과" };
  const missingMajor = { ...matching, affiliation: "" };
  assert.equal(judgeContest(item, matching).result, "eligible");
  assert.notEqual(judgeContest(item, otherMajor).result, "eligible");
  assert.equal(judgeContest(item, missingMajor).result, "needs_review");
  assert.equal(judgeContest(item, { ...matching, school: "" }).result, "needs_review");
});

test("전국 누구나는 서울 거주자를 지역 불충족으로 만들지 않는다", () => {
  const openNationwide = contest({
    region: null,
    evidence: { region: null },
  });
  assert.notEqual(judgeContest(openNationwide, baseProfile, DEFAULT_SETTINGS).result, "ineligible");
});

test("개인 또는 팀 최대 4인은 3인 팀을 허용한다", () => {
  const upToFour = contest({
    entry_type: "both",
    team_size: { min: null, max: 4 },
    evidence: { entry_type: "개인 또는 팀(최대 4인)", team_size: "개인 또는 팀(최대 4인)" },
  });
  const result = judgeContest(upToFour, { ...baseProfile, entryType: "team", teamSize: 3 }, DEFAULT_SETTINGS);
  assert.notEqual(result.result, "ineligible");
});

test("대상 제한 없음 칩보다 대학원생 한정 본문을 우선한다", () => {
  const bodyRestricted = contest({
    status: { allowed: ["재학생", "대학원생"], excluded: [], chip_mismatch: true },
    evidence: { status: "국내 대학(원)생만 참가 가능" },
    evidence_source: { status: "body" },
  });
  const worker = { ...baseProfile, status: "직장인" };
  assert.notEqual(judgeContest(bodyRestricted, worker, DEFAULT_SETTINGS).result, "eligible");
});

test("직장인 일반인 칩만으로 재학생을 불가 처리하지 않는다", () => {
  const chipOnly = contest({
    status: { allowed: null, excluded: null, chip_mismatch: false },
    evidence: { status: null },
    chip_evidence: { status: "참여대상직장인/일반인" },
  });
  assert.notEqual(judgeContest(chipOnly, baseProfile, DEFAULT_SETTINGS).result, "ineligible");
});

test("불가 판정 사유와 본문 근거의 조건 표현이 일치해야 한다", () => {
  const valid = {
    result: "ineligible",
    reasons: [
      { field: "region", kind: "mismatch", message: "거주 지역 조건을 충족하지 않습니다.", evidence: "서울특별시 거주자" },
      { field: "status", kind: "mismatch", message: "허용 신분이 아닙니다.", evidence: "국내 대학 재학생만 참가 가능" },
    ],
  };
  const invalid = {
    result: "ineligible",
    reasons: [{ field: "region", kind: "mismatch", message: "거주 지역 조건을 충족하지 않습니다.", evidence: "전국 누구나" }],
  };
  assert.deepEqual(validateDecisionEvidence(valid), []);
  assert.equal(validateDecisionEvidence(invalid).length, 1);
});

test("정규화하지 못한 부문 자격은 확인 필요지만 유의사항은 판정에서 제외한다", () => {
  const unmodeled = contest({
    other_conditions: ["문제 해결이 필요한 기관 또는 개인"],
    evidence: { other_conditions: "문제 해결이 필요한 기관 또는 개인" },
  });
  const noticeOnly = contest({
    other_conditions: ["수상자는 시상식 필참"],
    evidence: { other_conditions: "수상자는 시상식 필참" },
  });
  assert.equal(judgeContest(unmodeled, baseProfile, DEFAULT_SETTINGS).result, "needs_review");
  assert.equal(judgeContest(noticeOnly, baseProfile, DEFAULT_SETTINGS).result, "eligible");
});

test("자격 정보가 없는 공식 API 공고는 지원 가능으로 단정하지 않는다", () => {
  const apiContest = { ...contest({}), eligibility_known: false };
  const decision = judgeContest(apiContest, baseProfile);
  assert.equal(decision.result, "needs_review");
  assert.equal(decision.reasons[0].kind, "eligibility_unknown");
  // 기존 데이터(플래그 없음)는 기존 판정을 유지한다.
  assert.equal(judgeContest(contest({}), baseProfile).result, "eligible");
});

test("계열 조건은 학과 카탈로그의 계열로 비교한다", () => {
  const engineering = contest({
    major_scope: "공학계열",
    evidence: { major_scope: "공학계열 전공 재학생" },
    evidence_source: { major_scope: "body" },
  });
  const engineer = { ...baseProfile, affiliation: "산업공학과", school: "서울과학기술대학교", majorFamily: "공학" };
  assert.equal(judgeContest(engineering, engineer).result, "eligible");
  const business = { ...baseProfile, affiliation: "경영학과", school: "연세대학교", majorFamily: "인문사회" };
  assert.equal(judgeContest(engineering, business).result, "ineligible");
  const unknownFamily = { ...baseProfile, affiliation: "자유전공학부", school: "예시대학교", majorFamily: "" };
  assert.equal(judgeContest(engineering, unknownFamily).result, "needs_review");
});

test("이공계 조건은 공학과 자연 계열을 모두 허용한다", () => {
  const stem = contest({
    major_scope: "이공계 전공",
    evidence: { major_scope: "이공계 전공자 대상" },
    evidence_source: { major_scope: "body" },
  });
  assert.equal(judgeContest(stem, { ...baseProfile, affiliation: "수학과", majorFamily: "자연과학" }).result, "eligible");
  assert.equal(judgeContest(stem, { ...baseProfile, affiliation: "국어국문학과", majorFamily: "인문사회" }).result, "ineligible");
  const social = contest({ major_scope: "사회계열", evidence: { major_scope: "사회계열 전공자" }, evidence_source: { major_scope: "body" } });
  assert.equal(judgeContest(social, { ...baseProfile, affiliation: "경영학과", majorFamily: "인문사회" }).result, "eligible");
});

test("관련 전공 표현은 학과명이 달라도 불가로 단정하지 않는다", () => {
  const related = contest({
    major_scope: "IT 관련 전공",
    evidence: { major_scope: "IT 관련 전공 대학생" },
    evidence_source: { major_scope: "body" },
  });
  const decision = judgeContest(related, { ...baseProfile, affiliation: "산업공학과", majorFamily: "공학" });
  assert.equal(decision.result, "needs_review");
  assert.equal(decision.reasons[0].kind, "related_major");
});
