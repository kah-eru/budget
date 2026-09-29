import { type Page } from "@playwright/test";
import { test, expect } from "./turbo";

async function account(page: Page, name: string) {
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create private account" }).click();
}

async function add(page: Page, accountName: string, type: string, amount: string, description: string) {
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("link", { name: accountName }).click();
  await page.getByRole("link", { name: "Add transaction" }).click();
  await page.getByLabel("Date").fill(new Date().toISOString().slice(0, 10));
  await page.getByLabel("Amount (USD)").fill(amount);
  await page.getByLabel("Type").selectOption({ label: type });
  await page.getByLabel("Description").fill(description);
  await page.getByRole("button", { name: "Save transaction" }).click();
}

// Synthetic data on the disposable local database only.
test("Timeline side by side joins a transfer across two accounts and the lines turn off", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const suffix = Date.now().toString();
  const checking = "Checking " + suffix, savings = "Savings " + suffix;
  await account(page, checking);
  await account(page, savings);
  await add(page, checking, "Transfer out or card payment", "250.00", "To savings " + suffix);
  await add(page, savings, "Transfer in", "250.00", "From checking " + suffix);
  await add(page, checking, "Transfer out or card payment", "40.00", "Venmo " + suffix);
  await add(page, checking, "Expense", "4.50", "Coffee " + suffix);

  await page.getByRole("link", { name: "Timeline", exact: true }).click();
  await page.getByRole("button", { name: /^Filters/ }).click();
  await page.getByRole("button", { name: "Select all" }).click();
  await expect(page.getByRole("checkbox", { name: savings })).toBeChecked();
  await expect(page.locator("[data-account-count]")).not.toHaveText("All");
  await page.getByRole("button", { name: "Clear all" }).click();
  await expect(page.getByRole("checkbox", { name: savings })).not.toBeChecked();
  await page.getByRole("checkbox", { name: checking }).check();
  await page.getByRole("checkbox", { name: savings }).check();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.screenshot({ path: ".local/filters-phone.png" });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.locator("main")).toContainText("2 of");
  await expect(page.getByRole("button", { name: "Filters, on" })).toBeVisible();  // the icon shows a dot while filters apply
  await page.getByRole("link", { name: "List", exact: true }).click();

  const lanes = page.getByRole("region", { name: "Transactions by account" });
  await expect(lanes.locator(".lane-head")).toHaveCount(2);
  await expect(lanes).toContainText("To " + savings);
  await expect(lanes).toContainText("From " + checking);
  await expect(lanes).toContainText("To elsewhere");
  await expect(lanes.locator("svg.flows path.flow")).toHaveCount(1);
  await expect(lanes.locator("svg.flows path.is-stub")).toHaveCount(1);

  await page.setViewportSize({ width: 360, height: 800 });
  await expect.poll(() => lanes.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);  // lanes scroll sideways inside their box
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await page.screenshot({ path: `.local/lanes-${scheme}.png`, fullPage: true });
  }
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: ".local/lanes-desktop.png", fullPage: true });

  // The lines turn off from Filters, stay off after a reload on this device, and turn back on.
  await page.getByRole("button", { name: /^Filters/ }).click();
  await page.getByLabel("Show money moving").uncheck();
  await expect(lanes.locator("svg.flows")).toHaveClass(/is-off/);
  await page.reload();
  await page.getByRole("button", { name: /^Filters/ }).click();
  await expect(page.getByLabel("Show money moving")).not.toBeChecked();
  await page.getByLabel("Show money moving").check();
  await expect(lanes.locator("svg.flows")).not.toHaveClass(/is-off/);
});
