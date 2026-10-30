import test from "node:test";
import assert from "node:assert/strict";

import { DEFAULT_SETTINGS, judgeContest, validateDecisionEvidence } from "../../web/decision-engine.mjs";

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
