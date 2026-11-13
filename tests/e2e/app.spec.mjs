// Fixture-mode E2E: recorded official API payloads, real Python service, real browser.
import { test, expect } from "@playwright/test";
import { card, clearStorage, counts, fillProfile, openApp, saveProfileAs } from "./helpers.mjs";

const SEOUL_TECH_IE = { status: "재학생", nationality: "대한민국", age: 23, school: "서울과학기술대학교", major: "산업공학", family: "공학", region: "서울", business: "none", entry: "individual" };
const PUSAN_BUSINESS = { status: "직장인", nationality: "대한민국", age: 35, school: "부산대학교", major: "경영학", family: "인문사회", region: "부산", business: "none", entry: "team", teamSize: 3 };
const YONSEI_CS_GRAD = { status: "대학원생", nationality: "대한민국", age: 27, school: "연세대학교", major: "컴퓨터과학", family: "공학", region: "서울", business: "prospective", entry: "individual" };

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await clearStorage(page);
});

test("모든 탭을 방문하고 각 화면의 핵심 요소가 보인다", async ({ page }) => {
  await openApp(page);
  const routes = [
    ["explore", "판정 결과"], ["calendar", "다가오는 일정"], ["add", "공식 공고 URL로 추가하기"],
    ["profiles", "저장한 프로필 비교"], ["feedback", "사용 후 짧은 의견"],
  ];
  for (const [route, heading] of routes) {
    await page.locator(`#main-nav [data-route="${route}"]`).click();
    await expect(page).toHaveURL(new RegExp(`#/${route}$`));
    await expect(page.locator(`[data-view="${route}"]`)).toBeVisible();
    await expect(page.locator(`[data-view="${route}"]`).getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.locator(`#main-nav [data-route="${route}"]`)).toHaveAttribute("aria-current", "page");
  }
  await page.locator('#main-nav [data-route="explore"]').click();
  await page.getByTestId("card-link").first().click();
  await expect(page).toHaveURL(/#\/contest\//);
  await expect(page.getByTestId("detail-title")).toBeVisible();
  await page.getByTestId("back-to-list").click();
  await expect(page.locator('[data-view="explore"]')).toBeVisible();
});

test("공식 API 7개 출처가 모두 응답하고 실제 공고가 기본으로 표시된다", async ({ page }) => {
  await openApp(page);
  for (const source of ["kstartup", "kocca", "seoul", "kctf", "codeforces", "kaggle", "work24"]) {
    await expect(page.getByTestId(`source-chip-${source}`)).toContainText(/\d+건/);
  }
  await expect(page.locator("#data-filter")).toHaveValue("real");
  const cards = page.getByTestId("contest-card");
  await expect(cards).toHaveCount(14);
  await expect(page.getByTestId("hero-total")).toContainText("공식 출처 14건");
  // 마감된 공고(픽스처의 마감 항목)는 공식 API 정규화 단계에서 제외된다.
  await expect(card(page, "이미 마감된 창업 공고")).toHaveCount(0);
  await expect(card(page, "마감된 CTF")).toHaveCount(0);
});

test("여러 대학·학과 프로필을 저장하면 같은 공고의 판정이 달라진다", async ({ page }) => {
  await openApp(page);
  await fillProfile(page, SEOUL_TECH_IE);
  const startup = card(page, "대학생 창업 아이디어 경진대회");
  await expect(startup).toHaveAttribute("data-result", "eligible");
  const seoulTechCounts = await counts(page);
  await saveProfileAs(page, "서울과기대 산업공학");

  await page.locator('#main-nav [data-route="explore"]').click();
  await page.locator("#reset-profile").click();
  await fillProfile(page, PUSAN_BUSINESS);
  await expect(startup).toHaveAttribute("data-result", "ineligible");
  await expect(startup.locator(".reason-line")).toContainText("신분");
  const pusanCounts = await counts(page);
  expect(pusanCounts).not.toEqual(seoulTechCounts);
  await saveProfileAs(page, "부산대 경영 직장인");

  await page.locator('#main-nav [data-route="explore"]').click();
  await page.locator("#reset-profile").click();
  await fillProfile(page, YONSEI_CS_GRAD);
  await expect(card(page, "청년 예비창업 패키지")).toHaveAttribute("data-result", "needs_review");
  await saveProfileAs(page, "연세대 컴퓨터 대학원");

  const rows = page.getByTestId("profile-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("서울과학기술대학교");
  await expect(rows.nth(0)).toContainText("공학계열");
  await expect(rows.nth(1)).toContainText("부산대학교");
  await expect(rows.nth(1)).toContainText("인문사회계열");
  await expect(rows.nth(2)).toContainText("연세대학교");
  const tallies = await rows.evaluateAll((nodes) => nodes.map((node) => [...node.querySelectorAll("td.num")].map((cell) => cell.textContent.trim()).join("/")));
  expect(new Set(tallies).size, `프로필별 판정 분포 ${tallies.join(" | ")}`).toBeGreaterThan(1);

  // 저장한 프로필을 적용하면 탐색 화면의 판정이 그 조건으로 바뀐다.
  await rows.nth(0).getByTestId("profile-apply").click();
  await page.locator('#main-nav [data-route="explore"]').click();
  await expect(page.getByTestId("active-profile")).toContainText("서울과기대 산업공학");
  await expect(startup).toHaveAttribute("data-result", "eligible");
  // 새로고침 후에도 프로필이 유지된다.
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator('#profile-form input[name="school"]')).toHaveValue("서울과학기술대학교");
});

test("유형·출처·접수 상태·검색·정렬 옵션으로 실제 공고를 조회한다", async ({ page }) => {
  await openApp(page);
  await page.locator("#kind-filter").selectOption("internship");
  await expect(page.getByTestId("contest-card")).toHaveCount(2);
  for (const kind of await page.getByTestId("contest-card").evaluateAll((nodes) => nodes.map((node) => node.dataset.kind))) expect(kind).toBe("internship");

  await page.locator("#kind-filter").selectOption("all");
  await page.locator("#source-filter").selectOption("kstartup");
  await expect(page.getByTestId("contest-card")).toHaveCount(3);
  await page.locator("#source-filter").selectOption("all");

  await page.getByTestId("source-chip-codeforces").click();
  await expect(page.getByTestId("contest-card")).toHaveCount(2);
  await page.getByTestId("source-chip-codeforces").click();

  await page.locator("#contest-search").fill("Kaggle");
  await expect(page.getByTestId("contest-card")).toHaveCount(2);
  await page.locator("#contest-search").fill("");

  await page.locator("#deadline-filter").selectOption("open");
  await page.locator("#sort-filter").selectOption("deadline");
  const deadlines = await page.locator(".contest-card .date-label").allTextContents();
  const dates = deadlines.map((text) => text.match(/\d{4}-\d{2}-\d{2}/)?.[0]).filter(Boolean);
  expect(dates).toEqual([...dates].sort());

  await page.locator("#data-filter").selectOption("sample");
  await expect(page.getByTestId("contest-card").first()).toContainText("샘플 데이터");
  await page.getByTestId("tab-ineligible").click();
  await page.locator("#contest-search").fill("존재하지않는공고");
  await expect(page.getByTestId("empty-state")).toBeVisible();
  await page.locator("#reset-filters").click();
  await expect(page.locator("#contest-search")).toHaveValue("");
});

test("공고 상세에서 일정·제출물·접수 방법·근거를 확인하고 체크리스트와 캘린더를 쓴다", async ({ page }) => {
  await openApp(page);
  await fillProfile(page, SEOUL_TECH_IE);
  await card(page, "콘텐츠 스토리 공모전").getByTestId("open-detail").click();
  await expect(page.getByTestId("detail-title")).toContainText("콘텐츠 스토리 공모전");
  const schedule = page.getByTestId("schedule-item");
  await expect(schedule).toHaveCount(4);
  await expect(page.getByTestId("schedule-timeline")).toContainText("결과 발표");
  await expect(page.getByTestId("schedule-timeline")).toContainText("시상식");
  const deliverables = page.getByTestId("deliverable-check");
  await expect(deliverables).toHaveCount(2);
  await expect(page.getByTestId("deliverables")).toContainText("스토리 기획안");
  await expect(page.getByTestId("apply-method")).toContainText("온라인 접수");
  await expect(page.getByTestId("detail-facts")).toContainText("3,000만 원");
  await expect(page.getByTestId("evidence-list")).toContainText("만 19세 이상");
  await expect(page.getByTestId("detail-compare")).toContainText("현재 입력");

  await deliverables.first().check();
  await expect(page.getByTestId("checklist-progress")).toHaveText("1 / 2 준비 완료");
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.getByTestId("checklist-progress")).toHaveText("1 / 2 준비 완료");

  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("download-ics").click();
  const download = await downloadPromise;
  const ics = await (await download.createReadStream()).toArray().then((chunks) => Buffer.concat(chunks).toString("utf8"));
  expect(ics).toContain("BEGIN:VCALENDAR");
  expect((ics.match(/BEGIN:VEVENT/g) || []).length).toBe(4);
  expect(ics).toContain("콘텐츠 스토리 공모전");
});

