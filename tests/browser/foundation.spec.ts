import { test, expect } from "@playwright/test";

// Run only against the disposable local development database. These are synthetic.
test("sign-in, private account creation, explicit sharing, reflow and reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your accounts" })).toBeVisible();
  const suffix = Date.now().toString();
  const accountName = "Synthetic checking " + suffix;
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill(accountName);
  await page.getByRole("button", { name: "Create private account" }).click();
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("link", { name: /^New group/ }).click();
  await page.getByLabel("Name", { exact: true }).fill("Synthetic group " + suffix);
  await page.getByRole("button", { name: "Create group", exact: true }).click();
  await expect(page.locator("main")).not.toContainText(accountName);
  await page.getByRole("link", { name: "Manage sharing" }).click();
  await page.getByLabel(accountName, { exact: true }).check();
  await page.getByLabel("I understand that everyone").check();
  await page.getByRole("button", { name: "Save sharing" }).click();
  await expect(page.locator("main")).toContainText(accountName);
  await expect(page.getByRole("status")).toHaveText("Sharing saved.");
  expect(await page.getByRole("status").evaluate((element) => element.getAnimations().length)).toBe(0);
  for (const width of [320, 360, 390, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: ".local/foundation-phone.png", fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: ".local/foundation-desktop.png", fullPage: true });
});

test("sign-in and server-rendered controls work without JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:8000/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your accounts" })).toBeVisible();
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("link", { name: /^Add account/ }).click();
  await page.getByLabel("Name", { exact: true }).fill("No JavaScript synthetic account");
  await page.getByRole("button", { name: "Create private account" }).click();
  await expect(page.locator("main")).toContainText("No JavaScript synthetic account");
  await context.close();
});
