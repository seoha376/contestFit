// 프로필 → JSON Resume 변환. DOM·브라우저 API에 의존하지 않는 순수 모듈이다.
//
// ContestFit 프로필에 있는 정보 중 이력서에 쓰는 것(학교·전공·신분·역량·관심 분야·거주 지역)만 옮긴다.
// 나이·국적·사업자·참가 형태는 공고 자격 판정용이라 이력서로 내보내지 않는다.
// 없는 값은 추측해서 채우지 않고 키를 생략한다. 이름·이메일·한 줄 소개는 사용자가 직접 넘긴 값만 쓴다.
import { APP_CONFIG } from "./config.mjs";

export const JSON_RESUME_SCHEMA = "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json";
export const JSON_RESUME_VERSION = "v1.0.0";

// 판정 엔진용 대표 프로필이 쓰는 값이라 실제 학과·소속으로 취급하지 않는다.
const PLACEHOLDER_AFFILIATIONS = new Set(["일반 전공", "직장인", "사업자"]);
const OTHER_GROUP = "기타";
const INTEREST_GROUP = "관심 분야";

const text = (value) => String(value ?? "").trim();
const unique = (values) => [...new Set((values || []).map(text).filter(Boolean))];

function compact(object) {
  return Object.fromEntries(Object.entries(object).filter(([, value]) => value !== undefined && value !== ""));
}

/** 프로필의 전공·소속 중 실제 학과로 볼 수 있는 값. 대표 프로필의 자리표시 값은 빈 문자열이 된다. */
export function resumeMajor(profile = {}) {
  const value = text(profile.affiliation);
  return PLACEHOLDER_AFFILIATIONS.has(value) ? "" : value;
}

function groupKeywords(chosen, groups) {
  const picked = unique(chosen);
  const known = new Set(groups.flatMap((group) => group.skills));
  const result = groups
    .map((group) => ({ name: group.name, keywords: group.skills.filter((skill) => picked.includes(skill)) }))
    .filter((group) => group.keywords.length);
  const extra = picked.filter((value) => !known.has(value));
  if (extra.length) result.push({ name: OTHER_GROUP, keywords: extra });
  return result;
}

/**
 * ContestFit 프로필을 JSON Resume(v1.0.0) 문서로 바꾼다.
 * options: { name, email, summary, now, skillGroups } — 이름·이메일·한 줄 소개는 저장하지 않고 이 호출에서만 쓴다.
 */
export function buildJsonResume(profile = {}, options = {}) {
  const skillGroups = options.skillGroups || APP_CONFIG.skillGroups;
  const now = options.now instanceof Date ? options.now : new Date();
  const school = text(profile.school);
  const major = resumeMajor(profile);
  const status = text(profile.status);
  const region = text(profile.region);

  const basics = compact({
    name: text(options.name),
    label: [major, status].filter(Boolean).join(" "),
    email: text(options.email),
    summary: text(options.summary),
    location: region ? { countryCode: "KR", region } : undefined,
  });

  const education = school || major
    ? [compact({ institution: school, area: major, studyType: status === "대학원생" ? "대학원" : undefined })]
    : [];
  const skills = groupKeywords(profile.skills, skillGroups);
  const interests = unique(profile.interests);

  return compact({
    $schema: JSON_RESUME_SCHEMA,
    basics,
    education: education.length ? education : undefined,
    skills: skills.length ? skills : undefined,
    interests: interests.length ? [{ name: INTEREST_GROUP, keywords: interests }] : undefined,
    meta: { version: JSON_RESUME_VERSION, lastModified: now.toISOString(), generator: "ContestFit" },
  });
}

/** 이력서로 쓰려면 아직 채워야 하는 항목 이름. */
export function resumeGaps(resume) {
  const gaps = [];
  if (!resume.basics?.name) gaps.push("이름");
  if (!resume.basics?.email) gaps.push("이메일");
  if (!resume.education?.length) gaps.push("학교·전공");
  if (!resume.skills?.length) gaps.push("역량");
  return gaps;
}

/** 다운로드 파일 이름. 이름에서 경로·특수문자를 제거하고 한글은 유지한다. */
export function resumeFileName(options = {}) {
  const slug = text(options.name).replace(/[^\p{L}\p{N}_-]+/gu, "-").replace(/^-+|-+$/g, "");
  return `contestfit-resume-${slug || "draft"}.json`;
}
