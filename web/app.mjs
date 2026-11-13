import { judgeContest } from "./decision-engine.mjs";
import { evaluateFit, titleTopics } from "./fit-engine.mjs";
import { APP_CONFIG, EMPTY_PROFILE } from "./config.mjs";

const labels = { eligible: "지원 가능", needs_review: "확인 필요", ineligible: "지원 불가" };
const kindLabels = Object.fromEntries(APP_CONFIG.kindOptions.map((item) => [item.value, item.label]));
const fieldLabels = {
  age: "연령", status: "신분", major_scope: "전공/소속", region: "지역", schoolRegion: "학교 소재지",
  nationality: "국적", business_reg: "사업자", entry_type: "참가 형태", team_size: "팀 인원", other_conditions: "기타 조건",
};
const scheduleIcons = { apply: "접수", review: "심사", event: "행사", announcement: "발표", award: "시상" };

const state = {
  contests: [],
  sources: [],
  store: null,
  dataStatus: null,
  profile: loadProfile(),
  savedProfiles: loadJson(APP_CONFIG.profilesKey, []),
  checklist: loadJson(APP_CONFIG.checklistKey, {}),
  activeFilter: "all",
  query: "",
  kindFilter: "all",
  sourceFilter: "all",
  dataFilter: "all",
  categoryFilter: "all",
  deadlineFilter: "all",
  selectedSections: {},
  sort: "deadline",
  loaded: false,
  preview: null,
};

const $ = (selector) => document.querySelector(selector);
const form = $("#profile-form");
const tabs = $("#result-tabs");
const list = $("#contest-list");
const summary = $("#summary-counts");
const loading = $("#loading-state");
const knownSkills = new Set(APP_CONFIG.skillGroups.flatMap((group) => group.skills));
const knownInterests = new Set(APP_CONFIG.interestOptions);
let departmentTimer = null;
let schoolTimer = null;
let majorTimer = null;

// ---------- utilities ----------
function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
function loadJson(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || "null") ?? fallback; } catch { return fallback; }
}
function saveJson(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage may be unavailable */ }
}
function loadProfile() {
  const stored = loadJson(APP_CONFIG.storageKey, null);
  return stored ? { ...EMPTY_PROFILE, ...stored } : { ...EMPTY_PROFILE };
}
function saveProfile() { saveJson(APP_CONFIG.storageKey, state.profile); }
function commaValues(value) {
  return [...new Set(String(value || "").split(/[,，\n]/).map((item) => item.trim()).filter(Boolean))].slice(0, 12);
}
function localToday() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}
function daysUntil(dateText) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateText || "")) return null;
  return Math.round((new Date(`${dateText}T00:00:00`) - new Date(`${localToday()}T00:00:00`)) / 86400000);
}
function ddayText(dateText) {
  const days = daysUntil(dateText);
  if (days === null) return "";
  if (days < 0) return "마감됨";
  return days === 0 ? "D-Day" : `D-${days}`;
}
function formatDate(dateText) {
  if (!dateText) return "미기재";
  const date = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(date.getTime())) return dateText;
  return date.toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric", weekday: "short" });
}
function sourceOf(contest) {
  if (contest.source) return contest.source;
  if (contest.is_sample) return { id: "sample", name: "샘플 데이터", type: "sample" };
  return { id: "curated", name: "팀 검수 공고", type: "curated" };
}
function judge(contest, profile = state.profile) {
  return judgeContest(contest, { ...profile, selectedSectionId: state.selectedSections[contest.id] || "" },
    { confidenceThreshold: APP_CONFIG.confidenceThreshold });
}
async function getJson(url, options) {
  const response = await fetch(url, options);
  let data = {};
  try { data = await response.json(); } catch { /* keep empty */ }
  if (!response.ok) throw new Error(data.error || `요청 실패 (${response.status})`);
  return data;
}

// ---------- profile form ----------
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
  const activeName = state.savedProfiles.find((item) => item.id === state.profile.profileId)?.name;
  form.innerHTML = `
    <div class="profile-heading">
      <div><span class="eyebrow">MY PROFILE</span><h2>내 조건</h2>${activeName ? `<p class="active-profile" data-testid="active-profile">적용 중: ${escapeHtml(activeName)}</p>` : ""}</div>
      <button type="button" class="text-button" id="reset-profile">초기화</button>
    </div>
    <p class="privacy-note"><span aria-hidden="true">●</span> 입력값은 이 브라우저에만 저장됩니다.</p>
    <label>1. 신분 / 재학 상태
      <select name="status" data-testid="profile-status"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.statusOptions, state.profile.status)}</select>
    </label>
    <label>2. 국적
      <select name="nationality"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.nationalityOptions, state.profile.nationality)}</select>
    </label>
    <label>3. 만 나이
      <input name="age" type="number" min="0" max="120" inputmode="numeric" placeholder="예: 24" value="${escapeHtml(state.profile.age)}" data-testid="profile-age">
    </label>
    <label>학교 이름 <span>(학교별 제한 확인용)</span>
      <input name="school" type="search" placeholder="대학명 두 글자 이상 입력" value="${escapeHtml(state.profile.school)}" aria-controls="school-results" aria-autocomplete="list" data-testid="profile-school">
    </label>
    <div id="school-results" class="department-results" aria-live="polite" data-testid="school-results"></div>
    <p id="school-note" class="department-note">학교명을 입력하면 공식 학과자료의 대학명을 제안합니다.</p>
    <label>4. 전공 / 소속
      <input name="affiliation" type="text" placeholder="예: 산업공학과" value="${escapeHtml(state.profile.affiliation)}" data-testid="profile-major">
    </label>
    <div id="department-results" class="department-results" aria-live="polite" data-testid="department-results"></div>
    <p id="department-note" class="department-note">학과를 목록에서 고르면 계열(공학·인문 등)도 함께 저장됩니다.</p>
    <label>학과 계열 <span>(계열 조건 판정용)</span>
      <select name="majorFamily" data-testid="profile-family"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.majorFamilies, state.profile.majorFamily)}</select>
    </label>
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
      <select name="region" data-testid="profile-region"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.regionOptions, state.profile.region)}</select>
    </label>
    <label>학교 소재지
      <select name="schoolRegion"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.regionOptions, state.profile.schoolRegion)}</select>
    </label>
    <label>직장·사업장 소재지
      <select name="affiliationRegion"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.regionOptions, state.profile.affiliationRegion)}</select>
    </label>
    <fieldset>
      <legend>6. 사업자 / 창업 상태</legend>
      <select name="businessStatus" data-testid="profile-business"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.businessOptions, state.profile.businessStatus)}</select>
      <input name="businessYears" type="number" min="0" step="0.1" inputmode="decimal" placeholder="창업 연차" value="${escapeHtml(state.profile.businessYears)}" ${state.profile.businessStatus === "registered" ? "" : "disabled"}>
    </fieldset>
    <fieldset>
      <legend>7. 참가 형태</legend>
      <select name="entryType" data-testid="profile-entry"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.entryOptions, state.profile.entryType)}</select>
      <input name="teamSize" type="number" min="1" inputmode="numeric" placeholder="팀 인원" value="${escapeHtml(state.profile.teamSize)}" ${state.profile.entryType === "team" ? "" : "disabled"}>
    </fieldset>
  `;
  form.querySelector("#reset-profile").addEventListener("click", () => {
    state.profile = { ...EMPTY_PROFILE };
    try { localStorage.removeItem(APP_CONFIG.storageKey); } catch { /* ignore */ }
    renderForm();
    renderAll();
  });
}

