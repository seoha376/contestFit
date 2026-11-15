import test from "node:test";
import assert from "node:assert/strict";

import { buildJsonResume, resumeFileName, resumeGaps, resumeMajor, JSON_RESUME_SCHEMA } from "../../web/resume-export.mjs";
import { EMPTY_PROFILE } from "../../web/config.mjs";

const NOW = new Date("2026-11-15T03:00:00.000Z");

const fullProfile = {
  status: "재학생",
  nationality: "대한민국",
  age: 23,
  school: "서울과학기술대학교",
  affiliation: "산업공학과",
  majorFamily: "공학",
  skills: ["Python", "데이터 분석", "발표", "Rust"],
  interests: ["AI", "데이터", "AI"],
  region: "서울",
  businessStatus: "prospective",
  entryType: "team",
  teamSize: 3,
};

test("학교·전공·신분·역량·관심 분야·거주 지역을 JSON Resume 구조로 옮긴다", () => {
  const resume = buildJsonResume(fullProfile, { name: "  홍길동 ", email: "gildong@example.com", summary: "데이터로 문제를 푸는 학생", now: NOW });

  assert.equal(resume.$schema, JSON_RESUME_SCHEMA);
  assert.deepEqual(resume.basics, {
    name: "홍길동",
    label: "산업공학과 재학생",
    email: "gildong@example.com",
    summary: "데이터로 문제를 푸는 학생",
    location: { countryCode: "KR", region: "서울" },
  });
  assert.deepEqual(resume.education, [{ institution: "서울과학기술대학교", area: "산업공학과" }]);
  assert.deepEqual(resume.skills, [
    { name: "개발·데이터", keywords: ["Python", "데이터 분석"] },
    { name: "디자인·콘텐츠", keywords: ["발표"] },
    { name: "기타", keywords: ["Rust"] },
  ]);
  assert.deepEqual(resume.interests, [{ name: "관심 분야", keywords: ["AI", "데이터"] }]);
  assert.deepEqual(resume.meta, { version: "v1.0.0", lastModified: "2026-11-15T03:00:00.000Z", generator: "ContestFit" });
});

test("공고 자격 판정용 정보(나이·국적·사업자·참가 형태)는 이력서에 넣지 않는다", () => {
  const resume = buildJsonResume(fullProfile, { now: NOW });
  const serialized = JSON.stringify(resume);
  // 값(대한민국·prospective·team)과 키(age·nationality·teamSize)가 모두 없어야 한다. 학과명 속 '공학'은 허용한다.
  assert.ok(!/대한민국|prospective|"team"|"age"|nationality|teamSize|businessStatus|entryType|majorFamily/.test(serialized));
  assert.ok(!serialized.includes("23"), "나이(23)가 이력서에 들어갔다");
});

test("대표 프로필의 자리표시 소속('일반 전공' 등)은 학과로 내보내지 않는다", () => {
  assert.equal(resumeMajor({ affiliation: "일반 전공" }), "");
  const resume = buildJsonResume({ status: "재학생", affiliation: "일반 전공", region: "서울" }, { now: NOW });
  assert.equal(resume.education, undefined);
  assert.equal(resume.basics.label, "재학생");

  const worker = buildJsonResume({ status: "직장인", affiliation: "직장인" }, { now: NOW });
  assert.equal(worker.basics.label, "직장인");
  assert.equal(worker.education, undefined);
});

test("학교 없이 학과만 있어도, 대학원생은 studyType을 대학원으로 표시한다", () => {
  const major = buildJsonResume({ status: "재학생", affiliation: "컴퓨터과학" }, { now: NOW });
  assert.deepEqual(major.education, [{ area: "컴퓨터과학" }]);

  const grad = buildJsonResume({ status: "대학원생", school: "연세대학교", affiliation: "컴퓨터과학" }, { now: NOW });
  assert.deepEqual(grad.education, [{ institution: "연세대학교", area: "컴퓨터과학", studyType: "대학원" }]);
});

test("입력이 없으면 값을 지어내지 않고 키를 생략하며 부족한 항목을 알려 준다", () => {
  const resume = buildJsonResume(EMPTY_PROFILE, { now: NOW });
  assert.deepEqual(resume.basics, {});
  for (const key of ["education", "skills", "interests"]) assert.ok(!(key in resume), key);
  assert.deepEqual(resumeGaps(resume), ["이름", "이메일", "학교·전공", "역량"]);

  const filled = buildJsonResume(fullProfile, { name: "홍길동", email: "a@b.kr", now: NOW });
  assert.deepEqual(resumeGaps(filled), []);
});

test("결과는 JSON으로 직렬화해도 같고 undefined 값이 없다", () => {
  const resume = buildJsonResume(fullProfile, { name: "홍길동", now: NOW });
  assert.deepEqual(JSON.parse(JSON.stringify(resume)), resume);
});

test("입력 프로필과 기본 프로필을 바꾸지 않는다", () => {
  const frozen = Object.freeze({ ...fullProfile, skills: Object.freeze([...fullProfile.skills]), interests: Object.freeze([...fullProfile.interests]) });
  assert.doesNotThrow(() => buildJsonResume(frozen, { now: NOW }));
  assert.doesNotThrow(() => buildJsonResume(EMPTY_PROFILE, { now: NOW }));
});

test("역량 묶음은 옵션으로 바꿀 수 있다", () => {
  const resume = buildJsonResume({ skills: ["A", "B"] }, { now: NOW, skillGroups: [{ name: "그룹", skills: ["A"] }] });
  assert.deepEqual(resume.skills, [{ name: "그룹", keywords: ["A"] }, { name: "기타", keywords: ["B"] }]);
});

test("파일 이름에서 경로·특수문자를 없애고 한글은 유지한다", () => {
  assert.equal(resumeFileName({ name: "홍길동" }), "contestfit-resume-홍길동.json");
  assert.equal(resumeFileName({ name: "Kim Min-su" }), "contestfit-resume-Kim-Min-su.json");
  assert.equal(resumeFileName({ name: "../../etc/passwd" }), "contestfit-resume-etc-passwd.json");
  assert.equal(resumeFileName({ name: "  " }), "contestfit-resume-draft.json");
  assert.equal(resumeFileName(), "contestfit-resume-draft.json");
});
