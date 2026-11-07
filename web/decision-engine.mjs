export const DEFAULT_SETTINGS = Object.freeze({ confidenceThreshold: 0.7 });

const CONDITION_FIELDS = [
  "age", "status", "major_scope", "region", "nationality",
  "business_reg", "entry_type", "team_size",
];

const FIELD_LABELS = {
  age: "연령",
  status: "신분/재학 상태",
  major_scope: "전공/소속",
  region: "거주 지역",
  nationality: "국적",
  business_reg: "사업자·창업 상태",
  entry_type: "참가 형태",
  team_size: "팀 인원",
};

function evidenceText(section, field) {
  const evidence = section.evidence?.[field];
  return Array.isArray(evidence) ? evidence.join(" ") : String(evidence ?? "");
}

function hasBodyEvidence(section, field) {
  const source = section.evidence_source?.[field];
  return Boolean(evidenceText(section, field)) && source !== "chip";
}

function reasonEvidenceIsConsistent(reasonItem) {
  const text = Array.isArray(reasonItem.evidence) ? reasonItem.evidence.join(" ") : String(reasonItem.evidence ?? "");
  if (!text) return false;
  if (reasonItem.field === "region") {
    return !/(?:전국|누구나)/.test(text)
      && /서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주/.test(text)
      && /거주|주민등록|소재/.test(text);
  }
  if (reasonItem.field === "status") {
    return /재학생|휴학생|대학(?:\(원\)|원)?생|직장인|일반인|수료생|졸업생|예비\s*창업자|초등학생|중학생|고등학생/.test(text);
  }
  return true;
}

export function validateDecisionEvidence(decision) {
  if (decision.result !== "ineligible") return [];
  return (decision.reasons ?? []).filter((item) => item.kind === "mismatch" && !reasonEvidenceIsConsistent(item));
}

function reason(field, kind, message, evidence = null) {
  return { field, kind, message, evidence };
}

function isSpecified(section, field) {
  if (field === "age") return section.age?.min != null || section.age?.max != null;
  if (field === "status") return section.status?.allowed != null || section.status?.excluded != null;
  if (field === "business_reg") return section.business_reg?.policy != null || section.business_reg?.years != null;
  if (field === "team_size") return section.team_size?.min != null || section.team_size?.max != null;
  if (field === "region" && section[field] === "제한없음") return false;
  return section[field] != null && section[field] !== "";
}

function hasUnmappedEvidence(section, field) {
  return !isSpecified(section, field) && Boolean(evidenceText(section, field));
}

function normalizedStatus(status) {
  const aliases = {
    대학생: ["재학생", "휴학생", "대학생"],
    학생: ["재학생", "휴학생", "대학생", "대학원생"],
    재학생: ["재학생"],
    휴학생: ["휴학생"],
    대학원생: ["대학원생"],
    수료생: ["수료생"],
    직장인: ["직장인"],
    일반인: ["일반인"],
    예비창업자: ["예비창업자"],
  };
  return aliases[status] ?? [status];
}

function statusMatches(profileStatus, conditionStatus) {
  return normalizedStatus(conditionStatus).includes(profileStatus);
}

function ambiguousEnumeration(section, field) {
  const text = evidenceText(section, field);
  return /(?:,|·|및).{0,30}등\s*(?:누구나|참가|지원|가능)/.test(text);
}

function isAdvisoryCondition(text) {
  return /1\s*인당.{0,20}(?:1개|작품|출품)|가족.{0,12}(?:참가|지원)\s*불가|시상식.{0,15}(?:필수|필참)|법정대리인.{0,30}(?:동의|서명)/.test(text);
}

function compareText(profileValue, requiredValue) {
  if (Array.isArray(requiredValue)) return requiredValue.some((value) => compareText(profileValue, value));
  const profile = String(profileValue).replace(/\s+/g, "").toLowerCase();
  const required = String(requiredValue).replace(/\s+/g, "").toLowerCase();
  return profile === required || profile.includes(required) || required.includes(profile);
}