function syncConditionalInputs() {
  form.elements.businessYears.disabled = form.elements.businessStatus.value !== "registered";
  form.elements.teamSize.disabled = form.elements.entryType.value !== "team";
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
    majorFamily: data.get("majorFamily") || "",
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

function applyProfileChange() {
  state.profile = profileFromForm();
  saveProfile();
  renderAll();
}

form.addEventListener("input", (event) => {
  if (event.target.name === "affiliation") state.profile.profileId = "";
  state.profile = profileFromForm();
  saveProfile();
  syncConditionalInputs();
  renderAll();
});

form.addEventListener("input", (event) => {
  if (event.target.name !== "affiliation") return;
  clearTimeout(departmentTimer);
  clearTimeout(majorTimer);
  const query = event.target.value.trim();
  const results = form.querySelector("#department-results");
  results.innerHTML = "";
  if (query.length < 2) return;
  departmentTimer = setTimeout(async () => {
    try {
      const school = form.elements.school.value.trim();
      const data = await getJson(`/api/departments?q=${encodeURIComponent(school ? `${school} ${query}` : query)}`);
      if (form.elements.affiliation.value.trim() !== query) return;
      form.querySelector("#department-note").textContent = data.count
        ? `공식 학과자료 ${data.reference_year || "연도 미상"}년 ${data.count.toLocaleString("ko-KR")}건에서 검색`
        : (data.coverage_note || "학과명을 직접 입력할 수 있습니다.");
      results.innerHTML = (data.departments || []).map((item) => `<button type="button" data-major="${escapeHtml(item.major)}" data-school="${escapeHtml(item.school)}" data-region="${escapeHtml(item.region || "")}" data-family="${escapeHtml(item.family || "")}">${escapeHtml(item.school)} · ${escapeHtml(item.major)}${item.family ? ` <small>${escapeHtml(item.family)}계열</small>` : ""}</button>`).join("");
    } catch {
      form.querySelector("#department-note").textContent = "학과 검색을 사용할 수 없습니다. 학과명은 직접 입력할 수 있습니다.";
    }
  }, 220);
  majorTimer = setTimeout(async () => {
    if (form.elements.majorFamily.value) return;
    try {
      const data = await getJson(`/api/majors?q=${encodeURIComponent(query)}`);
      const match = (data.majors || []).find((item) => item.family);
      if (match && !form.elements.majorFamily.value && form.elements.affiliation.value.trim() === query) {
        form.elements.majorFamily.value = match.family;
        form.querySelector("#department-note").textContent = `‘${match.major}’ 기준 ${match.family}계열로 추정 (${data.source}). 다르면 직접 바꿔 주세요.`;
        applyProfileChange();
      }
    } catch { /* optional enrichment */ }
  }, 600);
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
      const data = await getJson(`/api/schools?q=${encodeURIComponent(query)}`);
      if (form.elements.school.value.trim() !== query) return;
      form.querySelector("#school-note").textContent = data.count
        ? `공식 학과자료 ${data.reference_year || "연도 미상"}년 · 대학 ${data.count.toLocaleString("ko-KR")}곳 중 검색${data.schools.length ? "" : " · 일치하는 대학 없음"}`
        : "공식 대학 목록이 없습니다. 학교명을 직접 입력할 수 있습니다.";
      results.innerHTML = data.schools.map((item) => `<button type="button" data-school-choice="${escapeHtml(item.name)}" data-region="${escapeHtml(item.region || "")}">${escapeHtml(item.name)}${item.region ? ` · ${escapeHtml(item.region)}` : ""}</button>`).join("");
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
    applyProfileChange();
    return;
  }
  const school = event.target.closest("[data-school-choice]");
  if (school) {
    form.elements.school.value = school.dataset.schoolChoice;
    const region = APP_CONFIG.regionOptions.find((item) => school.dataset.region.startsWith(item));
    if (region) form.elements.schoolRegion.value = region;
    form.querySelector("#school-results").innerHTML = "";
    applyProfileChange();
    return;
  }
  const choice = event.target.closest("[data-major]");
  if (!choice) return;
  form.elements.affiliation.value = choice.dataset.major;
  form.elements.school.value = choice.dataset.school;
  if (choice.dataset.family) form.elements.majorFamily.value = choice.dataset.family;
  const region = APP_CONFIG.regionOptions.find((item) => choice.dataset.region.startsWith(item));
  if (region) form.elements.schoolRegion.value = region;
  form.querySelector("#department-results").innerHTML = "";
  applyProfileChange();
});

// ---------- explore ----------
function renderTabs(counts, total) {
  tabs.innerHTML = APP_CONFIG.filters.map((filter) => {
    const count = filter.id === "all" ? total : counts[filter.id];
    return `<button type="button" role="tab" aria-selected="${state.activeFilter === filter.id}" class="tab ${state.activeFilter === filter.id ? "active" : ""}" data-filter="${filter.id}" data-testid="tab-${filter.id}">${filter.label}<span>${count}</span></button>`;
  }).join("");
}

