// Mobile viewport: every tab fits the screen and the main flow works with touch-sized controls.
import { test, expect } from "@playwright/test";
import { card, clearStorage, fillProfile, openApp } from "./helpers.mjs";

test.beforeEach(async ({ page }) => clearStorage(page));

test("모바일에서 모든 탭이 가로 스크롤 없이 보인다", async ({ page }) => {
  await openApp(page);
  for (const route of ["explore", "calendar", "add", "profiles", "feedback"]) {
    await page.goto(`/#/${route}`);
    await expect(page.locator(`[data-view="${route}"]`)).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${route} 화면 가로 넘침`).toBeLessThanOrEqual(1);
  }
  await page.goto("/#/explore");
  await page.getByTestId("card-link").first().click();
  await expect(page.getByTestId("detail-title")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
});

test("모바일에서 프로필 입력 후 상세 화면까지 이동한다", async ({ page }) => {
  await openApp(page);
  await fillProfile(page, { status: "재학생", age: 22, school: "서울과학기술대학교", major: "산업공학", region: "서울", business: "none", entry: "individual" });
  const target = card(page, "대학생 창업 아이디어 경진대회");
  await expect(target).toHaveAttribute("data-result", "eligible");
  await target.getByTestId("open-detail").click();
  await expect(page.getByTestId("schedule-timeline")).toBeVisible();
});
