import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("search transactions, edit from a filtered list and return to it; year view reflows", async ({ page }) => {
  test.setTimeout(60_000);  // the reused preview database grows with every run
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
  // The Timeline tab keeps the month chosen on Overview.
  await page.getByRole("link", { name: "Timeline", exact: true }).click();
  await expect(page).toHaveURL(/start=2026-03-01&end=2026-03-31/);
  await expect(page.locator("main")).toContainText("3/26");  // the chart's period label
  await page.getByRole("button", { name: /^Filters/ }).click();
  await page.getByLabel("Search").fill("coffee " + suffix);
  await page.getByRole("button", { name: "Apply filters" }).click();
  const filtered = page.url();
  await expect(page.locator("main")).toContainText("Coffee " + suffix);
  await expect(page.locator("main")).not.toContainText("Hardware " + suffix);
  // Each day starts with a line carrying its signed net; money out rows show a minus.
  await expect(page.locator(".day-line").first()).toBeVisible();
  await expect(page.locator("summary", { hasText: "Coffee " + suffix }).first()).toContainText("−$");
  // "Go to" a day on this page scrolls there without leaving the page.
  const day = await page.locator("[data-day]").first().getAttribute("data-day");
  await page.locator("#jump-day").fill(day!);
  await expect(page).toHaveURL(filtered);
  await expect(page.locator(`#day-${day}`)).toBeInViewport();
  const chart = page.getByRole("img", { name: /^Running posted spending/ });
  // The skeleton holds the chart's space, so mounting must not change the page height below it.
  await expect(chart.locator("svg:not(.chart-skeleton)").first()).toBeVisible();
  await expect(chart.locator(".chart-skeleton")).toHaveCount(0);
  await page.locator("summary", { hasText: "Coffee " + suffix }).first().click();  // rows open to show Edit
  await page.getByRole("link", { name: new RegExp("^Edit Coffee " + suffix) }).click();
  await page.getByLabel("Display name").fill("Morning coffee " + suffix);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page).toHaveURL(filtered);
  await expect(page.locator("main")).toContainText("Morning coffee " + suffix);
  // The chart re-measures shortly after a resize, so poll instead of reading once.
  for (const width of [320, 360, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.setViewportSize({ width: 360, height: 800 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  await page.screenshot({ path: ".local/transactions-phone.png", fullPage: true });
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("link", { name: "1Y", exact: true }).click();
  await expect(page.getByRole("heading", { name: "2026", exact: true })).toBeVisible();
  for (const width of [320, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.screenshot({ path: ".local/year-phone.png", fullPage: true });
});