function conditionChips(decision) {
  const specified = decision.sections.flatMap((section) => section.specifiedFields ?? []);
  const missing = decision.missingFields ?? [];
  const chips = [...new Set(specified)].map((field) => `<span class="chip condition">${escapeHtml(fieldLabels[field] ?? field)} 조건</span>`);
  chips.push(...[...new Set(missing)].slice(0, 4).map((field) => `<span class="chip missing">명시 없음 · ${escapeHtml(fieldLabels[field] ?? field)}</span>`));
  chips.push(...(decision.otherConditions ?? []).map((item) => `<span class="chip notice">기타 조건 · ${escapeHtml(item)}</span>`));
  return chips.join("");
}

function sourceBadge(contest) {
  const source = sourceOf(contest);
  const cls = source.type === "official_api" || source.type === "official_list" ? "source-badge official" : source.type === "user_submission" ? "source-badge user" : "source-badge";
  return `<span class="${cls}" data-testid="source-badge">${escapeHtml(source.name)}</span>`;
}

function dataBadge(contest) {
  if (contest.validation_status === "verified") return '<span class="data-badge verified">검수 완료</span>';
  if (contest.validation_status === "draft") return '<span class="data-badge">사용자 추가 · 검수 전</span>';
  if (contest.is_sample) return '<span class="sample-badge">샘플 데이터</span>';
  return '<span class="data-badge">공식 데이터 · 검수 전</span>';
}

function cardHtml({ contest, decision, fit }) {
  const firstReason = decision.reasons?.[0]?.message ?? "판정 사유를 확인해 주세요.";
  const kind = kindLabels[contest.kind || "contest"] || "공모전";
  const dday = ddayText(contest.deadline);
  const nextEvent = (contest.details?.schedule || []).find((item) => (item.end_date || item.date) >= localToday());
  return `
    <article class="contest-card status-${decision.result}" data-testid="contest-card" data-contest-id="${escapeHtml(contest.id)}" data-result="${decision.result}" data-source="${escapeHtml(sourceOf(contest).id)}" data-kind="${escapeHtml(contest.kind || "contest")}">
      <div class="card-topline">
        <div class="badge-groups">
          <div class="badge-group">
            <span class="badge-group-label">지원 자격</span>
            <div class="badges">
              <span class="result-badge" data-testid="result-badge">${labels[decision.result]}</span>
              <span class="kind-badge">${escapeHtml(kind)}</span>
              ${dataBadge(contest)}
              ${contest.deadline && contest.deadline < localToday() ? '<span class="data-badge">접수 마감</span>' : ""}
            </div>
          </div>
          <div class="badge-group">
            <span class="badge-group-label">주제 관련성 · 자격과 별개</span>
            <div class="badges"><span class="fit-badge ${fit.level === "related" ? "" : fit.level === "unknown" ? "unknown" : "no-signal"}">${fit.level === "related" ? "내 주제와 연결" : fit.level === "unknown" ? "관련성 정보 부족" : "일치 신호 없음"}</span></div>
          </div>
        </div>
        <div class="card-side">
          ${sourceBadge(contest)}
          <span class="organizer">${escapeHtml(contest.organizer || "주최 미기재")}</span>
        </div>
      </div>
      <h3><a href="#/contest/${encodeURIComponent(contest.id)}" class="card-link" data-testid="card-link">${escapeHtml(contest.title)}</a></h3>
      <p class="deadline-line">
        ${contest.deadline ? `<span class="date-label">접수 마감 ${escapeHtml(contest.deadline)}</span>${dday ? ` <span class="dday ${daysUntil(contest.deadline) !== null && daysUntil(contest.deadline) <= 7 ? "urgent" : ""}">${dday}</span>` : ""}` : '<span class="date-label">마감일 미기재</span>'}
        ${contest.category ? ` · ${escapeHtml(contest.category)}` : titleTopics(contest.title).length ? ` · ${escapeHtml(titleTopics(contest.title).join(" · "))}` : ""}
        ${nextEvent && nextEvent.type !== "apply" ? ` · 다음 일정 ${escapeHtml(nextEvent.label)} ${escapeHtml(nextEvent.date)}` : ""}
      </p>
      <p class="reason-line">${escapeHtml(firstReason)}</p>
      <p class="fit-note"><span class="fit-note-label">주제 관련성 (자격 판정과 별개):</span> ${escapeHtml(fit.reasons.join(" "))}</p>
      ${contest.sections.length > 1 ? `<div class="section-picker"><label for="section-${escapeHtml(contest.id)}">지원 부문</label><select class="section-select" id="section-${escapeHtml(contest.id)}" data-section-for="${escapeHtml(contest.id)}"><option value="">부문 선택 전</option>${contest.sections.map((section) => `<option value="${escapeHtml(section.id)}" ${state.selectedSections[contest.id] === section.id ? "selected" : ""}>${escapeHtml(section.name || section.id)}</option>`).join("")}</select></div>` : ""}
      <div class="chips">${conditionChips(decision)}</div>
      <div class="card-actions">
        <a class="primary-link" href="#/contest/${encodeURIComponent(contest.id)}" data-testid="open-detail">상세 · 일정 · 제출물 보기 →</a>
        ${contest.source_url ? `<a class="secondary-link" href="${escapeHtml(contest.source_url)}" target="_blank" rel="noopener noreferrer">원문 ↗</a>` : ""}
      </div>
    </article>`;
}

function filteredContests() {
  const query = state.query.toLocaleLowerCase("ko-KR");
  const today = localToday();
  return state.contests.filter((contest) => {
    const searchText = `${contest.title || ""} ${contest.organizer || ""} ${contest.category || ""} ${(contest.topic_tags || []).join(" ")}`.toLocaleLowerCase("ko-KR");
    if (query && !searchText.includes(query)) return false;
    if (state.kindFilter !== "all" && (contest.kind || "contest") !== state.kindFilter) return false;
    if (state.sourceFilter !== "all" && sourceOf(contest).id !== state.sourceFilter) return false;
    if (state.dataFilter !== "all" && (state.dataFilter === "sample") !== Boolean(contest.is_sample)) return false;
    if (state.categoryFilter !== "all" && contest.category !== state.categoryFilter && !titleTopics(contest.title).includes(state.categoryFilter)) return false;
    if (state.deadlineFilter === "unknown" && contest.deadline) return false;
    if (state.deadlineFilter === "open" && !(contest.deadline && contest.deadline >= today)) return false;
    return true;
  });
}

