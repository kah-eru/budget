import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("search transactions, edit from a filtered list and return to it; year view reflows", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const suffix = Date.now().toString();
  const accountName = "Synthetic card " + suffix;
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill(accountName);
  await page.getByRole("button", { name: "Create private account" }).click();
  for (const [description, amount] of [["Coffee " + suffix, "4.50"], ["Hardware " + suffix, "90.00"]]) {
    await page.getByRole("link", { name: accountName }).click();
    await page.getByRole("link", { name: "Add transaction" }).click();
    await page.getByLabel("Date").fill("2026-03-02");
    await page.getByLabel("Amount (USD)").fill(amount);
    await page.getByLabel("Description").fill(description);
    await page.getByRole("button", { name: "Save transaction" }).click();
    await page.getByRole("link", { name: /^Back to / }).click();
  }
  await page.goto(page.url() + "?period=2026-03");
  await page.getByRole("link", { name: "View March 2026 timeline" }).click();
  await page.getByLabel("Search").fill("coffee " + suffix);
  await page.getByRole("button", { name: "Apply filters" }).click();
  const filtered = page.url();
  await expect(page.locator("main")).toContainText("Coffee " + suffix);
  await expect(page.locator("main")).not.toContainText("Hardware " + suffix);
  const chart = page.getByRole("img", { name: /^Running posted spending/ });
  // The skeleton holds the chart's space, so mounting must not change the page height below it.
  await expect(chart.locator("svg:not(.chart-skeleton)").first()).toBeVisible();
  await expect(chart.locator(".chart-skeleton")).toHaveCount(0);
  await page.getByRole("link", { name: new RegExp("^Edit Coffee " + suffix) }).click();
  await page.getByLabel("Display name").fill("Morning coffee " + suffix);
  await page.getByRole("button", { name: "Save changes" }).click();
  expect(page.url()).toBe(filtered);
  await expect(page.locator("main")).toContainText("Morning coffee " + suffix);
  // The chart re-measures shortly after a resize, so poll instead of reading once.
  for (const width of [320, 360, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.setViewportSize({ width: 360, height: 800 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  await page.screenshot({ path: ".local/transactions-phone.png", fullPage: true });
  await page.getByRole("link", { name: /^Back to / }).click();
  await page.getByRole("link", { name: "Year", exact: true }).click();
  await expect(page.getByRole("heading", { name: "2026", exact: true })).toBeVisible();
  for (const width of [320, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.screenshot({ path: ".local/year-phone.png", fullPage: true });
});
