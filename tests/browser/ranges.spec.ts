import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only.
test("1M | 1Y | Lifetime on Overview and Timeline, and the phone's (i) note", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Overview", exact: true }).click();

  // On a phone the note waits behind (i) and closes on a tap elsewhere.
  const note = page.locator("#spending-note");
  const info = page.getByRole("button", { name: "About this total" });
  await expect(note).toBeHidden();
  await info.click();
  await expect(note).toBeVisible();
  await page.waitForTimeout(300);
  await page.screenshot({ path: ".local/overview-tip-phone.png" });
  await page.locator(".hero-amount").first().click({ position: { x: 4, y: 4 } });
  await expect(note).toBeHidden();

  await page.getByRole("link", { name: "Lifetime", exact: true }).click();
  await expect(page.getByRole("link", { name: "Lifetime", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("link", { name: "Previous all" })).toHaveCount(0);
  await info.click();
  await expect(note).toContainText("Lifetime spending · since");
  await page.keyboard.press("Escape");
  await expect(note).toBeHidden();
  // Wider screens show the note inline and no (i).
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(note).toBeVisible();
  await expect(info).toBeHidden();
  // Inline under the total, not where the phone popup was placed.
  const [amount, placed] = await Promise.all([page.locator(".hero-amount").first().boundingBox(), note.boundingBox()]);
  expect(Math.abs((placed?.x ?? 0) - (amount?.x ?? 0))).toBeLessThan(2);
  await page.waitForTimeout(1000);  // the chart redraws for the new width
  await page.screenshot({ path: ".local/overview-lifetime-desktop.png" });

  await page.setViewportSize({ width: 360, height: 800 });
  await page.getByRole("link", { name: "Timeline", exact: true }).click();
  const range = page.getByRole("navigation", { name: "Range" });
  await expect(range.getByRole("link", { name: "1M" })).toHaveAttribute("aria-current", "page");
  await range.getByRole("link", { name: "Lifetime" }).click();
  await expect(range.getByRole("link", { name: "Lifetime" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("button", { name: /^Filters/ })).not.toContainText("on");
  await range.getByRole("link", { name: "1Y" }).click();
  await expect(range.getByRole("link", { name: "1Y" })).toHaveAttribute("aria-current", "page");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  await page.waitForTimeout(1000);
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.waitForTimeout(300);  // buttons ease their background between themes
    await page.screenshot({ path: `.local/timeline-ranges-${scheme}.png` });
  }
});