function renderResults() {
  if (!state.loaded) return;
  const judged = filteredContests().map((contest) => ({ contest, decision: judge(contest), fit: evaluateFit(contest, state.profile) }));
  if (state.sort === "relevance") judged.sort((a, b) => ({ related: 0, unknown: 1, no_signal: 2 }[a.fit.level] - { related: 0, unknown: 1, no_signal: 2 }[b.fit.level]));
  if (state.sort === "deadline") judged.sort((a, b) => (a.contest.deadline || "9999-12-31").localeCompare(b.contest.deadline || "9999-12-31"));
  const counts = { eligible: 0, needs_review: 0, ineligible: 0 };
  judged.forEach(({ decision }) => { counts[decision.result] += 1; });
  renderTabs(counts, judged.length);
  summary.innerHTML = `<span class="summary-lead">현재 프로필 기준</span><span class="stat" data-testid="count-eligible"><strong class="stat-num stat-eligible">${counts.eligible}</strong>지원 가능</span><span class="stat" data-testid="count-needs_review"><strong class="stat-num stat-needs_review">${counts.needs_review}</strong>확인 필요</span><span class="stat" data-testid="count-ineligible"><strong class="stat-num stat-ineligible">${counts.ineligible}</strong>지원 불가</span>`;
  const visible = state.activeFilter === "all" ? judged : judged.filter(({ decision }) => decision.result === state.activeFilter);
  if (visible.length) {
    list.innerHTML = visible.slice(0, 120).map((item) => cardHtml(item)).join("")
      + (visible.length > 120 ? `<p class="muted list-more">${visible.length - 120}건이 더 있습니다. 검색·필터로 범위를 좁혀 주세요.</p>` : "");
  } else {
    list.innerHTML = `<div class="empty-state" data-testid="empty-state"><strong>${judged.length ? "해당 판정의 공고가 없습니다." : "조건에 맞는 공고가 없습니다."}</strong><span>프로필이나 필터를 바꿔 보세요.</span><button type="button" class="empty-reset" id="reset-filters">필터 초기화</button></div>`;
  }
}

function resetFilters() {
  Object.assign(state, { activeFilter: "all", query: "", kindFilter: "all", sourceFilter: "all", dataFilter: "all", categoryFilter: "all", deadlineFilter: "all", sort: "deadline" });
  $("#contest-search").value = "";
  for (const [selector, value] of [["#kind-filter", "all"], ["#source-filter", "all"], ["#data-filter", "all"], ["#category-filter", "all"], ["#deadline-filter", "all"], ["#sort-filter", "deadline"]]) $(selector).value = value;
  renderResults();
}

function renderSourceStrip() {
  const strip = $("#source-strip");
  if (!state.sources.length) { strip.innerHTML = ""; return; }
  const described = new Map((state.dataStatus?.sources || []).map((item) => [item.id, item]));
  strip.innerHTML = `<span class="strip-label">공고 출처</span>` + state.sources.map((item) => {
    const meta = described.get(item.id) || {};
    const label = meta.name || item.id;
    const status = item.status === "ok" ? `${item.count}건` : item.status === "not_configured" ? "키 미설정" : "응답 오류";
    return `<button type="button" class="source-chip ${item.status}" data-source-chip="${escapeHtml(item.id)}" title="${escapeHtml(meta.description || item.error || "")}" data-testid="source-chip-${escapeHtml(item.id)}">${escapeHtml(label)} <b>${escapeHtml(status)}</b></button>`;
  }).join("");
}

function updateDataSummary() {
  const total = state.contests.length;
  $("#contest-total").textContent = total;
  const real = state.contests.filter((item) => !item.is_sample).length;
  const official = state.contests.filter((item) => ["official_api", "official_list"].includes(sourceOf(item).type)).length;
  const user = state.contests.filter((item) => sourceOf(item).type === "user_submission").length;
  const status = state.dataStatus;
  let text = `공식 출처 ${official}건 · 사용자 추가 ${user}건 · 샘플 ${total - real}건`;
  if (status && typeof status.departments === "number") text += ` · 학과 ${status.departments.toLocaleString("ko-KR")}개 · 학교 ${status.schools.toLocaleString("ko-KR")}곳 (${status.reference_year}년 기준)`;
  $("#data-summary").textContent = text;
  const footer = $("#footer-sources");
  if (footer) footer.textContent = `저장소: ${state.store?.backend === "supabase" ? "Supabase" : "로컬"} · 데이터 출처: ${(status?.sources || []).filter((item) => item.configured).map((item) => item.name).join(", ") || "샘플"}`;
}

function populateFilters() {
  const categories = [...new Set(state.contests.flatMap((item) => [item.category, ...titleTopics(item.title)].filter(Boolean)))].sort();
  $("#category-filter").innerHTML = `<option value="all">전체 주제</option>${categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("")}`;
  $("#kind-filter").innerHTML = `<option value="all">전체 유형</option>${APP_CONFIG.kindOptions.map((item) => `<option value="${item.value}">${item.label} (${state.contests.filter((contest) => (contest.kind || "contest") === item.value).length})</option>`).join("")}`;
  const sources = new Map();
  for (const contest of state.contests) {
    const source = sourceOf(contest);
    sources.set(source.id, { name: source.name, count: (sources.get(source.id)?.count || 0) + 1 });
  }
  $("#source-filter").innerHTML = `<option value="all">전체 출처</option>${[...sources].map(([id, item]) => `<option value="${escapeHtml(id)}">${escapeHtml(item.name)} (${item.count})</option>`).join("")}`;
  $("#kind-filter").value = state.kindFilter;
  $("#source-filter").value = sources.has(state.sourceFilter) ? state.sourceFilter : "all";
}

// ---------- contest detail ----------
function findContest(id) { return state.contests.find((item) => item.id === id); }

function replaceContest(updated) {
  const index = state.contests.findIndex((item) => item.id === updated.id);
  if (index >= 0) state.contests[index] = updated; else state.contests.unshift(updated);
}

function scheduleTimeline(contest) {
  const items = contest.details?.schedule || [];
  if (!items.length) return '<p class="muted">일정 정보가 없습니다. 원문 분석을 실행하거나 주최 공고를 확인하세요.</p>';
  return `<ol class="timeline" data-testid="schedule-timeline">${items.map((item) => {
    const date = item.end_date ? `${formatDate(item.date)} ~ ${formatDate(item.end_date)}` : formatDate(item.date);
    const keyDate = item.end_date || item.date;
    const past = keyDate < localToday();
    return `<li class="timeline-item ${past ? "past" : ""}" data-testid="schedule-item" data-type="${escapeHtml(item.type)}">
      <span class="timeline-tag">${escapeHtml(scheduleIcons[item.type] || "일정")}</span>
      <div><strong>${escapeHtml(item.label)}</strong> <span class="timeline-dday">${past ? "지남" : escapeHtml(ddayText(keyDate))}</span><br><span class="timeline-date">${escapeHtml(date)}</span>
      ${item.evidence ? `<q class="timeline-evidence">${escapeHtml(item.evidence)}</q>` : ""}</div></li>`;
  }).join("")}</ol>`;
}