function compareMajorScope(profileValue, requiredValue) {
  if (Array.isArray(requiredValue)) return requiredValue.some((value) => compareMajorScope(profileValue, value));
  return String(profileValue).replace(/\s+/g, "").toLowerCase()
    .includes(String(requiredValue).replace(/\s+/g, "").toLowerCase());
}

function evaluateAge(section, profile, output) {
  if (!isSpecified(section, "age")) return;
  if (section.age?.basis_date) {
    output.review.push(reason("age", "basis_date", "공고의 연령 기준일에 맞춘 만 나이를 확인해야 합니다.", section.evidence?.age));
    return;
  }
  if (profile.age == null || profile.age === "") {
    output.review.push(reason("age", "missing_profile", "프로필 연령을 입력해야 합니다.", section.evidence?.age));
    return;
  }
  const { min, max } = section.age;
  if (min != null && max != null && min > max) {
    output.review.push(reason("age", "contradiction", "연령 조건의 최소·최대 값이 모순됩니다.", section.evidence?.age));
  } else if ((min != null && Number(profile.age) < min) || (max != null && Number(profile.age) > max)) {
    output.fail.push(reason("age", "mismatch", "연령 조건을 충족하지 않습니다.", section.evidence?.age));
  }
}

function evaluateStatus(section, profile, output) {
  if (!isSpecified(section, "status")) return;
  const allowed = section.status?.allowed;
  const excluded = section.status?.excluded;
  if (ambiguousEnumeration(section, "status")) {
    output.review.push(reason("status", "ambiguous_enumeration", "나열된 신분이 요건인지 예시인지 확인이 필요합니다.", section.evidence?.status));
    return;
  }
  if (!profile.status) {
    output.review.push(reason("status", "missing_profile", "프로필 신분/재학 상태를 입력해야 합니다.", section.evidence?.status));
    return;
  }
  const allowedList = Array.isArray(allowed) ? allowed : allowed == null ? null : [allowed];
  const excludedList = Array.isArray(excluded) ? excluded : excluded == null ? [] : [excluded];
  if (allowedList?.some((value) => excludedList.some((excludedValue) => value === excludedValue))) {
    output.review.push(reason("status", "contradiction", "허용·제외 신분 조건이 모순됩니다.", section.evidence?.status));
  } else if (excludedList.some((value) => statusMatches(profile.status, value))) {
    output.fail.push(reason("status", "mismatch", "제외된 신분/재학 상태입니다.", section.evidence?.status));
  } else if (allowedList && allowedList.length > 0 && !allowedList.some((value) => statusMatches(profile.status, value))) {
    output.fail.push(reason("status", "mismatch", "허용된 신분/재학 상태에 해당하지 않습니다.", section.evidence?.status));
  }
}

function evaluateSimple(section, profile, field, profileKey, output) {
  if (!isSpecified(section, field)) return;
  const profileValue = field === "major_scope" && profile.school
    ? `${profile.school} ${profile[profileKey] || ""}`.trim()
    : profile[profileKey];
  if (field === "major_scope") {
    const scopes = Array.isArray(section[field]) ? section[field] : [section[field]];
    const needsSchool = scopes.some((value) => /(?:대학교|대학|학교)/.test(String(value)));
    const needsMajor = scopes.some((value) => /(?:학과|학부|전공)/.test(String(value)));
    if ((needsSchool && !profile.school || needsMajor && !profile.affiliation)
      && !compareMajorScope(profileValue || "", section[field])) {
      output.review.push(reason(field, "missing_profile", "공고의 학교·학과 조건과 비교할 프로필 정보가 부족합니다.", section.evidence?.[field]));
      return;
    }
  }
  if (profileValue == null || profileValue === "") {
    output.review.push(reason(field, "missing_profile", `프로필 ${FIELD_LABELS[field]}을(를) 입력해야 합니다.`, section.evidence?.[field]));
  } else if (!(field === "major_scope" ? compareMajorScope(profileValue, section[field]) : compareText(profileValue, section[field]))) {
    output.fail.push(reason(field, "mismatch", `${FIELD_LABELS[field]} 조건을 충족하지 않습니다.`, section.evidence?.[field]));
  }
}

