import { judgeContest } from "./decision-engine.mjs";
import { evaluateFit, titleTopics } from "./fit-engine.mjs";
import { APP_CONFIG, EMPTY_PROFILE } from "./config.mjs";

const labels = {
  eligible: "지원 가능",
  needs_review: "확인 필요",
  ineligible: "지원 불가",
};

const fieldLabels = {
  age: "연령",
  status: "신분",
  major_scope: "전공/소속",
  region: "지역",
  schoolRegion: "학교 소재지",
  nationality: "국적",
  business_reg: "사업자",
  entry_type: "참가 형태",
  team_size: "팀 인원",
};

const state = {
  contests: [],
  dataMeta: null,
  profile: loadProfile(),
  activeFilter: "all",
  query: "",
  dataFilter: "all",
  categoryFilter: "all",
  deadlineFilter: "all",
  selectedSections: {},
  sort: "relevance",
};

const form = document.querySelector("#profile-form");
const tabs = document.querySelector("#result-tabs");
const list = document.querySelector("#contest-list");
const summary = document.querySelector("#summary-counts");
const loading = document.querySelector("#loading-state");
const importForm = document.querySelector("#import-form");
const importMessage = document.querySelector("#import-message");
const fallbackBanner = document.querySelector("#fallback-banner");
const downloadPreview = document.querySelector("#download-preview");
const feedbackForm = document.querySelector("#feedback-form");
const knownSkills = new Set(APP_CONFIG.skillGroups.flatMap((group) => group.skills));
const knownInterests = new Set(APP_CONFIG.interestOptions);
let lastPreview = null;
let departmentTimer = null;
let schoolTimer = null;