function deliverableChecklist(contest) {
  const items = contest.details?.deliverables || [];
  if (!items.length) return '<p class="muted">공고에 제출물 목록이 없거나 추출하지 못했습니다. 원문에서 확인하세요.</p>';
  const checked = new Set(state.checklist[contest.id] || []);
  const done = items.filter((_, index) => checked.has(index)).length;
  return `<p class="checklist-progress" data-testid="checklist-progress">${done} / ${items.length} 준비 완료</p><ul class="checklist" data-testid="deliverables">${items.map((item, index) => `
    <li><label><input type="checkbox" data-check="${escapeHtml(contest.id)}" data-index="${index}" ${checked.has(index) ? "checked" : ""} data-testid="deliverable-check"> <span>${escapeHtml(item.text)}</span></label>
    ${item.evidence && item.evidence !== item.text ? `<q>${escapeHtml(item.evidence)}</q>` : ""}</li>`).join("")}</ul>`;
}

function evidenceRows(contest) {
  const rows = [];
  for (const section of contest.sections) {
    for (const [field, evidence] of Object.entries(section.evidence ?? {})) {
      if (!evidence) continue;
      const excerpts = Array.isArray(evidence) ? evidence : [evidence];
      rows.push(`<div class="evidence-row"><dt>${escapeHtml(fieldLabels[field] ?? field)}${contest.sections.length > 1 && section.name ? ` · ${escapeHtml(section.name)}` : ""}</dt><dd>${excerpts.map((item) => `<q>${escapeHtml(item)}</q>`).join("<br>")}</dd></div>`);
    }
  }
  return rows.length ? rows.join("") : '<p class="muted">저장된 근거 발췌가 없습니다.</p>';
}

function compareTable(contest) {
  const profiles = [{ id: "current", name: "현재 입력", profile: state.profile }, ...state.savedProfiles];
  return `<table class="compare-table" data-testid="detail-compare"><thead><tr><th>프로필</th><th>학교 · 학과</th><th>판정</th><th>사유</th></tr></thead><tbody>${profiles.map((item) => {
    const decision = judge(contest, item.profile);
    return `<tr class="status-${decision.result}"><td>${escapeHtml(item.name)}</td><td>${escapeHtml([item.profile.school, item.profile.affiliation].filter(Boolean).join(" · ") || "미입력")}</td><td><span class="result-pill">${labels[decision.result]}</span></td><td>${escapeHtml(decision.reasons?.[0]?.message || "")}</td></tr>`;
  }).join("")}</tbody></table>`;
}

function detailHtml(contest) {
  const decision = judge(contest);
  const details = contest.details || {};
  const kind = kindLabels[contest.kind || "contest"] || "공모전";
  const job = details.job;
  const facts = [
    ["유형", kind], ["출처", sourceOf(contest).name], ["주최·기관", contest.organizer || "미기재"],
    ["접수 마감", contest.deadline ? `${contest.deadline} (${ddayText(contest.deadline)})` : details.deadline_note || "미기재"],
    ["분야", contest.category || titleTopics(contest.title).join(" · ") || "미기재"],
    details.reward ? ["시상·보상", details.reward.value] : null,
    details.entry_fee ? ["참가비", details.entry_fee.value] : null,
    details.team_note ? ["팀 구성", details.team_note] : null,
    job?.pay ? ["급여", job.pay] : null, job?.region ? ["근무지", job.region] : null,
    job?.education ? ["학력", job.education] : null, job?.career ? ["경력", job.career] : null,
  ].filter(Boolean);
  const canAnalyze = contest.source_url && !contest.is_sample;
  return `
    <a class="back-link" href="#/explore" data-testid="back-to-list">← 목록으로</a>
    <article class="detail-page status-${decision.result}" data-contest-id="${escapeHtml(contest.id)}">
      <header class="detail-header">
        <div class="badges"><span class="result-badge" data-testid="detail-result">${labels[decision.result]}</span><span class="kind-badge">${escapeHtml(kind)}</span>${dataBadge(contest)}${sourceBadge(contest)}</div>
        <h2 data-testid="detail-title">${escapeHtml(contest.title)}</h2>
        <p class="detail-reason">${escapeHtml(decision.reasons?.[0]?.message || "")}</p>
        <div class="detail-actions">
          ${contest.source_url ? `<a class="primary-link" href="${escapeHtml(contest.source_url)}" target="_blank" rel="noopener noreferrer" data-testid="detail-source">원문 공고 열기 ↗</a>` : ""}
          ${(details.schedule || []).length ? '<button type="button" class="secondary-button" id="download-ics" data-testid="download-ics">캘린더(.ics) 저장</button>' : ""}
          ${canAnalyze ? `<button type="button" class="secondary-button" id="analyze-contest" data-testid="analyze-contest">${contest.analysis ? "원문 다시 분석" : "원문 분석으로 자격·일정 보강"}</button>` : ""}
        </div>
        <p id="analyze-message" class="muted" role="status" aria-live="polite" data-testid="analyze-message">${contest.analysis ? `원문 분석 ${new Date(contest.analysis.analyzed_at).toLocaleString("ko-KR")} · 자격 ${contest.analysis.eligibility_found ? "발견" : "미발견"} · 일정 ${contest.analysis.schedule_items}건 · 제출물 ${contest.analysis.deliverables}건` : ""}</p>
      </header>
      <div class="detail-grid">
        <section class="detail-card"><h3>핵심 정보</h3><dl class="facts" data-testid="detail-facts">${facts.map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
          ${details.summary ? `<p class="detail-summary">${escapeHtml(details.summary)}</p>` : ""}
          ${details.preference ? `<p class="muted">우대 사항: ${escapeHtml(details.preference)}</p>` : ""}</section>
        <section class="detail-card"><h3>일정</h3>${scheduleTimeline(contest)}</section>
        <section class="detail-card"><h3>제출해야 할 것</h3>${deliverableChecklist(contest)}
          ${details.apply_method ? `<h4>접수 방법</h4><p data-testid="apply-method">${escapeHtml(details.apply_method.value)}</p>` : ""}
          ${details.rights ? `<h4>권리 관계</h4><p class="muted">${escapeHtml(details.rights.value)}</p>` : ""}</section>
        <section class="detail-card wide"><h3>프로필별 판정 비교</h3>${compareTable(contest)}</section>
        <section class="detail-card wide"><h3>자격 조건과 원문 근거</h3><div class="chips">${conditionChips(decision)}</div><dl class="evidence-list" data-testid="evidence-list">${evidenceRows(contest)}</dl>
          ${(details.links || []).length ? `<p class="link-row">${details.links.map((link) => `<a href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link.label)} ↗</a>`).join("")}</p>` : ""}
          <p class="final-notice">판정 결과와 별개로 최종 지원 전 주최 공고를 반드시 확인하세요.</p></section>
      </div>
    </article>`;
}

