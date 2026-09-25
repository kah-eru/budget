import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("categorize a transaction, see it by category on Overview, filter the timeline, add a category", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const suffix = Date.now().toString();
  const accountName = "Category card " + suffix;
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill(accountName);
  await page.getByRole("button", { name: "Create private account" }).click();
  await page.getByRole("link", { name: accountName }).click();
  await page.getByRole("link", { name: "Add transaction" }).click();
  await page.getByLabel("Date").fill("2026-04-03");
  await page.getByLabel("Amount (USD)").fill("62.10");
  await page.getByLabel("Description").fill("Market " + suffix);
  await page.getByRole("button", { name: "Save transaction" }).click();
  await page.getByRole("link", { name: new RegExp("^Edit Market " + suffix) }).click();
  await page.getByLabel("Category").selectOption({ label: "Groceries" });
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator("main")).toContainText("Groceries");

  await page.getByRole("link", { name: /^Back to / }).click();
  await page.goto(page.url().split("?")[0] + "?period=2026-04");
  const section = page.getByRole("region", { name: "By category" });
  await expect(section.getByRole("link", { name: /^Groceries/ })).toBeVisible();
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.setViewportSize({ width: 360, height: 800 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await section.screenshot({ path: `.local/categories-${scheme}.png` });
  }
  await section.getByRole("link", { name: /^Groceries/ }).click();
  await expect(page.getByLabel("Category")).toHaveValue(/\d+/);
  await expect(page.locator("main")).toContainText("Market " + suffix);

  await page.goBack();
  await page.getByRole("link", { name: "Manage categories" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Pets " + suffix);
  await page.getByRole("button", { name: "Add category" }).click();
  await expect(page.getByRole("link", { name: "Pets " + suffix })).toBeVisible();
});