test("자격 정보가 없는 공식 목록 공고는 원문 분석 후 자격·일정·제출물이 채워진다", async ({ page }) => {
  await openApp(page);
  await fillProfile(page, SEOUL_TECH_IE);
  const seoul = card(page, "서울 청년 정책 아이디어 공모전");
  await expect(seoul).toHaveAttribute("data-result", "needs_review");
  await seoul.getByTestId("open-detail").click();
  await expect(page.getByTestId("detail-result")).toHaveText("확인 필요");
  await page.getByTestId("analyze-contest").click();
  await expect(page.getByTestId("analyze-message")).toContainText("자격 발견", { timeout: 20_000 });
  await expect(page.getByTestId("detail-result")).toHaveText("지원 가능");
  await expect(page.getByTestId("schedule-item")).toHaveCount(4);
  await expect(page.getByTestId("deliverables")).toContainText("정책 제안서");
  await expect(page.getByTestId("evidence-list")).toContainText("서울시에 거주하는");
  // 분석 결과는 서버 저장소에 캐시되어 목록과 다른 프로필 판정에도 반영된다.
  await page.getByTestId("back-to-list").click();
  await expect(seoul).toHaveAttribute("data-result", "eligible");
  await page.locator("#reset-profile").click();
  await fillProfile(page, PUSAN_BUSINESS);
  await expect(seoul).toHaveAttribute("data-result", "ineligible");
});