async function renderDetail(id) {
  const target = $("#contest-detail");
  let contest = findContest(id);
  if (!contest) {
    target.innerHTML = '<div class="loading-state"><span class="loader" aria-hidden="true"></span><span>공고를 불러오는 중입니다.</span></div>';
    try {
      contest = (await getJson(`/api/contests/${encodeURIComponent(id)}`)).contest;
      replaceContest(contest);
    } catch (error) {
      target.innerHTML = `<div class="empty-state"><strong>공고를 찾을 수 없습니다.</strong><span>${escapeHtml(error.message)}</span><a class="primary-link" href="#/explore">목록으로</a></div>`;
      return;
    }
  }
  target.innerHTML = detailHtml(contest);
  document.title = `${contest.title} — Contest Fit`;
}

function icsFor(contest) {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  const fold = (value) => String(value).replace(/[\\;,]/g, (char) => `\\${char}`).replace(/\n/g, "\\n");
  const events = (contest.details?.schedule || []).map((item, index) => {
    const start = (item.end_date && item.type === "apply" ? item.end_date : item.date).replaceAll("-", "");
    const endDate = new Date(`${item.end_date && item.type === "apply" ? item.end_date : item.date}T00:00:00`);
    endDate.setDate(endDate.getDate() + 1);
    const end = `${endDate.getFullYear()}${String(endDate.getMonth() + 1).padStart(2, "0")}${String(endDate.getDate()).padStart(2, "0")}`;
    const label = item.type === "apply" ? (item.end_date || !item.date ? "접수 마감" : item.label) : item.label;
    return ["BEGIN:VEVENT", `UID:${contest.id}-${index}@contestfit`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${start}`, `DTEND;VALUE=DATE:${end}`,
      `SUMMARY:${fold(`[${label}] ${contest.title}`)}`, `DESCRIPTION:${fold(`${item.evidence || ""}\n${contest.source_url || ""}`)}`, contest.source_url ? `URL:${contest.source_url}` : "", "END:VEVENT"].filter(Boolean).join("\r\n");
  });
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ContestFit//KO", "CALSCALE:GREGORIAN", ...events, "END:VCALENDAR"].join("\r\n");
}

function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$("#contest-detail").addEventListener("click", async (event) => {
  const page = event.target.closest("[data-contest-id]");
  if (!page) return;
  const contest = findContest(page.dataset.contestId);
  if (!contest) return;
  if (event.target.closest("#download-ics")) {
    download(`contestfit-${contest.id}.ics`, icsFor(contest), "text/calendar;charset=utf-8");
    return;
  }
  const analyzeButton = event.target.closest("#analyze-contest");
  if (analyzeButton) {
    analyzeButton.disabled = true;
    const message = $("#analyze-message");
    message.textContent = "주최 기관 원문을 확인하고 있습니다… (robots.txt 확인 후 한 번만 열람)";
    try {
      const updated = (await getJson(`/api/contests/${encodeURIComponent(contest.id)}/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })).contest;
      replaceContest(updated);
      await renderDetail(updated.id);
      renderResults();
    } catch (error) {
      message.textContent = `${error.message} 원문을 공고 추가 화면에 붙여넣어 분석할 수도 있습니다.`;
      analyzeButton.disabled = false;
    }
  }
});

$("#contest-detail").addEventListener("change", (event) => {
  const box = event.target.closest("[data-check]");
  if (!box) return;
  const id = box.dataset.check;
  const checked = new Set(state.checklist[id] || []);
  if (box.checked) checked.add(Number(box.dataset.index)); else checked.delete(Number(box.dataset.index));
  state.checklist[id] = [...checked];
  saveJson(APP_CONFIG.checklistKey, state.checklist);
  const contest = findContest(id);
  const total = contest?.details?.deliverables?.length || 0;
  const progress = $("#contest-detail .checklist-progress");
  if (progress) progress.textContent = `${checked.size} / ${total} 준비 완료`;
});

// ---------- calendar ----------
function renderCalendar() {
  if (!state.loaded) return;
  const scope = $("#calendar-scope").value;
  const range = Number($("#calendar-range").value);
  const type = $("#calendar-type").value;
  const today = localToday();
  const limit = new Date(`${today}T00:00:00`);
  limit.setDate(limit.getDate() + range);
  const limitText = `${limit.getFullYear()}-${String(limit.getMonth() + 1).padStart(2, "0")}-${String(limit.getDate()).padStart(2, "0")}`;
  const events = [];
  for (const contest of state.contests) {
    if (contest.is_sample && state.contests.some((item) => !item.is_sample)) continue;
    const decision = judge(contest);
    if (scope === "possible" && decision.result === "ineligible") continue;
    if (scope === "eligible" && decision.result !== "eligible") continue;
    for (const item of contest.details?.schedule || []) {
      const date = item.type === "apply" ? (item.end_date || item.date) : item.date;
      if (!date || date < today || date > limitText) continue;
      if (type !== "all" && item.type !== type) continue;
      events.push({ date, item, contest, decision });
    }
  }
  events.sort((a, b) => a.date.localeCompare(b.date) || a.contest.title.localeCompare(b.contest.title));
  const target = $("#calendar-list");
  if (!events.length) {
    target.innerHTML = '<div class="empty-state" data-testid="calendar-empty"><strong>이 기간에 일정이 없습니다.</strong><span>판정 범위나 기간을 넓혀 보세요.</span></div>';
    return;
  }
  const groups = new Map();
  for (const event of events) {
    if (!groups.has(event.date)) groups.set(event.date, []);
    groups.get(event.date).push(event);
  }
  target.innerHTML = [...groups].map(([date, items]) => `
    <section class="calendar-day" data-testid="calendar-day"><h3><span>${escapeHtml(formatDate(date))}</span><span class="dday">${escapeHtml(ddayText(date))}</span></h3>
      <ul>${items.map(({ item, contest, decision }) => `<li class="calendar-event status-${decision.result}" data-testid="calendar-event">
        <span class="timeline-tag">${escapeHtml(item.type === "apply" ? "마감" : scheduleIcons[item.type] || "일정")}</span>
        <a href="#/contest/${encodeURIComponent(contest.id)}">${escapeHtml(contest.title)}</a>
        <span class="calendar-meta">${escapeHtml(item.label)} · ${labels[decision.result]} · ${escapeHtml(sourceOf(contest).name)}</span></li>`).join("")}</ul></section>`).join("");
}
for (const id of ["#calendar-scope", "#calendar-range", "#calendar-type"]) $(id).addEventListener("change", renderCalendar);

