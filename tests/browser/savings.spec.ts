import { type Page } from "@playwright/test";
import { test, expect } from "./turbo";

async function add(page: Page, accountName: string, type: string, amount: string, description: string) {
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("link", { name: accountName }).first().click();
  await page.getByRole("link", { name: "Add transaction" }).click();
  await page.getByLabel("Date").fill(new Date().toISOString().slice(0, 10));
  await page.getByLabel("Amount (USD)").fill(amount);
  await page.getByLabel("Type").selectOption({ label: type });
  await page.getByLabel("Description").fill(description);
  await page.getByRole("button", { name: "Save transaction" }).click();
}

// Synthetic data on the disposable local database only.
test("a savings account shows on Overview and the Savings page with its net saved", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const name = "Rainy day " + Date.now();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Counts in net worth as").selectOption({ label: "Something you own" });
  await page.getByLabel("Current value (USD)").fill("2000");
  await page.getByLabel("Savings account").check();
  await page.getByRole("button", { name: "Create private account" }).click();
  await add(page, name, "Transfer in", "500.00", "From checking");
  await add(page, name, "Transfer out or card payment", "200.00", "To checking");

  await page.setViewportSize({ width: 360, height: 800 });  // before the chart mounts, so it isn't caught redrawing
  // The header's switch flips Overview to Savings in place, and the choice is remembered on this device.
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("link", { name: "Invite someone to Budget" })).toBeVisible();  // in the header now
  await page.locator("label.segment", { hasText: "Savings" }).click();
  const savingsMode = page.locator('[data-mode="savings"]').first();
  await expect(savingsMode).toBeVisible();
  await expect(savingsMode).toContainText("saved");
  await expect(page.locator('[data-mode="spending"]').first()).toBeHidden();
  // The same mode on the Timeline: only savings accounts, with money in, out and net saved.
  await page.getByRole("link", { name: "Timeline", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Savings", exact: true })).toBeVisible();
  await expect(page.locator("main")).toContainText("From checking");
  await expect(page.getByRole("img", { name: /^Net saved so far/ }).locator("svg").first()).toBeVisible();
  await page.waitForTimeout(1000);
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.waitForTimeout(300);  // buttons ease their background between themes
    await page.screenshot({ path: `.local/timeline-savings-${scheme}.png` });
  }
  await page.emulateMedia({ colorScheme: "light" });
  await page.locator("label.segment", { hasText: "Spending" }).click();
  await expect(page.getByRole("heading", { name: "Spending", exact: true })).toBeVisible();
  await page.locator("label.segment", { hasText: "Savings" }).click();
  await expect(page.getByRole("heading", { name: "Savings", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /^Workspace:/ }).click();
  await expect(page.getByRole("navigation", { name: "Workspaces" })).toBeVisible();
  await page.waitForTimeout(300);
  await page.screenshot({ path: ".local/workspace-menu-phone.png" });
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(1000);  // the chart redraws for the new width
  await page.screenshot({ path: ".local/header-desktop.png" });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.reload();
  await expect(savingsMode).toBeVisible();
  await expect(page.locator('[data-mode="savings"] [data-spending-chart] svg').first()).toBeVisible();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: ".local/overview-savings.png" });
  await page.getByRole("link", { name: "Savings accounts and details" }).click();
  await expect(page.getByRole("heading", { name: "Savings", exact: true })).toBeVisible();
  const row = page.locator("li", { hasText: name });
  await expect(row).toContainText("$2,000.00");
  await expect(row).toContainText("+$300.00");
  await expect(page.locator("[data-spending-chart] svg").first()).toBeVisible();
  await page.waitForTimeout(1000);  // the chart's draw-in is JS-driven, not a Web Animation
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await page.screenshot({ path: `.local/savings-${scheme}.png` });
  }
  await page.emulateMedia({ colorScheme: "light" });
  await page.getByRole("link", { name: "View savings transactions" }).click();
  await expect(page.getByRole("region", { name: "Transactions by account" })).toContainText(name);
});