test("사용자가 공식 URL을 입력해 공고를 추가하고 목록·상세·일정에서 확인한다", async ({ page }) => {
  await openApp(page, "#/add");
  await page.getByTestId("import-url").fill("https://contest.example.org/2026/ai-idea");
  await page.getByTestId("import-preview").click();
  await expect(page.getByTestId("import-message")).toContainText("미리보기 완료");
  await expect(page.getByTestId("import-result")).toContainText("AI 서비스 아이디어 공모전");
  await expect(page.getByTestId("import-result").getByTestId("schedule-item")).toHaveCount(2);
  await page.getByTestId("import-save").click();
  await expect(page.getByTestId("import-message")).toContainText("저장했습니다");
  await page.getByTestId("saved-link").click();
  await expect(page.getByTestId("detail-title")).toContainText("AI 서비스 아이디어 공모전");
  await expect(page.getByTestId("contest-detail").getByTestId("deliverables")).toContainText("아이디어 기획서");

  // 다른 사용자(새 브라우저 상태)도 저장된 공고를 본다.
  await page.evaluate(() => localStorage.clear());
  await openApp(page, "#/explore");
  await page.locator("#source-filter").selectOption("user");
  await expect(card(page, "AI 서비스 아이디어 공모전")).toContainText("사용자 추가 · 검수 전");

  // 붙여넣은 원문만으로도 추가할 수 있다 (자동 열람이 막힌 공고).
  await page.locator('#main-nav [data-route="add"]').click();
  await page.getByTestId("import-url").fill("https://blocked.example.org/notice/77");
  await page.getByTestId("import-text").fill("(테스트) 지역 상생 캠페인 공모전\n응모자격: 만 14세 이상 누구나\n접수기간: 2026.11.20 ~ 2026.12.31\n제출서류\n- 캠페인 포스터 (JPG)");
  await page.getByTestId("import-preview").click();
  await expect(page.getByTestId("import-message")).toContainText("미리보기 완료");
  await page.getByTestId("import-save").click();
  await expect(page.getByTestId("import-message")).toContainText("저장했습니다");

  await page.locator('#main-nav [data-route="calendar"]').click();
  await page.locator("#calendar-scope").selectOption("all");
  await page.locator("#calendar-range").selectOption("120");
  await expect(page.getByTestId("calendar-event").filter({ hasText: "AI 서비스 아이디어 공모전" }).first()).toBeVisible();
});

test("모음 사이트나 로컬 주소는 공고 추가에서 거부된다", async ({ page }) => {
  await openApp(page, "#/add");
  for (const url of ["https://linkareer.com/activity/1", "https://localhost/contest"]) {
    await page.getByTestId("import-url").fill(url);
    await page.getByTestId("import-preview").click();
    await expect(page.getByTestId("import-message")).toContainText(/모음 사이트|공개된 공식 사이트/);
  }
});

test("일정 화면은 판정 범위와 일정 종류로 걸러진다", async ({ page }) => {
  await openApp(page);
  await fillProfile(page, SEOUL_TECH_IE);
  await page.locator('#main-nav [data-route="calendar"]').click();
  await page.locator("#calendar-range").selectOption("120");
  await expect(page.getByTestId("calendar-day").first()).toBeVisible();
  await page.locator("#calendar-type").selectOption("award");
  for (const text of await page.getByTestId("calendar-event").allTextContents()) expect(text).toContain("시상식");
  await page.locator("#calendar-type").selectOption("all");
  await page.locator("#calendar-scope").selectOption("eligible");
  for (const text of await page.getByTestId("calendar-event").allTextContents()) expect(text).toContain("지원 가능");
});

test("익명 의견을 제출하면 응답 요약이 갱신된다", async ({ page }) => {
  await openApp(page, "#/feedback");
  const form = page.locator("#feedback-form");
  await form.locator('select[name="task_completed"]').selectOption("yes");
  await form.locator('select[name="reason_clear"]').selectOption("yes");
  await form.locator('select[name="ease"]').selectOption("4");
  await page.getByTestId("feedback-submit").click();
  await expect(page.getByTestId("feedback-message")).toContainText("저장했습니다");
  await expect(page.getByTestId("feedback-summary")).toContainText("응답 수");
  await expect(page.getByTestId("feedback-summary")).toContainText("4 / 5");
});