// ---------- add posting ----------
const importForm = $("#import-form");
const importMessage = $("#import-message");
const saveButton = $("#save-submission");
const downloadPreview = $("#download-preview");

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = importForm.querySelector('button[type="submit"]');
  button.disabled = true;
  saveButton.hidden = true;
  downloadPreview.hidden = true;
  importMessage.textContent = "공고 조건을 읽고 있습니다…";
  try {
    const data = new FormData(importForm);
    const result = await getJson("/api/preview", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_url: data.get("source_url"), text: data.get("text") }) });
    state.preview = result.contest;
    const decision = judge(result.contest);
    $("#import-result").innerHTML = `<div class="preview-card">${cardHtml({ contest: result.contest, decision, fit: evaluateFit(result.contest, state.profile) })}
      <div class="detail-grid compact"><section class="detail-card"><h3>추출한 일정</h3>${scheduleTimeline(result.contest)}</section>
      <section class="detail-card"><h3>추출한 제출물</h3>${deliverableChecklist(result.contest)}</section></div></div>`;
    importMessage.textContent = `미리보기 완료 · 자격 ${result.contest.eligibility_known ? "조건 발견" : "조건 미발견"} · 일정 ${result.contest.details.schedule.length}건 · 제출물 ${result.contest.details.deliverables.length}건. 확인 후 ‘목록에 저장’을 누르세요.`;
    saveButton.hidden = false;
    downloadPreview.hidden = false;
  } catch (error) {
    importMessage.textContent = error.message || "서버 연결을 확인해 주세요.";
  } finally {
    button.disabled = false;
  }
});

saveButton.addEventListener("click", async () => {
  if (!state.preview) return;
  saveButton.disabled = true;
  importMessage.textContent = "목록에 저장하고 있습니다…";
  try {
    const data = new FormData(importForm);
    const result = await getJson("/api/submissions", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_url: data.get("source_url"), text: data.get("text") }) });
    replaceContest(result.contest);
    populateFilters();
    updateDataSummary();
    renderAll();
    importMessage.innerHTML = `저장했습니다. <a href="#/contest/${encodeURIComponent(result.contest.id)}" data-testid="saved-link">상세 보기 →</a> 다른 사용자에게도 ‘사용자 추가 · 검수 전’으로 표시됩니다.`;
    saveButton.hidden = true;
  } catch (error) {
    importMessage.textContent = error.message || "저장하지 못했습니다.";
  } finally {
    saveButton.disabled = false;
  }
});

downloadPreview.addEventListener("click", () => {
  if (state.preview) download(`${state.preview.id}.json`, JSON.stringify(state.preview, null, 2), "application/json");
});

// ---------- profiles ----------
function renderProfiles() {
  const target = $("#profile-compare");
  if (!state.savedProfiles.length) {
    target.innerHTML = '<div class="empty-state" data-testid="profiles-empty"><strong>저장한 프로필이 없습니다.</strong><span>탐색 화면에서 조건을 입력한 뒤 이름을 붙여 저장하세요.</span></div>';
    return;
  }
  const contests = state.contests.filter((item) => !item.is_sample || state.contests.every((contest) => contest.is_sample));
  target.innerHTML = `<table class="compare-table profiles-table" data-testid="profiles-table"><thead><tr><th>프로필</th><th>학교 · 학과 · 계열</th><th>신분 · 나이 · 지역</th><th>지원 가능</th><th>확인 필요</th><th>지원 불가</th><th></th></tr></thead><tbody>${state.savedProfiles.map((item) => {
    const counts = { eligible: 0, needs_review: 0, ineligible: 0 };
    contests.forEach((contest) => { counts[judge(contest, item.profile).result] += 1; });
    const active = state.profile.profileId === item.id;
    return `<tr data-testid="profile-row" class="${active ? "active-row" : ""}"><td><strong>${escapeHtml(item.name)}</strong>${active ? ' <span class="kind-badge">적용 중</span>' : ""}</td>
      <td>${escapeHtml([item.profile.school, item.profile.affiliation, item.profile.majorFamily && `${item.profile.majorFamily}계열`].filter(Boolean).join(" · ") || "미입력")}</td>
      <td>${escapeHtml([item.profile.status, item.profile.age !== "" && item.profile.age != null ? `만 ${item.profile.age}세` : "", item.profile.region].filter(Boolean).join(" · ") || "미입력")}</td>
      <td class="num stat-eligible" data-testid="profile-eligible">${counts.eligible}</td><td class="num stat-needs_review">${counts.needs_review}</td><td class="num stat-ineligible" data-testid="profile-ineligible">${counts.ineligible}</td>
      <td class="row-actions"><button type="button" data-apply-profile="${escapeHtml(item.id)}" data-testid="profile-apply">적용</button><button type="button" class="ghost" data-delete-profile="${escapeHtml(item.id)}">삭제</button></td></tr>`;
  }).join("")}</tbody></table><p class="muted">비교 대상: ${contests.length}건 (${contests.some((item) => item.is_sample) ? "샘플 포함" : "실제 공고"}) · 공고별 비교는 상세 화면에서 볼 수 있습니다.</p>`;
}

$("#save-profile-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = new FormData(event.target).get("name").trim();
  if (!name) return;
  const id = `p-${Date.now().toString(36)}`;
  const profile = { ...state.profile, profileId: id };
  state.savedProfiles = [...state.savedProfiles.filter((item) => item.name !== name), { id, name, profile }].slice(-12);
  state.profile = profile;
  saveJson(APP_CONFIG.profilesKey, state.savedProfiles);
  saveProfile();
  event.target.reset();
  $("#profile-message").textContent = `‘${name}’ 프로필을 저장했습니다.`;
  renderForm();
  renderAll();
});

