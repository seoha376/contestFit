import { expect } from "@playwright/test";

export async function openApp(page, hash = "#/explore") {
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
  await page.goto(`/${hash}`);
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60_000 });
}

export async function clearStorage(page) {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("cf-e2e-cleared")) {
      localStorage.clear();
      sessionStorage.setItem("cf-e2e-cleared", "1");
    }
  });
}

/** Fill the profile through the real UI: school and department come from the official catalog API. */
export async function fillProfile(page, profile) {
  const form = page.locator("#profile-form");
  if (profile.status) await form.locator('select[name="status"]').selectOption(profile.status);
  if (profile.nationality) await form.locator('select[name="nationality"]').selectOption(profile.nationality);
  if (profile.age !== undefined) await form.locator('input[name="age"]').fill(String(profile.age));
  if (profile.school) {
    await form.locator('input[name="school"]').fill(profile.school);
    const choice = page.locator("[data-school-choice]").filter({ hasText: profile.school }).first();
    await expect(choice).toBeVisible();
    await choice.click();
  }
  if (profile.major) {
    await form.locator('input[name="affiliation"]').fill(profile.major);
    const suggestion = page.locator("#department-results [data-major]").filter({ hasText: profile.school || profile.major }).first();
    await expect(suggestion).toBeVisible();
    await suggestion.click();
  }
  if (profile.family) await expect(form.locator('select[name="majorFamily"]')).toHaveValue(profile.family);
  if (profile.region) await form.locator('select[name="region"]').selectOption(profile.region);
  if (profile.business) await form.locator('select[name="businessStatus"]').selectOption(profile.business);
  if (profile.entry) await form.locator('select[name="entryType"]').selectOption(profile.entry);
  if (profile.teamSize) await form.locator('input[name="teamSize"]').fill(String(profile.teamSize));
}

export async function saveProfileAs(page, name) {
  await page.locator('#main-nav [data-route="profiles"]').click();
  await page.getByTestId("profile-name").fill(name);
  await page.getByTestId("profile-save").click();
  await expect(page.locator("#profile-message")).toContainText(name);
}

export function card(page, title) {
  return page.getByTestId("contest-list").getByTestId("contest-card").filter({ hasText: title });
}

export async function counts(page) {
  const read = async (id) => Number((await page.getByTestId(`count-${id}`).locator("strong").textContent()).trim());
  return { eligible: await read("eligible"), needs_review: await read("needs_review"), ineligible: await read("ineligible") };
}
