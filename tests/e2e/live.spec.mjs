// Live E2E against the deployed site (E2E_MODE=live BASE_URL=https://...).
// Real official APIs, real Supabase store. Assertions adapt to whatever is open today,
// and every step records what it saw in the test report.
import { test, expect } from "@playwright/test";
import { clearStorage, fillProfile, openApp, saveProfileAs } from "./helpers.mjs";

test.describe.configure({ mode: "serial" });

const PROFILES = [
  { name: "서울과기대 산업공학 재학생", value: { status: "재학생", nationality: "대한민국", age: 23, school: "서울과학기술대학교", major: "산업공학", region: "서울", business: "none", entry: "individual" } },
  { name: "부산대 경영 직장인 팀", value: { status: "직장인", nationality: "대한민국", age: 35, school: "부산대학교", major: "경영학", region: "부산", business: "none", entry: "team", teamSize: 3 } },
  { name: "연세대 컴퓨터 대학원 예비창업", value: { status: "대학원생", nationality: "대한민국", age: 27, school: "연세대학교", major: "컴퓨터과학", region: "서울", business: "prospective", entry: "individual" } },
  { name: "전남대 시각디자인 휴학생", value: { status: "휴학생", nationality: "대한민국", age: 21, school: "전남대학교", major: "디자인", region: "광주", business: "none", entry: "individual" } },
];

test.beforeEach(async ({ page }) => clearStorage(page));

test("배포 서버 상태: 실호출 모드, Supabase 저장소, 공식 API 응답", async ({ request }, testInfo) => {
  const health = await (await request.get("/api/health")).json();
  expect(health.ok).toBe(true);
  expect(health.source_mode).toBe("live");
  const sources = await (await request.get("/api/sources")).json();
  await testInfo.attach("sources.json", { body: JSON.stringify({ health, sources }, null, 2), contentType: "application/json" });
  const configured = sources.sources.filter((item) => item.configured && item.type !== "reference_api");
  const ok = configured.filter((item) => item.status === "ok");
  expect(ok.length, `응답한 공식 출처: ${ok.map((item) => `${item.name}(${item.count})`).join(", ")}`).toBeGreaterThanOrEqual(2);
  for (const item of configured) expect(item.status, `${item.name}: ${item.error || ""}`).toBe("ok");
  expect(health.store.backend).toBe("supabase");
  expect(health.store.ok).toBe(true);
});

test("모든 탭 방문과 상세 화면 이동", async ({ page }) => {
  await openApp(page);
  for (const route of ["calendar", "add", "profiles", "feedback", "explore"]) {
    await page.locator(`#main-nav [data-route="${route}"]`).click();
    await expect(page.locator(`[data-view="${route}"]`)).toBeVisible();
  }
  await expect(page.getByTestId("contest-card").first()).toBeVisible();
  await page.getByTestId("card-link").first().click();
  await expect(page.getByTestId("detail-title")).toBeVisible();
});

test("여러 대학·학과 프로필로 실제 공고를 조회하고 비교한다", async ({ page }, testInfo) => {
  await openApp(page);
  const results = [];
  for (const profile of PROFILES) {
    await page.locator('#main-nav [data-route="explore"]').click();
    await page.locator("#reset-profile").click();
    await fillProfile(page, profile.value);
    const family = await page.locator('#profile-form select[name="majorFamily"]').inputValue();
    expect(family, `${profile.name} 계열 자동 입력`).not.toBe("");
    await saveProfileAs(page, profile.name);
    results.push({ profile: profile.name, family });
  }
  const rows = page.getByTestId("profile-row");
  await expect(rows).toHaveCount(PROFILES.length);
  const tallies = await rows.evaluateAll((nodes) => nodes.map((node) => [...node.querySelectorAll("td.num")].map((cell) => Number(cell.textContent))));
  await testInfo.attach("profile-tallies.json", { body: JSON.stringify({ results, tallies }, null, 2), contentType: "application/json" });
  for (const tally of tallies) expect(tally.reduce((sum, value) => sum + value, 0)).toBeGreaterThan(0);
});