function commaValues(value) {
  return [...new Set(String(value || "").split(/[,，\n]/).map((item) => item.trim()).filter(Boolean))].slice(0, 12);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function loadProfile() {
  try {
    const stored = JSON.parse(localStorage.getItem(APP_CONFIG.storageKey) || "null");
    return stored ? { ...EMPTY_PROFILE, ...stored } : { ...EMPTY_PROFILE };
  } catch {
    return { ...EMPTY_PROFILE };
  }
}

function saveProfile() {
  localStorage.setItem(APP_CONFIG.storageKey, JSON.stringify(state.profile));
}

function optionList(values, selected) {
  return values.map((item) => {
    const value = typeof item === "string" ? item : item.value;
    const label = typeof item === "string" ? item : item.label;
    return `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
}

function choiceButtons(values, selected, kind) {
  return values.map((value) => `<button type="button" class="choice-button ${selected.includes(value) ? "selected" : ""}" data-${kind}="${escapeHtml(value)}" aria-pressed="${selected.includes(value)}">${escapeHtml(value)}</button>`).join("");
}

function renderForm() {
  form.innerHTML = `
    <div class="profile-heading">
      <div><span class="eyebrow">MY PROFILE</span><h2>내 조건</h2></div>
      <button type="button" class="text-button" id="reset-profile">초기화</button>
    </div>
    <p class="privacy-note"><span aria-hidden="true">●</span> 입력값은 이 브라우저에만 저장됩니다.</p>
    <label>1. 신분 / 재학 상태
      <select name="status"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.statusOptions, state.profile.status)}</select>
    </label>
    <label>2. 국적
      <select name="nationality"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.nationalityOptions, state.profile.nationality)}</select>
    </label>
    <label>3. 만 나이
      <input name="age" type="number" min="0" max="120" inputmode="numeric" placeholder="예: 24" value="${escapeHtml(state.profile.age)}">
    </label>
    <label>4. 전공 / 소속
      <input name="affiliation" type="text" placeholder="예: 컴퓨터공학과" value="${escapeHtml(state.profile.affiliation)}">
    </label>
    <div id="department-results" class="department-results" aria-live="polite"></div>
    <p id="department-note" class="department-note">학과는 직접 입력할 수 있습니다. 공식 전국 목록이 등록되면 검색 제안을 보여줍니다.</p>
    <label>학교 이름 <span>(학교별 제한 확인용)</span>
      <input name="school" type="search" placeholder="대학명 두 글자 이상 입력" value="${escapeHtml(state.profile.school)}" aria-controls="school-results" aria-autocomplete="list">
    </label>
    <div id="school-results" class="department-results" aria-live="polite"></div>
    <p id="school-note" class="department-note">학교명을 입력하면 공식 학과자료의 대학명을 제안합니다. 직접 입력도 가능합니다.</p>
    <div class="choice-field" role="group" aria-label="내 역량">
      <strong>내 역량 <span>(여러 개 선택)</span></strong>
      ${APP_CONFIG.skillGroups.map((group, index) => {
        const count = group.skills.filter((skill) => (state.profile.skills || []).includes(skill)).length;
        return `<details class="choice-group" ${index === 0 ? "open" : ""}><summary>${escapeHtml(group.name)} <span class="selection-count">${count ? `${count}개 선택` : ""}</span></summary><div class="choice-buttons">${choiceButtons(group.skills, state.profile.skills || [], "skill")}</div></details>`;
      }).join("")}
    </div>
    <label>목록에 없는 역량 <span>(선택)</span>
      <input name="skillsCustom" type="text" placeholder="쉼표로 구분해 추가" value="${escapeHtml((state.profile.skills || []).filter((value) => !knownSkills.has(value)).join(", "))}">
    </label>
    <div class="choice-field" role="group" aria-label="관심 주제">
      <strong>관심 주제 <span>(여러 개 선택)</span></strong>
      <div class="choice-buttons">${choiceButtons(APP_CONFIG.interestOptions, state.profile.interests || [], "interest")}</div>
    </div>
    <label>목록에 없는 관심 주제 <span>(선택)</span>
      <input name="interestsCustom" type="text" placeholder="쉼표로 구분해 추가" value="${escapeHtml((state.profile.interests || []).filter((value) => !knownInterests.has(value)).join(", "))}">
    </label>
    <p class="department-note">역량·관심 주제는 탐색에만 사용하며 지원 자격을 바꾸지 않습니다.</p>
    <label>5. 거주 지역
      <select name="region"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.regionOptions, state.profile.region)}</select>
    </label>
    <label>학교 소재지
      <select name="schoolRegion"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.regionOptions, state.profile.schoolRegion)}</select>
    </label>
    <label>직장·사업장 소재지
      <select name="affiliationRegion"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.regionOptions, state.profile.affiliationRegion)}</select>
    </label>
    <fieldset>
      <legend>6. 사업자 / 창업 상태</legend>
      <select name="businessStatus"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.businessOptions, state.profile.businessStatus)}</select>
      <input name="businessYears" type="number" min="0" step="0.1" inputmode="decimal" placeholder="창업 연차" value="${escapeHtml(state.profile.businessYears)}" ${state.profile.businessStatus === "registered" ? "" : "disabled"}>
    </fieldset>
    <fieldset>
      <legend>7. 참가 형태</legend>
      <select name="entryType"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.entryOptions, state.profile.entryType)}</select>
      <input name="teamSize" type="number" min="1" inputmode="numeric" placeholder="팀 인원" value="${escapeHtml(state.profile.teamSize)}" ${state.profile.entryType === "team" ? "" : "disabled"}>
    </fieldset>
  `;
  form.querySelector("#reset-profile").addEventListener("click", () => {
    state.profile = { ...EMPTY_PROFILE };
    localStorage.removeItem(APP_CONFIG.storageKey);
    renderForm();
    renderResults();
  });
}

function syncConditionalInputs() {
  const businessYears = form.elements.businessYears;
  const teamSize = form.elements.teamSize;
  businessYears.disabled = form.elements.businessStatus.value !== "registered";
  teamSize.disabled = form.elements.entryType.value !== "team";
}

function profileFromForm() {
  const data = new FormData(form);
  return {
    ...state.profile,
    status: data.get("status") || "",
    nationality: data.get("nationality") || "",
    age: data.get("age") === "" ? "" : Number(data.get("age")),
    affiliation: data.get("affiliation")?.trim() || "",
    school: data.get("school")?.trim() || "",
    skills: [...new Set([...form.querySelectorAll('[data-skill][aria-pressed="true"]')].map((item) => item.dataset.skill).concat(commaValues(data.get("skillsCustom"))))],
    interests: [...new Set([...form.querySelectorAll('[data-interest][aria-pressed="true"]')].map((item) => item.dataset.interest).concat(commaValues(data.get("interestsCustom"))))],
    region: data.get("region") || "",
    schoolRegion: data.get("schoolRegion") || "",
    affiliationRegion: data.get("affiliationRegion") || "",
    businessStatus: data.get("businessStatus") || "",
    businessYears: data.get("businessYears") === "" ? "" : Number(data.get("businessYears")),
    entryType: data.get("entryType") || "",
    teamSize: data.get("teamSize") === "" ? "" : Number(data.get("teamSize")),
  };
}

function renderTabs(counts, total) {
  tabs.innerHTML = APP_CONFIG.filters.map((filter) => {
    const count = filter.id === "all" ? total : counts[filter.id];
    return `<button type="button" role="tab" aria-selected="${state.activeFilter === filter.id}" class="tab ${state.activeFilter === filter.id ? "active" : ""}" data-filter="${filter.id}">${filter.label}<span>${count}</span></button>`;
  }).join("");
}

function conditionChips(decision) {
  const specified = decision.sections.flatMap((section) => section.specifiedFields ?? []);
  const missing = decision.missingFields ?? decision.sections.flatMap((section) => section.missingFields ?? []);
  const chips = [...new Set(specified)].map((field) => `<span class="chip condition">${escapeHtml(fieldLabels[field] ?? field)} 조건</span>`);
  chips.push(...[...new Set(missing)].map((field) => `<span class="chip missing">명시 없음 · ${escapeHtml(fieldLabels[field] ?? field)}</span>`));
  chips.push(...(decision.otherConditions ?? []).map((item) => `<span class="chip notice">기타 조건 · ${escapeHtml(item)}</span>`));
  return chips.join("");
}

function updateDataSummary() {
  const total = state.contests.length;
  const samples = state.contests.filter((item) => item.is_sample).length;
  // 검수 완료 건수는 목록 안에서 실공고이면서 verified인 항목만 명시적으로 센다.
  const verified = state.contests.filter((item) => !item.is_sample && item.validation_status === "verified").length;
  const unverified = state.contests.filter((item) => item.validation_status !== "verified").length;
  const summaryElement = document.querySelector("#data-summary");
  if (summaryElement) {
    summaryElement.textContent = total > 0 && samples === total
      ? `샘플 ${samples}건 · 실제 0건 — 전부 검증 전 샘플입니다`
      : `샘플 ${samples}건 · 실제 ${total - samples}건 · 검수 완료 ${verified}건${unverified ? ` · 검증 전 ${unverified}건 포함` : ""}`;
  }
  const totalElement = document.querySelector("#contest-total");
  if (totalElement) totalElement.textContent = total;
}

function deadlineLabel(contest, localToday) {
  if (!contest.deadline) return "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(contest.deadline)) return `접수 마감 ${contest.deadline}`;
  const due = new Date(`${contest.deadline}T00:00:00`);
  const today = new Date(`${localToday}T00:00:00`);
  if (Number.isNaN(due.getTime()) || Number.isNaN(today.getTime())) return `접수 마감 ${contest.deadline}`;
  const days = Math.round((due - today) / 86400000);
  if (days < 0) return `접수 마감 ${contest.deadline} · 마감됨`;
  if (days === 0) return `접수 마감 ${contest.deadline} · D-Day`;
  return `접수 마감 ${contest.deadline} · D-${days}`;
}

function resetFilters() {
  state.activeFilter = "all";
  state.query = "";
  state.dataFilter = "all";
  state.categoryFilter = "all";
  state.deadlineFilter = "all";
  state.sort = "relevance";
  document.querySelector("#contest-search").value = "";
  document.querySelector("#data-filter").value = "all";
  document.querySelector("#category-filter").value = "all";
  document.querySelector("#deadline-filter").value = "all";
  document.querySelector("#sort-filter").value = "relevance";
  renderResults();
}

function evidenceRows(contest) {
  const rows = [];
  for (const section of contest.sections) {
    for (const [field, evidence] of Object.entries(section.evidence ?? {})) {
      if (!evidence) continue;
      const excerpts = Array.isArray(evidence) ? evidence : [evidence];
      rows.push(`<div class="evidence-row"><dt>${escapeHtml(fieldLabels[field] ?? (field === "other_conditions" ? "기타 조건" : field))}</dt><dd>${excerpts.map((item) => `<q>${escapeHtml(item)}</q>`).join("<br>")}</dd></div>`);
    }
  }
  return rows.length ? rows.join("") : "<p class=\"muted\">저장된 근거 발췌가 없습니다.</p>";
}

function cardHtml({ contest, decision, fit, localToday }) {
  const firstReason = decision.reasons?.[0]?.message ?? "판정 사유를 확인해 주세요.";
  const collected = contest.collected_at ? new Date(contest.collected_at).toLocaleDateString("ko-KR") : "미기재";
  return `
    <article class="contest-card status-${decision.result}">
      <div class="card-topline">
        <div class="badge-groups">
          <div class="badge-group">
            <span class="badge-group-label">지원 자격</span>
            <div class="badges">
              <span class="result-badge">${labels[decision.result]}</span>
              <span class="data-badge">${contest.validation_status === "verified" ? "검수 완료" : "검증 전 데이터"}</span>
              <span class="sample-badge">${contest.is_sample ? "샘플 데이터" : "실제 공고"}</span>
              ${contest.deadline && contest.deadline < localToday ? '<span class="data-badge">접수 마감</span>' : ""}
            </div>
          </div>
          <div class="badge-group">
            <span class="badge-group-label">주제 관련성 · 자격과 별개</span>
            <div class="badges">
              <span class="fit-badge ${fit.level === "related" ? "" : fit.level === "unknown" ? "unknown" : "no-signal"}">${fit.level === "related" ? "내 주제와 연결" : fit.level === "unknown" ? "관련성 정보 부족" : "일치 신호 없음"}</span>
            </div>
          </div>
        </div>
        <span class="organizer">${escapeHtml(contest.organizer || "주최 미기재")}</span>
      </div>
      <h3>${escapeHtml(contest.title)}</h3>
      ${(contest.category || titleTopics(contest.title).length) ? `<p class="deadline-line">주제: ${escapeHtml(contest.category || titleTopics(contest.title).join(" · "))}${contest.category ? "" : " · 제목 키워드"}</p>` : ""}
      ${contest.deadline ? `<p class="deadline-line"><span class="date-label">${escapeHtml(deadlineLabel(contest, localToday))}</span></p>` : ""}
      <p class="reason-line">${escapeHtml(firstReason)}</p>
      <p class="fit-note"><span class="fit-note-label">주제 관련성 (자격 판정과 별개):</span> ${escapeHtml(fit.reasons.join(" "))}</p>
      ${contest.sections.length > 1 ? `<div class="section-picker"><label for="section-${escapeHtml(contest.id)}">지원 부문</label><select class="section-select" id="section-${escapeHtml(contest.id)}" data-contest-id="${escapeHtml(contest.id)}"><option value="">부문 선택 전</option>${contest.sections.map((section) => `<option value="${escapeHtml(section.id)}" ${state.selectedSections[contest.id] === section.id ? "selected" : ""}>${escapeHtml(section.name || section.id)}</option>`).join("")}</select></div>` : ""}
      <div class="chips">${conditionChips(decision)}</div>
      <details>
        <summary>자격 분석 리포트 · 근거 보기 <span aria-hidden="true">＋</span></summary>
        <div class="detail-body">
          <div class="report-head"><span class="report-title">자격 분석 리포트</span><span class="report-sub">원문 근거 발췌</span></div>
          <dl class="evidence-list">${evidenceRows(contest)}</dl>
          ${contest.skill_signals?.length ? `<p class="muted">공고에 명시된 역량: ${contest.skill_signals.map((item) => `${escapeHtml(item.name)} — ${escapeHtml(item.evidence)}`).join(" · ")}</p>` : ""}
          <div class="detail-meta">
            <span>수집일 ${escapeHtml(collected)}</span>
            ${contest.source_url ? `<a href="${escapeHtml(contest.source_url)}" target="_blank" rel="noopener noreferrer">원문 공고 열기 ↗</a>` : ""}
          </div>
          <p class="final-notice">판정 결과와 별개로 최종 지원 전 주최 공고를 반드시 확인하세요.</p>
        </div>
      </details>
    </article>
  `;
}

function renderResults() {
  if (!state.contests.length) return;
  const settings = { confidenceThreshold: APP_CONFIG.confidenceThreshold };
  const query = state.query.toLocaleLowerCase("ko-KR");
  const today = new Date();
  const localToday = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const matching = state.contests.filter((contest) => {
    const searchText = `${contest.title || ""} ${contest.organizer || ""} ${(contest.topic_tags || []).join(" ")} ${(contest.skill_signals || []).map((item) => item.name).join(" ")}`;
    const matchText = searchText.toLocaleLowerCase("ko-KR").includes(query);
    const matchData = state.dataFilter === "all" || (state.dataFilter === "sample" ? contest.is_sample : !contest.is_sample);
    const matchCategory = state.categoryFilter === "all" || contest.category === state.categoryFilter || titleTopics(contest.title).includes(state.categoryFilter);
    const matchDeadline = state.deadlineFilter === "all"
      || (state.deadlineFilter === "unknown" && !contest.deadline)
      || (state.deadlineFilter === "open" && contest.deadline && contest.deadline >= localToday);
    return matchText && matchData && matchCategory && matchDeadline;
  });
  const judged = matching.map((contest) => ({
    contest,
    decision: judgeContest(contest, { ...state.profile, selectedSectionId: state.selectedSections[contest.id] || "" }, settings),
    fit: evaluateFit(contest, state.profile),
  }));
  if (state.sort === "relevance") judged.sort((a, b) => ({ related: 0, unknown: 1, no_signal: 2 }[a.fit.level] - { related: 0, unknown: 1, no_signal: 2 }[b.fit.level]));
  if (state.sort === "deadline") judged.sort((a, b) => (a.contest.deadline || "9999-12-31").localeCompare(b.contest.deadline || "9999-12-31"));
  const counts = { eligible: 0, needs_review: 0, ineligible: 0 };
  judged.forEach(({ decision }) => { counts[decision.result] += 1; });
  renderTabs(counts, judged.length);
  summary.innerHTML = `<span class="summary-lead">현재 프로필 기준</span><span class="stat"><strong class="stat-num stat-eligible">${counts.eligible}</strong>지원 가능</span><span class="stat"><strong class="stat-num stat-needs_review">${counts.needs_review}</strong>확인 필요</span><span class="stat"><strong class="stat-num stat-ineligible">${counts.ineligible}</strong>지원 불가</span>`;
  const visible = state.activeFilter === "all" ? judged : judged.filter(({ decision }) => decision.result === state.activeFilter);
  if (visible.length) {
    list.innerHTML = visible.map((item) => cardHtml({ ...item, localToday })).join("");
  } else if (!judged.length) {
    list.innerHTML = `<div class="empty-state"><strong>조건에 맞는 공고가 없습니다.</strong><span>검색어와 필터를 확인해 보세요.</span><button type="button" class="empty-reset" id="reset-filters">필터 초기화</button></div>`;
  } else {
    list.innerHTML = `<div class="empty-state"><strong>해당 판정의 공고가 없습니다.</strong><span>프로필이나 필터를 바꿔 보세요.</span><button type="button" class="empty-reset" id="reset-filters">필터 초기화</button></div>`;
  }
}

form.addEventListener("input", () => {
  state.profile = profileFromForm();
  saveProfile();
  syncConditionalInputs();
  renderResults();
});

form.addEventListener("input", (event) => {
  if (event.target.name !== "affiliation") return;
  clearTimeout(departmentTimer);
  const query = event.target.value.trim();
  const results = form.querySelector("#department-results");
  results.innerHTML = "";
  if (query.length < 2) return;
  departmentTimer = setTimeout(async () => {
    try {
      const response = await fetch(`/api/departments?q=${encodeURIComponent(query)}`);
      if (!response.ok) return;
      const data = await response.json();
      if (form.elements.affiliation.value.trim() !== query) return;
      form.querySelector("#department-note").textContent = data.count
        ? `공식 학과자료 ${data.reference_year || "연도 미상"}년 ${data.count.toLocaleString("ko-KR")}건에서 검색 · 재학 여부는 공고 원문 확인`
        : data.coverage_note;
      results.innerHTML = data.departments.map((item) => `<button type="button" data-major="${escapeHtml(item.major)}" data-school="${escapeHtml(item.school)}" data-region="${escapeHtml(item.region)}">${escapeHtml(item.school)} · ${escapeHtml(item.major)}</button>`).join("");
    } catch {
      form.querySelector("#department-note").textContent = "학과 검색을 사용할 수 없습니다. 학과명은 직접 입력할 수 있습니다.";
    }
  }, 250);
});

form.addEventListener("input", (event) => {
  if (event.target.name !== "school") return;
  clearTimeout(schoolTimer);
  const query = event.target.value.trim();
  const results = form.querySelector("#school-results");
  results.innerHTML = "";
  if (query.length < 2) return;
  schoolTimer = setTimeout(async () => {
    try {
      const response = await fetch(`/api/schools?q=${encodeURIComponent(query)}`);
      if (!response.ok) throw new Error("search failed");
      const data = await response.json();
      if (form.elements.school.value.trim() !== query) return;
      form.querySelector("#school-note").textContent = data.count
        ? `공식 학과자료 ${data.reference_year || "연도 미상"}년 · 대학 ${data.count.toLocaleString("ko-KR")}곳 중 검색${data.schools.length ? "" : " · 일치하는 대학 없음"}`
        : "공식 대학 목록이 아직 동기화되지 않았습니다. 학교명을 직접 입력할 수 있습니다.";
      results.innerHTML = data.schools.map((item) => `<button type="button" data-school-choice="${escapeHtml(item.name)}" data-region="${escapeHtml(item.region)}">${escapeHtml(item.name)}${item.region ? ` · ${escapeHtml(item.region)}` : ""}</button>`).join("");
    } catch {
      form.querySelector("#school-note").textContent = "대학 검색을 사용할 수 없습니다. 학교명을 직접 입력할 수 있습니다.";
    }
  }, 180);
});

form.addEventListener("click", (event) => {
  const choiceButton = event.target.closest("[data-skill], [data-interest]");
  if (choiceButton) {
    const selected = choiceButton.getAttribute("aria-pressed") !== "true";
    choiceButton.setAttribute("aria-pressed", String(selected));
    choiceButton.classList.toggle("selected", selected);
    const group = choiceButton.closest(".choice-group");
    if (group) {
      const count = group.querySelectorAll('[data-skill][aria-pressed="true"]').length;
      group.querySelector(".selection-count").textContent = count ? `${count}개 선택` : "";
    }
    state.profile = profileFromForm();
    saveProfile();
    renderResults();
    return;
  }
  const school = event.target.closest("[data-school-choice]");
  if (school) {
    form.elements.school.value = school.dataset.schoolChoice;
    const region = APP_CONFIG.regionOptions.find((item) => school.dataset.region.startsWith(item));
    if (region) form.elements.schoolRegion.value = region;
    form.querySelector("#school-results").innerHTML = "";
    state.profile = profileFromForm();
    saveProfile();
    renderResults();
    return;
  }
  const choice = event.target.closest("[data-major]");
  if (!choice) return;
  form.elements.affiliation.value = choice.dataset.major;
  form.elements.school.value = choice.dataset.school;
  const region = APP_CONFIG.regionOptions.find((item) => choice.dataset.region.startsWith(item));
  if (region) form.elements.schoolRegion.value = region;
  form.querySelector("#department-results").innerHTML = "";
  state.profile = profileFromForm();
  saveProfile();
  renderResults();
});

tabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.activeFilter = button.dataset.filter;
  renderResults();
});

list.addEventListener("click", (event) => {
  if (!event.target.closest("#reset-filters")) return;
  resetFilters();
});

list.addEventListener("change", (event) => {
  const picker = event.target.closest("[data-contest-id]");
  if (!picker) return;
  state.selectedSections[picker.dataset.contestId] = picker.value;
  renderResults();
});

document.querySelector("#contest-search").addEventListener("input", (event) => {
  state.query = event.target.value.trim();
  renderResults();
});

document.querySelector("#data-filter").addEventListener("change", (event) => {
  state.dataFilter = event.target.value;
  renderResults();
});

document.querySelector("#category-filter").addEventListener("change", (event) => {
  state.categoryFilter = event.target.value;
  renderResults();
});

document.querySelector("#deadline-filter").addEventListener("change", (event) => {
  state.deadlineFilter = event.target.value;
  renderResults();
});

document.querySelector("#sort-filter").addEventListener("change", (event) => {
  state.sort = event.target.value;
  renderResults();
});

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = importForm.querySelector("button");
  button.disabled = true;
  downloadPreview.hidden = true;
  importMessage.textContent = "공고 조건을 읽고 있습니다…";
  try {
    const data = new FormData(importForm);
    const response = await fetch("/api/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_url: data.get("source_url"), text: data.get("text") }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "공고를 처리할 수 없습니다.");
    state.contests.unshift(result.contest);
    lastPreview = result.contest;
    downloadPreview.hidden = false;
    state.query = "";
    state.dataFilter = "all";
    state.categoryFilter = "all";
    state.deadlineFilter = "all";
    state.activeFilter = "all";
    document.querySelector("#contest-search").value = "";
    document.querySelector("#data-filter").value = "all";
    document.querySelector("#category-filter").value = "all";
    document.querySelector("#deadline-filter").value = "all";
    renderResults();
    updateDataSummary();
    importMessage.textContent = "검수 전 공고를 목록 맨 위에 추가했습니다. 새로고침하면 미리보기는 사라집니다.";
  } catch (error) {
    importMessage.textContent = error.message || "서버 연결을 확인해 주세요.";
  } finally {
    button.disabled = false;
  }
});

downloadPreview.addEventListener("click", () => {
  if (!lastPreview) return;
  const blob = new Blob([JSON.stringify(lastPreview, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${lastPreview.id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
});

feedbackForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#feedback-message");
  const data = new FormData(feedbackForm);
  try {
    const response = await fetch("/api/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_completed: data.get("task_completed") === "yes",
        reason_clear: data.get("reason_clear") === "yes",
        ease: Number(data.get("ease")),
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "의견을 저장할 수 없습니다.");
    feedbackForm.reset();
    message.textContent = "의견을 저장했습니다. 감사합니다.";
  } catch (error) {
    message.textContent = error.message || "서버 연결을 확인해 주세요.";
  }
});

function applyContestData() {
  const categories = [...new Set(state.contests.flatMap((item) => [item.category, ...titleTopics(item.title)].filter(Boolean)))].sort();
  document.querySelector("#category-filter").innerHTML = `<option value="all">전체 주제</option>${categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("")}`;
  updateDataSummary();
  loading.hidden = true;
  renderResults();
}

async function start() {
  renderForm();
  try {
    const response = await fetch("/api/contests");
    if (!response.ok) throw new Error(`seed load failed: ${response.status}`);
    const seed = await response.json();
    state.contests = seed.contests;
    state.dataMeta = { schemaVersion: seed.schema_version ?? null, validationStatus: seed.validation_status ?? null };
    applyContestData();
  } catch (error) {
    console.error(error);
    try {
      const fallbackResponse = await fetch("./data/seed.json");
      if (!fallbackResponse.ok) throw new Error(`seed fallback failed: ${fallbackResponse.status}`);
      const seed = await fallbackResponse.json();
      state.contests = seed.contests;
      state.dataMeta = { schemaVersion: seed.schema_version ?? null, validationStatus: seed.validation_status ?? null };
      if (fallbackBanner) fallbackBanner.hidden = false;
      applyContestData();
    } catch (fallbackError) {
      console.error(fallbackError);
      loading.innerHTML = `<strong>공고 데이터를 불러오지 못했습니다.</strong><span>Python 서비스로 실행했는지 확인해 주세요.</span>`;
    }
  }
}

start();
