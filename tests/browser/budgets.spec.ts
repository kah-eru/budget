import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("fixed, yearly and flexible budgets feed the monthly plan", async ({ page }) => {
  test.setTimeout(90_000);  // budgets, plan, a split and a split rule in one journey
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Manage budgets" }).click();
  await page.getByRole("link", { name: /^Income/ }).click();
  await page.getByLabel("Expected monthly income (USD)").fill("5000");
  await page.getByRole("button", { name: "Save income" }).click();
  const add = async (kind: string, category: string, amount: string, due?: string) => {
    await page.getByRole("link", { name: "Add budget" }).click();
    await page.getByLabel("Type").selectOption({ label: kind });
    await page.getByLabel("Category", { exact: true }).selectOption({ label: category });
    await page.getByLabel("Limit (USD)").fill(amount);
    if (due) await page.getByLabel("Due day of the month").fill(due);
    await page.getByRole("button", { name: "Save budget" }).click();
  };
  await add("Fixed bill", "Housing", "1500", "1");
  await add("Yearly or irregular cost", "Health", "1200");
  const plan = page.getByRole("region", { name: /Monthly plan/ });
  await expect(plan).toContainText("Disposable income");
  await expect(plan).toContainText("$5,000.00");
  await expect(page.locator("main")).toContainText("Fixed bill, due on day 1");
  await expect(page.locator("main")).toContainText("set aside $100.00/month");
  await page.setViewportSize({ width: 360, height: 800 });
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await plan.screenshot({ path: `.local/plan-${scheme}.png` });
  }

  await page.emulateMedia({ colorScheme: "light" });

  // Split one purchase across two categories; the lines must add up exactly.
  const suffix = Date.now().toString();
  const accountName = "Split card " + suffix;
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill(accountName);
  await page.getByRole("button", { name: "Create private account" }).click();
  await page.getByRole("link", { name: accountName }).click();
  await page.getByRole("link", { name: "Add transaction" }).click();
  await page.getByLabel("Date").fill("2026-04-12");
  await page.getByLabel("Amount (USD)").fill("50.00");
  await page.getByLabel("Description").fill("Superstore " + suffix);
  await page.getByRole("button", { name: "Save transaction" }).click();
  await page.getByRole("link", { name: new RegExp("^Edit Superstore " + suffix) }).click();
  await page.getByRole("link", { name: "Split across categories" }).click();
  await page.getByLabel("Line 1 category").selectOption({ label: "Groceries" });
  await page.getByLabel("Line 1 amount (USD)").fill("30");
  await page.getByLabel("Line 2 category").selectOption({ label: "Shopping" });
  await page.getByLabel("Line 2 amount (USD)").fill("19.99");
  await page.getByRole("button", { name: "Save split" }).click();
  await expect(page.getByRole("alert")).toContainText("$0.01 left to split");
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  await page.screenshot({ path: ".local/split-phone.png", fullPage: true });
  await page.getByLabel("Line 2 amount (USD)").fill("20");
  await page.getByRole("button", { name: "Save split" }).click();
  await expect(page.locator("main")).toContainText("Split: Groceries $30.00, Shopping $20.00");

  // A rule with a 70/30 split template, applied to history, rounds so the lines add up exactly.
  const tag = suffix.replace(/\d/g, (d) => "abcdefghij"[Number(d)]);
  await page.getByRole("link", { name: "Add transaction" }).click();
  await page.getByLabel("Date").fill("2026-04-13");
  await page.getByLabel("Amount (USD)").fill("10.01");
  await page.getByLabel("Description").fill(`Warehouse${tag} #7`);
  await page.getByRole("button", { name: "Save transaction" }).click();
  await page.goto("/");
  await page.getByRole("link", { name: "Manage categories" }).click();
  await page.getByRole("link", { name: /^Rules/ }).click();
  await page.getByRole("link", { name: "Add rule" }).click();
  await page.getByLabel("Text").fill(`warehouse${tag}`);
  await page.getByLabel("Category", { exact: true }).selectOption({ label: "Groceries" });
  await page.getByLabel("Split with (optional)").selectOption({ label: "Shopping" });
  await page.getByLabel("Share for the second category (%)").fill("30");
  await page.getByLabel("Also apply to existing transactions").check();
  await page.getByRole("button", { name: "Save rule" }).click();
  await expect(page.getByRole("link", { name: new RegExp(`warehouse${tag}.*Groceries 70% / Shopping 30%`) })).toBeVisible();
  await page.goto("/");
  await page.getByRole("link", { name: accountName }).click();
  await expect(page.locator("li", { hasText: `Warehouse${tag} #7` })).toContainText("Split: Groceries $7.01, Shopping $3.00");
});
