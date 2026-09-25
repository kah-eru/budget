import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("fixed, yearly and flexible budgets feed the monthly plan", async ({ page }) => {
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
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished)));
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await plan.screenshot({ path: `.local/plan-${scheme}.png` });
  }
});
