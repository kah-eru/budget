import { test, expect, type Page } from "@playwright/test";

const settle = (page: Page) => page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));

async function shots(page: Page, name: string) {
  await page.setViewportSize({ width: 360, height: 800 });
  await settle(page);
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await page.screenshot({ path: `.local/${name}-${scheme}.png`, fullPage: true });
  }
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 1280, height: 800 });
}

// Synthetic data on the disposable local database only.
test("net worth, a recurring bill with its reminder, and an optional goal", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const suffix = Date.now().toString();

  // Net worth: something you own, typed in by hand.
  await page.goto("/accounts/new/?kind=asset");
  await page.getByLabel("Name", { exact: true }).fill("Home " + suffix);
  await page.getByLabel("Current value (USD)").fill("400000");
  await page.getByRole("button", { name: "Create private account" }).click();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("link", { name: /^Net worth/ }).click();
  await expect(page.locator("main")).toContainText("Home " + suffix);
  await shots(page, "networth");

  // A bill due in two days: the forecast lists it and Alerts reminds.
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("link", { name: "Manage budgets" }).click();
  await page.getByRole("link", { name: "Bills, income and the 30-day forecast" }).click();
  await page.getByRole("link", { name: "Add a bill or income" }).click();
  const due = new Date(Date.now() + 2 * 86_400_000).toISOString().slice(0, 10);
  await page.getByLabel("Name", { exact: true }).fill("Rent " + suffix);
  await page.getByLabel("Usual amount (USD)").fill("1500");
  await page.getByLabel("Next due date").fill(due);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("region", { name: /Next 30 days/ })).toContainText("Rent " + suffix);
  await shots(page, "bills");
  await page.getByRole("link", { name: /alerts/i }).first().click();
  await expect(page.locator("main")).toContainText("Rent " + suffix);

  // Goals stay hidden until turned on.
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Turn on goals" }).click();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("link", { name: "Manage budgets" }).click();
  await page.getByRole("link", { name: "All goals" }).click();
  await page.getByRole("link", { name: "Add a goal" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Trip " + suffix);
  await page.getByLabel("Target (USD)").fill("1000");
  await page.getByLabel("Saved or paid so far (USD)").fill("250");
  await page.getByRole("button", { name: "Save goal" }).click();
  await page.getByRole("link", { name: "Budgets" }).first().click();
  await expect(page.getByRole("region", { name: "Goals" })).toContainText("25%");
  await shots(page, "goals");
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Turn off goals" }).click();  // leave the shared test user as it was
});
