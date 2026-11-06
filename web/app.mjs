import { judgeAll } from "./decision-engine.mjs";
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
  nationality: "국적",
  business_reg: "사업자",
  entry_type: "참가 형태",
  team_size: "팀 인원",
};

const state = {
  contests: [],
  profile: loadProfile(),
  activeFilter: "all",
};

const form = document.querySelector("#profile-form");
const tabs = document.querySelector("#result-tabs");
const list = document.querySelector("#contest-list");
const summary = document.querySelector("#summary-counts");
const loading = document.querySelector("#loading-state");

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
      <input name="affiliation" type="text" placeholder="예: 컴퓨터공학과, 직장인" value="${escapeHtml(state.profile.affiliation)}">
    </label>
    <label>5. 거주 지역
      <select name="region"><option value="">선택해 주세요</option>${optionList(APP_CONFIG.regionOptions, state.profile.region)}</select>
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
    region: data.get("region") || "",
    businessStatus: data.get("businessStatus") || "",
    businessYears: data.get("businessYears") === "" ? "" : Number(data.get("businessYears")),
    entryType: data.get("entryType") || "",
    teamSize: data.get("teamSize") === "" ? "" : Number(data.get("teamSize")),
  };
}

function renderTabs(counts) {
  tabs.innerHTML = APP_CONFIG.filters.map((filter) => {
    const count = filter.id === "all" ? state.contests.length : counts[filter.id];
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

function cardHtml({ contest, decision }) {
  const firstReason = decision.reasons?.[0]?.message ?? "판정 사유를 확인해 주세요.";
  const collected = contest.collected_at ? new Date(contest.collected_at).toLocaleDateString("ko-KR") : "미기재";
  return `
    <article class="contest-card status-${decision.result}">
      <div class="card-topline">
        <div class="badges">
          <span class="result-badge">${labels[decision.result]}</span>
          <span class="data-badge">검증 전 데이터</span>
          <span class="sample-badge">${contest.is_sample ? "샘플" : "실제"}</span>
        </div>
        <span class="organizer">${escapeHtml(contest.organizer || "주최 미기재")}</span>
      </div>
      <h3>${escapeHtml(contest.title)}</h3>
      <p class="reason-line">${escapeHtml(firstReason)}</p>
      <div class="chips">${conditionChips(decision)}</div>
      <details>
        <summary>근거와 상세 보기 <span aria-hidden="true">＋</span></summary>
        <div class="detail-body">
          <dl class="evidence-list">${evidenceRows(contest)}</dl>
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
  const judged = judgeAll(state.contests, state.profile, settings);
  const counts = { eligible: 0, needs_review: 0, ineligible: 0 };
  judged.forEach(({ decision }) => { counts[decision.result] += 1; });
  renderTabs(counts);
  summary.innerHTML = `현재 프로필 기준 <strong>${counts.eligible}</strong>개 가능 · <strong>${counts.needs_review}</strong>개 확인 필요 · <strong>${counts.ineligible}</strong>개 불가`;
  const visible = state.activeFilter === "all" ? judged : judged.filter(({ decision }) => decision.result === state.activeFilter);
  list.innerHTML = visible.length ? visible.map(cardHtml).join("") : `<div class="empty-state"><strong>해당 판정의 공고가 없습니다.</strong><span>프로필이나 필터를 바꿔 보세요.</span></div>`;
}

form.addEventListener("input", () => {
  state.profile = profileFromForm();
  saveProfile();
  syncConditionalInputs();
  renderResults();
});

tabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.activeFilter = button.dataset.filter;
  renderResults();
});

async function start() {
  renderForm();
  try {
    const response = await fetch(`${APP_CONFIG.apiBaseUrl}/contests/feed`);
    if (!response.ok) throw new Error(`API load failed: ${response.status}`);
    const contests = await response.json();
    if (!Array.isArray(contests) || contests.length === 0) throw new Error("API returned no contest data");
    state.contests = contests;
    loading.hidden = true;
    renderResults();
  } catch (error) {
    try {
      const response = await fetch("./data/seed.json");
      if (!response.ok) throw new Error(`seed load failed: ${response.status}`);
      const seed = await response.json();
      state.contests = seed.contests;
      loading.hidden = true;
      renderResults();
      console.warn("서버 API를 사용할 수 없어 정적 seed.json으로 표시합니다.", error);
    } catch (seedError) {
      loading.innerHTML = `<strong>공모전 데이터를 불러오지 못했습니다.</strong><span>서버 또는 로컬 웹 서버가 실행 중인지 확인해 주세요.</span>`;
      console.error(seedError);
    }
  }
}

start();