function evaluateRegion(section, profile, output) {
  if (!isSpecified(section, "region")) return;
  const condition = section.region;
  const basis = typeof condition === "object" ? condition.basis : "residence";
  const regions = typeof condition === "object" ? condition.regions : [condition];
  const profileKey = basis === "residence" ? "region" : basis === "school" ? "schoolRegion" : "affiliationRegion";
  const profileValue = profile[profileKey];
  if (!profileValue) {
    output.review.push(reason("region", "missing_profile", basis === "residence" ? "프로필 거주 지역을 입력해야 합니다." : "공고의 지역 기준과 비교할 학교·소속 소재지가 없습니다.", section.evidence?.region));
  } else if (!regions.some((value) => compareText(profileValue, value))) {
    output.fail.push(reason("region", "mismatch", basis === "residence" ? "거주 지역 조건을 충족하지 않습니다." : "학교·소속 소재지 조건을 충족하지 않습니다.", section.evidence?.region));
  }
}

function evaluateBusiness(section, profile, output) {
  if (!isSpecified(section, "business_reg")) return;
  if (!profile.businessStatus) {
    output.review.push(reason("business_reg", "missing_profile", "사업자·창업 상태를 입력해야 합니다.", section.evidence?.business_reg));
    return;
  }
  const { policy, years } = section.business_reg;
  const hasBusiness = profile.businessStatus === "registered";
  if (policy === "required" && !hasBusiness) {
    output.fail.push(reason("business_reg", "mismatch", "사업자 등록 필수 조건을 충족하지 않습니다.", section.evidence?.business_reg));
  } else if (policy === "forbidden" && hasBusiness) {
    output.fail.push(reason("business_reg", "mismatch", "사업자 보유자는 참가할 수 없습니다.", section.evidence?.business_reg));
  } else if (years != null && hasBusiness && profile.businessYears == null) {
    output.review.push(reason("business_reg", "missing_profile", "창업 연차를 입력해야 합니다.", section.evidence?.business_reg));
  } else if (years != null && hasBusiness && Number(profile.businessYears) >= years) {
    output.fail.push(reason("business_reg", "mismatch", `창업 ${years}년 미만 조건을 충족하지 않습니다.`, section.evidence?.business_reg));
  }
}

function evaluateEntry(section, profile, output) {
  if (isSpecified(section, "entry_type")) {
    if (!profile.entryType) {
      output.review.push(reason("entry_type", "missing_profile", "개인/팀 참가 형태를 입력해야 합니다.", section.evidence?.entry_type));
    } else if (section.entry_type !== "both" && section.entry_type !== profile.entryType) {
      output.fail.push(reason("entry_type", "mismatch", section.entry_type === "individual" ? "개인 참가만 가능합니다." : "팀 참가만 가능합니다.", section.evidence?.entry_type));
    }
  }
  if (!isSpecified(section, "team_size")) return;
  if (profile.entryType !== "team") return;
  if (profile.teamSize == null || profile.teamSize === "") {
    output.review.push(reason("team_size", "missing_profile", "팀 인원을 입력해야 합니다.", section.evidence?.team_size));
    return;
  }
  const { min, max } = section.team_size;
  if (min != null && max != null && min > max) {
    output.review.push(reason("team_size", "contradiction", "팀 인원 조건의 최소·최대 값이 모순됩니다.", section.evidence?.team_size));
  } else if ((min != null && Number(profile.teamSize) < min) || (max != null && Number(profile.teamSize) > max)) {
    output.fail.push(reason("team_size", "mismatch", "팀 인원 조건을 충족하지 않습니다.", section.evidence?.team_size));
  }
}

