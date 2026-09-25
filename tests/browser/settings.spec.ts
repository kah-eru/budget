import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("theme choice applies, survives reload and returns to system; Timeline exports CSV", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  const root = page.locator("html");

  await page.locator("label.segment", { hasText: "Dark" }).click();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(34, 24, 28)");
  await page.screenshot({ path: ".local/settings-dark.png", fullPage: true });

  await page.locator("label.segment", { hasText: "Light" }).click();
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(255, 255, 255)");
  await page.locator("label.segment", { hasText: "System" }).click();
  await expect(root).not.toHaveAttribute("data-theme");
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 800 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.screenshot({ path: ".local/settings-light.png", fullPage: true });

  await page.getByRole("link", { name: "Timeline", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: /^Export CSV/ }).click();
  expect((await download).suggestedFilename()).toMatch(/^budget-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.csv$/);
});
