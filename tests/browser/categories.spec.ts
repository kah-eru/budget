import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("categorize a transaction, see it by category on Overview, filter the timeline, add a category", async ({ page }) => {
  test.setTimeout(90_000);  // one long journey: categories, rules, budgets, alerts, categorize by example
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
  await page.getByLabel("Category", { exact: true }).selectOption({ label: "Groceries" });
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
  await expect(page.getByLabel("Category", { exact: true })).toHaveValue(/\d+/);
  await expect(page.locator("main")).toContainText("Market " + suffix);

  await page.goBack();
  await page.getByRole("link", { name: "Manage categories" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Pets " + suffix);
  await page.getByRole("button", { name: "Add category" }).click();
  await expect(page.getByRole("link", { name: "Pets " + suffix })).toBeVisible();

  // A rule previews its matches; applying it to history keeps the hand-picked Groceries.
  await page.getByRole("link", { name: /^Rules/ }).click();
  await page.getByRole("link", { name: "Add rule" }).click();
  await page.getByLabel("Text").fill("market " + suffix);
  await page.getByLabel("Category", { exact: true }).selectOption({ label: "Pets " + suffix });
  await page.getByRole("button", { name: "Preview matches" }).click();
  await expect(page.getByRole("status")).toContainText("1 transaction matches");
  await expect(page.getByRole("status")).toContainText("Market " + suffix);
  await page.setViewportSize({ width: 360, height: 800 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished)));  // let the page crossfade end
  await page.screenshot({ path: ".local/rule-preview-phone.png", fullPage: true });
  await page.getByLabel("Also apply to existing transactions").check();
  await page.getByRole("button", { name: "Save rule" }).click();
  await expect(page.locator("body")).toContainText("0 existing transactions updated");
  await expect(page.getByRole("link", { name: new RegExp("Name contains “market " + suffix) })).toBeVisible();

  // A name-match budget below the April spend shows as over on Overview.
  await page.goto("/");
  await page.goto(page.url().split("?")[0] + "?period=2026-04");
  await page.getByRole("link", { name: "Manage budgets" }).click();
  await page.getByRole("link", { name: "Add budget" }).click();
  await page.getByLabel("Or a name containing").fill("market " + suffix);
  await page.getByLabel("Limit (USD)").fill("50");
  await page.getByRole("button", { name: "Save budget" }).click();
  await page.goto("/");
  await page.goto(page.url().split("?")[0] + "?period=2026-04");
  const budgets = page.getByRole("region", { name: "Budgets" });
  await expect(budgets.getByRole("link", { name: new RegExp("market " + suffix) })).toContainText("$12.10 over");
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await budgets.getByRole("link", { name: new RegExp("market " + suffix) }).screenshot({ path: `.local/budget-${scheme}.png` });
  }

  // A $5 budget this month, then a $6 purchase today: one alert in the header and the inbox.
  await page.emulateMedia({ colorScheme: "light" });
  await page.getByRole("link", { name: "Manage budgets" }).click();
  await page.getByRole("link", { name: "Add budget" }).click();
  await page.getByLabel("Or a name containing").fill("alert " + suffix);
  await page.getByLabel("Limit (USD)").fill("5");
  await page.getByRole("button", { name: "Save budget" }).click();
  await page.goto("/");
  await page.getByRole("link", { name: accountName }).click();
  await page.getByRole("link", { name: "Add transaction" }).click();
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  await page.getByLabel("Date").fill(today);
  await page.getByLabel("Amount (USD)").fill("6.00");
  await page.getByLabel("Description").fill("Alert " + suffix);
  await page.getByRole("button", { name: "Save transaction" }).click();
  await page.getByRole("link", { name: /new alert/ }).click();
  await expect(page.locator("main")).toContainText("Name contains “alert " + suffix + "” went over budget");
  await expect(page.locator("main")).toContainText("$1.00 over");
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished)));  // let the page crossfade end
  await page.screenshot({ path: ".local/alerts-phone.png" });
  await page.reload();
  await expect(page.getByRole("link", { name: /new alert/ })).toHaveCount(0);

  // Categorize by example: search, tick, keep the keyword as a rule; then one transaction "also similar".
  const tag = suffix.replace(/\d/g, (d) => "abcdefghij"[Number(d)]);  // letters only, like a real merchant name
  const addTxn = async (description: string) => {
    await page.goto("/");
    await page.getByRole("link", { name: accountName }).click();
    await page.getByRole("link", { name: "Add transaction" }).click();
    await page.getByLabel("Date").fill("2026-04-10");
    await page.getByLabel("Amount (USD)").fill("3.25");
    await page.getByLabel("Description").fill(description);
    await page.getByRole("button", { name: "Save transaction" }).click();
  };
  for (const d of [`Bagels${tag} #12`, `Bagels${tag} #34`, `Deli${tag} #1`, `Deli${tag} #2`]) await addTxn(d);
  await page.goto("/");
  await page.goto(page.url().split("?")[0] + "?period=2026-04");
  await page.getByRole("link", { name: "Manage categories" }).click();
  await page.getByRole("link", { name: /^Dining( ›)?$/ }).click();
  await page.getByRole("link", { name: "Add transactions" }).click();
  await page.getByLabel("Search transaction names").fill(`bagels${tag}`);
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByRole("status")).toContainText("2 transactions contain");
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished)));
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await page.screenshot({ path: `.local/category-add-${scheme}.png`, fullPage: true });
  }
  await page.emulateMedia({ colorScheme: "light" });
  await page.getByRole("button", { name: "Add ticked to Dining" }).click();
  await expect(page.locator("body")).toContainText(`Added 2 to Dining. Future “bagels${tag}” purchases will go there too.`);

  await page.goto("/");
  await page.getByRole("link", { name: accountName }).click();
  await page.getByRole("link", { name: new RegExp(`^Edit Deli${tag} #1`) }).click();
  await page.getByLabel("Category", { exact: true }).selectOption({ label: "Entertainment" });
  await expect(page.getByLabel("Name contains")).toHaveValue(`Deli${tag}`);
  await page.getByLabel(/^Also put other transactions/).check();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator("main")).toContainText(`Deli${tag} #2`);
  const deli2 = page.locator("li", { hasText: `Deli${tag} #2` });
  await expect(deli2).toContainText("Entertainment");
  await expect(page.locator("li", { hasText: `Bagels${tag} #34` })).toContainText("Dining");
});