$("#profile-compare").addEventListener("click", (event) => {
  const apply = event.target.closest("[data-apply-profile]");
  const remove = event.target.closest("[data-delete-profile]");
  if (apply) {
    const item = state.savedProfiles.find((entry) => entry.id === apply.dataset.applyProfile);
    if (!item) return;
    state.profile = { ...EMPTY_PROFILE, ...item.profile, profileId: item.id };
    saveProfile();
    renderForm();
    renderAll();
    $("#profile-message").textContent = `‘${item.name}’ 프로필을 적용했습니다. 탐색 화면의 판정이 이 조건으로 바뀌었습니다.`;
  }
  if (remove) {
    state.savedProfiles = state.savedProfiles.filter((entry) => entry.id !== remove.dataset.deleteProfile);
    saveJson(APP_CONFIG.profilesKey, state.savedProfiles);
    renderProfiles();
  }
});

// ---------- feedback ----------
async function loadFeedbackSummary() {
  try {
    const data = await getJson("/api/feedback-summary");
    $("#feedback-summary").innerHTML = data.responses
      ? `<dl class="facts"><div><dt>응답 수</dt><dd>${data.responses}</dd></div><div><dt>과제 완료율</dt><dd>${Math.round(data.task_completed_rate * 100)}%</dd></div><div><dt>판정 이유 이해율</dt><dd>${Math.round(data.reason_clear_rate * 100)}%</dd></div><div><dt>편의성 평균</dt><dd>${data.ease_average} / 5</dd></div></dl>`
      : "아직 응답이 없습니다.";
  } catch (error) {
    $("#feedback-summary").textContent = error.message;
  }
}

$("#feedback-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("#feedback-message");
  const data = new FormData(event.target);
  try {
    await getJson("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_completed: data.get("task_completed") === "yes", reason_clear: data.get("reason_clear") === "yes", ease: Number(data.get("ease")) }) });
    event.target.reset();
    message.textContent = "의견을 저장했습니다. 감사합니다.";
    loadFeedbackSummary();
  } catch (error) {
    message.textContent = error.message || "서버 연결을 확인해 주세요.";
  }
});

// ---------- explore events ----------
tabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.activeFilter = button.dataset.filter;
  renderResults();
});
list.addEventListener("click", (event) => {
  if (event.target.closest("#reset-filters")) resetFilters();
});
list.addEventListener("change", (event) => {
  const picker = event.target.closest("[data-section-for]");
  if (!picker) return;
  state.selectedSections[picker.dataset.sectionFor] = picker.value;
  renderResults();
});
$("#source-strip").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-source-chip]");
  if (!chip) return;
  state.sourceFilter = state.sourceFilter === chip.dataset.sourceChip ? "all" : chip.dataset.sourceChip;
  $("#source-filter").value = [...$("#source-filter").options].some((option) => option.value === state.sourceFilter) ? state.sourceFilter : "all";
  renderResults();
});
$("#contest-search").addEventListener("input", (event) => { state.query = event.target.value.trim(); renderResults(); });
for (const [selector, key] of [["#kind-filter", "kindFilter"], ["#source-filter", "sourceFilter"], ["#data-filter", "dataFilter"], ["#category-filter", "categoryFilter"], ["#deadline-filter", "deadlineFilter"], ["#sort-filter", "sort"]]) {
  $(selector).addEventListener("change", (event) => { state[key] = event.target.value; renderResults(); });
}

// ---------- routing ----------
function currentRoute() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [view, ...rest] = hash.split("/");
  if (view === "contest" && rest.length) return { view: "contest", id: decodeURIComponent(rest.join("/")) };
  return { view: ["explore", "calendar", "add", "profiles", "feedback"].includes(view) ? view : "explore" };
}

function renderAll() {
  renderResults();
  const route = currentRoute();
  if (route.view === "calendar") renderCalendar();
  if (route.view === "profiles") renderProfiles();
  if (route.view === "contest" && state.loaded) {
    const contest = findContest(route.id);
    if (contest) $("#contest-detail").innerHTML = detailHtml(contest);
  }
}

function showRoute() {
  const route = currentRoute();
  for (const view of document.querySelectorAll("[data-view]")) view.hidden = view.dataset.view !== route.view;
  for (const link of document.querySelectorAll("#main-nav [data-route]")) {
    const active = link.dataset.route === route.view || (route.view === "contest" && link.dataset.route === "explore");
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  }
  document.title = { explore: "Contest Fit — 공모전 자격 판정", calendar: "일정 — Contest Fit", add: "공고 추가 — Contest Fit", profiles: "프로필 비교 — Contest Fit", feedback: "의견 — Contest Fit", contest: "공고 상세 — Contest Fit" }[route.view];
  if (route.view === "contest") renderDetail(route.id);
  if (route.view === "calendar") renderCalendar();
  if (route.view === "profiles") renderProfiles();
  if (route.view === "feedback") loadFeedbackSummary();
  if (route.view !== "explore") window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", showRoute);

// ---------- start ----------
async function loadStatus() {
  try { state.dataStatus = await getJson("/api/data-status"); } catch { state.dataStatus = null; }
  renderSourceStrip();
  updateDataSummary();
}

async function start() {
  renderForm();
  showRoute();
  loadStatus();
  try {
    const data = await getJson("/api/contests");
    state.contests = data.contests || [];
    state.sources = data.sources || [];
    state.store = data.store || null;
    if (state.contests.some((item) => !item.is_sample)) {
      state.dataFilter = "real";
      $("#data-filter").value = "real";
    }
  } catch (error) {
    console.error(error);
    try {
      const seed = await getJson("./data/seed.json");
      state.contests = seed.contests;
      $("#fallback-banner").hidden = false;
    } catch {
      loading.innerHTML = "<strong>공고 데이터를 불러오지 못했습니다.</strong><span>서버 연결을 확인해 주세요.</span>";
      return;
    }
  }
  state.loaded = true;
  loading.hidden = true;
  populateFilters();
  renderSourceStrip();
  updateDataSummary();
  renderAll();
  if (currentRoute().view === "contest") renderDetail(currentRoute().id);
  document.body.dataset.ready = "true";
}

start();
