import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("a bank CSV is previewed, imported, shown and undone", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const suffix = Date.now().toString();
  const accountName = "Import card " + suffix;
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill(accountName);
  await page.getByRole("button", { name: "Create private account" }).click();
  await page.getByRole("link", { name: accountName }).click();
  await page.getByRole("link", { name: "Import CSV" }).click();

  // A credit-card style file: purchases positive, a refund negative; this month so the Timeline shows it.
  const now = new Date();
  const day = `${String(now.getMonth() + 1).padStart(2, "0")}/01/${now.getFullYear()}`;
  const csv = `Date,Description,Amount\n${day},Coffee ${suffix},4.50\n${day},Refund ${suffix},-2.00\n`;
  await page.getByLabel("CSV file").setInputFiles({ name: "card.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload and preview" }).click();
  await expect(page.getByRole("heading", { name: "Check card.csv" })).toBeVisible();
  const coffee = page.locator("li", { hasText: "Coffee " + suffix });
  await expect(coffee).toContainText("+$4.50");  // a tie guesses bank style, so the owner flips it
  await page.getByLabel("In the amount column").selectOption({ label: "Money out is positive (cards)" });
  await page.getByLabel("Money in counts as").selectOption({ label: "Refund" });
  await page.getByRole("button", { name: "Update preview" }).first().click();
  await expect(coffee).not.toContainText("+");
  await expect(page.locator("li", { hasText: "Refund " + suffix })).toContainText(" · Refund");

  await page.setViewportSize({ width: 360, height: 800 });
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await page.screenshot({ path: `.local/import-${scheme}.png`, fullPage: true });
  }
  await page.emulateMedia({ colorScheme: "light" });

  await page.getByRole("button", { name: "Import 2 transactions" }).click();
  await expect(page.locator("body")).toContainText("Imported 2 from card.csv.");
  await expect(page.locator("main")).toContainText("Coffee " + suffix);
  await expect(page.getByRole("heading", { name: "Imports" })).toBeVisible();

  // Imported rows keep the bank's amount: the original entry only offers the type.
  await page.locator("summary", { hasText: "Coffee " + suffix }).first().click();  // rows open to show Edit
  await page.getByRole("link", { name: new RegExp("^Edit Coffee " + suffix) }).click();
  await page.getByRole("link", { name: "Edit type" }).click();
  await expect(page.getByLabel("Amount (USD)")).toBeDisabled();
  await page.goBack();
  await page.goBack();

  await page.getByRole("link", { name: "Timeline", exact: true }).click();
  await page.goto(page.url() + "?q=" + encodeURIComponent("Coffee " + suffix));  // the shared test user has many rows this month
  await expect(page.locator("main")).toContainText("Coffee " + suffix);
  await page.goBack();
  await page.goBack();
  await page.getByRole("button", { name: /^Undo the import of card\.csv/ }).click();
  await expect(page.locator("body")).toContainText("Removed the 2 transactions imported from card.csv.");
  await expect(page.locator("main")).not.toContainText("Coffee " + suffix);
});