export function evaluateSection(section, profile, settings = DEFAULT_SETTINGS) {
  const output = { fail: [], review: [] };
  const threshold = settings.confidenceThreshold ?? DEFAULT_SETTINGS.confidenceThreshold;

  for (const field of CONDITION_FIELDS) {
    const confidence = section.confidence?.[field];
    if (isSpecified(section, field) && typeof confidence === "number" && confidence < threshold) {
      output.review.push(reason(field, "low_confidence", `${FIELD_LABELS[field]} 해석 신뢰도가 기준보다 낮습니다.`, section.evidence?.[field]));
    }
    if (hasUnmappedEvidence(section, field)) {
      output.review.push(reason(field, "unmapped_evidence", `${FIELD_LABELS[field]} 근거는 있으나 정규화된 조건이 없습니다.`, section.evidence?.[field]));
    }
  }

  const unmodeledConditions = (section.other_conditions ?? []).filter((item) => !isAdvisoryCondition(String(item)));
  if (unmodeledConditions.length) {
    output.review.push(reason("other_conditions", "unmodeled_condition", "정규화되지 않은 추가 자격 조건을 확인해야 합니다.", section.evidence?.other_conditions));
  }

  evaluateAge(section, profile, output);
  evaluateStatus(section, profile, output);
  evaluateSimple(section, profile, "major_scope", "affiliation", output);
  evaluateRegion(section, profile, output);
  evaluateSimple(section, profile, "nationality", "nationality", output);
  evaluateBusiness(section, profile, output);
  evaluateEntry(section, profile, output);

  const clearFailures = [];
  for (const failure of output.fail) {
    if (!hasBodyEvidence(section, failure.field) || !reasonEvidenceIsConsistent(failure)) {
      output.review.push(reason(failure.field, "unclear_evidence", `${FIELD_LABELS[failure.field]} 불충족 근거가 본문 조건과 명확히 일치하지 않습니다.`, failure.evidence));
    } else {
      clearFailures.push(failure);
    }
  }
  output.fail = clearFailures;

  const specified = CONDITION_FIELDS.filter((field) => isSpecified(section, field));
  const missingFields = CONDITION_FIELDS.filter((field) => !isSpecified(section, field) && !evidenceText(section, field));
  const result = output.fail.length ? "ineligible" : output.review.length ? "needs_review" : "eligible";
  const reasons = result === "ineligible" ? output.fail : result === "needs_review" ? output.review : [reason("all", "matched", "명시된 조건을 모두 충족합니다.")];
  return {
    sectionId: section.id,
    sectionName: section.name,
    result,
    reasons,
    specifiedFields: specified,
    missingFields,
    otherConditions: section.other_conditions ?? [],
  };
}

export function judgeContest(contest, profile, settings = DEFAULT_SETTINGS) {
  const evaluations = contest.sections.map((section) => evaluateSection(section, profile, settings));
  if (contest.validation_status === "draft") {
    return {
      result: "needs_review",
      reasons: [reason("source", "unverified_import", "새 공고의 자동 추출 조건을 검수해야 합니다.")],
      sections: evaluations,
      possibleSections: [],
      missingFields: [...new Set(evaluations.flatMap((item) => item.missingFields))],
      otherConditions: [...new Set(evaluations.flatMap((item) => item.otherConditions))],
    };
  }
  const selected = profile.selectedSectionId
    ? evaluations.find((item) => item.sectionId === profile.selectedSectionId)
    : null;
  if (selected) return { ...selected, sections: evaluations, possibleSections: selected.result === "eligible" ? [selected.sectionId] : [] };

  const results = new Set(evaluations.map((item) => item.result));
  let result;
  let reasons;
  if (results.size === 1) {
    result = evaluations[0]?.result ?? "needs_review";
    reasons = evaluations.flatMap((item) => item.reasons).slice(0, 3);
  } else {
    result = "needs_review";
    reasons = [reason("section", "section_divergence", "부문별 판정이 달라 지원 부문 선택이 필요합니다.")];
  }
  return {
    result,
    reasons,
    sections: evaluations,
    possibleSections: evaluations.filter((item) => item.result === "eligible").map((item) => item.sectionId),
    missingFields: [...new Set(evaluations.flatMap((item) => item.missingFields))],
    otherConditions: [...new Set(evaluations.flatMap((item) => item.otherConditions))],
  };
}

export function judgeAll(contests, profile, settings = DEFAULT_SETTINGS) {
  return contests.map((contest) => ({ contest, decision: judgeContest(contest, profile, settings) }));
}