test("유형·출처 필터로 실제 공고가 조회된다", async ({ page }, testInfo) => {
  await openApp(page);
  const seen = {};
  for (const option of await page.locator("#kind-filter option").evaluateAll((nodes) => nodes.map((node) => ({ value: node.value, text: node.textContent })))) {
    if (option.value === "all" || /\(0\)/.test(option.text)) continue;
    await page.locator("#kind-filter").selectOption(option.value);
    const kinds = await page.getByTestId("contest-card").evaluateAll((nodes) => nodes.map((node) => node.dataset.kind));
    expect(kinds.length, option.text).toBeGreaterThan(0);
    expect(new Set(kinds)).toEqual(new Set([option.value]));
    seen[option.value] = kinds.length;
  }
  await page.locator("#kind-filter").selectOption("all");
  for (const option of await page.locator("#source-filter option").evaluateAll((nodes) => nodes.map((node) => node.value))) {
    if (option === "all") continue;
    await page.locator("#source-filter").selectOption(option);
    const sources = await page.getByTestId("contest-card").evaluateAll((nodes) => nodes.map((node) => node.dataset.source));
    if (sources.length) expect(new Set(sources)).toEqual(new Set([option]));
    seen[`source:${option}`] = sources.length;
  }
  await testInfo.attach("filters.json", { body: JSON.stringify(seen, null, 2), contentType: "application/json" });
  expect(Object.keys(seen).length).toBeGreaterThan(2);
});

test("실제 공고 상세: 일정·제출물·원문 분석·캘린더", async ({ page, request }, testInfo) => {
  const data = await (await request.get("/api/contests?samples=0&deadline=open")).json();
  const withSchedule = data.contests.find((item) => (item.details?.schedule || []).length && (item.details?.deliverables || []).length)
    || data.contests.find((item) => (item.details?.schedule || []).length);
  expect(withSchedule, "일정이 있는 실제 공고").toBeTruthy();
  await openApp(page, `#/contest/${encodeURIComponent(withSchedule.id)}`);
  await expect(page.getByTestId("detail-title")).toContainText(withSchedule.title.slice(0, 10));
  await expect(page.getByTestId("schedule-item").first()).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByTestId("download-ics").click();
  expect((await download).suggestedFilename()).toMatch(/\.ics$/);

  // 자격 정보가 없는 공식 목록 공고 하나를 원문 분석한다 (robots.txt 허용 사이트).
  const unknown = data.contests.filter((item) => item.eligibility_known === false && item.source?.id === "seoul");
  const analyzed = [];
  for (const contest of unknown.slice(0, 3)) {
    const response = await request.post(`/api/contests/${encodeURIComponent(contest.id)}/analyze`, { data: {} });
    const body = await response.json();
    analyzed.push({ title: contest.title, status: response.status(), found: body.contest?.analysis?.eligibility_found, schedule: body.contest?.details?.schedule?.length, deliverables: body.contest?.details?.deliverables?.length, error: body.error });
    if (response.ok()) break;
  }
  await testInfo.attach("analysis.json", { body: JSON.stringify(analyzed, null, 2), contentType: "application/json" });
  if (unknown.length) expect(analyzed.some((item) => item.status === 200), JSON.stringify(analyzed)).toBe(true);
});

test("사용자가 실제 공식 URL을 입력해 공고를 추가한다", async ({ page, request }, testInfo) => {
  const data = await (await request.get("/api/contests?samples=0&source=seoul")).json();
  const target = data.contests[0];
  test.skip(!target, "서울시 목록에 접수 중인 공고가 없습니다.");
  await openApp(page, "#/add");
  await page.getByTestId("import-url").fill(target.source_url);
  await page.getByTestId("import-preview").click();
  await expect(page.getByTestId("import-message")).toContainText(/미리보기 완료|자동 열람|robots/, { timeout: 60_000 });
  const message = await page.getByTestId("import-message").textContent();
  await testInfo.attach("url-add.txt", { body: `${target.source_url}\n${message}`, contentType: "text/plain" });
  expect(message).toContain("미리보기 완료");
  await page.getByTestId("import-save").click();
  await expect(page.getByTestId("import-message")).toContainText("저장했습니다");
  await page.getByTestId("saved-link").click();
  await expect(page.getByTestId("detail-title")).toBeVisible();
});

test("일정 화면과 의견 요약이 실제 데이터로 표시된다", async ({ page }) => {
  await openApp(page, "#/calendar");
  await page.locator("#calendar-scope").selectOption("all");
  await page.locator("#calendar-range").selectOption("120");
  await expect(page.getByTestId("calendar-event").first()).toBeVisible();
  await page.locator('#main-nav [data-route="feedback"]').click();
  await expect(page.getByTestId("feedback-summary")).not.toContainText("불러오는 중");
});
