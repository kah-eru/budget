import { test, expect, settled } from "./turbo";

// Synthetic data on the disposable local database only.
test.use({ hasTouch: true, viewport: { width: 360, height: 800 } });

test("tabs change without reloading the app, Back restores a working page, a touch prefetches the link", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await nav.getByRole("link", { name: "Overview" }).click();
  await page.evaluate(() => ((window as unknown as { sameDocument: boolean }).sameDocument = true));
  const kept = () => page.evaluate(() => (window as unknown as { sameDocument?: boolean }).sameDocument === true);

  // A tab: the same document (the code stays loaded), the new page's own chart draws.
  await nav.getByRole("link", { name: "Timeline" }).click();
  await expect(nav.getByRole("link", { name: "Timeline" })).toHaveAttribute("aria-current", "page");
  expect(await kept()).toBe(true);
  await expect(page.locator("[data-spending-chart]:visible svg path").first()).toBeAttached();

  // Back: Overview from Turbo's copy, still one chart, and it draws again.
  await page.goBack();
  await settled(page);
  await expect(nav.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  expect(await kept()).toBe(true);
  await expect(page.locator("[data-spending-chart]:visible svg path").first()).toBeAttached();
  await expect(page.locator("[data-spending-chart]:visible > div")).toHaveCount(1);

  // A touch on a link fetches it before the finger lifts; Alerts is never prefetched (opening it marks alerts read).
  const prefetched: string[] = [];
  page.on("request", (r) => r.headers()["x-sec-purpose"] === "prefetch" && prefetched.push(new URL(r.url()).pathname));
  const touch = async (name: string | RegExp) => {
    const box = (await page.getByRole("link", { name }).first().boundingBox())!;
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: box.x + 4, y: box.y + box.height / 2 }] });
    await page.waitForTimeout(300);  // past Turbo's 100 ms wait
    await cdp.send("Input.dispatchTouchEvent", { type: "touchCancel", touchPoints: [] });
  };
  await touch("Settings");
  await expect.poll(() => prefetched).toContain("/settings/");
  await touch(/Alerts|new alert/);
  await page.waitForTimeout(300);
  expect(prefetched).not.toContain("/alerts/");
});
