import { test, expect } from "@playwright/test";

// Synthetic data on the disposable local database only. Touches go through CDP, as a phone's would.
test.use({ hasTouch: true, viewport: { width: 360, height: 800 } });

test("phone swipes: the chart steps months, the page switches tabs, the line keeps its tooltip", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  const cdp = await page.context().newCDPSession(page);
  const swipe = async (x1: number, y1: number, x2: number, y2 = y1) => {
    // Let the page change's crossfade end first: during it every touch lands on <html>.
    await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: x1, y: y1 }] });
    for (let i = 1; i <= 8; i++) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x1 + ((x2 - x1) * i) / 8, y: y1 + ((y2 - y1) * i) / 8 }] });
    }
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  };
  const chart = page.locator("[data-spending-chart]:visible").first();
  await expect(chart.locator("svg path").first()).toBeAttached();
  await page.waitForTimeout(800); // the line draws in

  // On the line: the chart keeps the touch for its tooltip, and the page stays.
  const onLine = await chart.evaluate((slot) => {
    const line = [...slot.querySelectorAll<SVGPathElement>("svg path")].filter((p) => ["none", "transparent", "rgba(0, 0, 0, 0)"].includes(getComputedStyle(p).fill) && getComputedStyle(p).stroke !== "none")
      .sort((a, b) => b.getTotalLength() - a.getTotalLength())[0];
    const at = line.getPointAtLength(line.getTotalLength() / 2);
    const p = new DOMPoint(at.x, at.y).matrixTransform(line.getScreenCTM()!);
    return { x: p.x, y: p.y };
  });
  const here = page.url();
  await swipe(onLine.x, onLine.y, onLine.x - 100);
  await page.waitForTimeout(500);
  expect(page.url()).toBe(here);

  // Away from the line (the empty top of the chart): next month, then back.
  const box = (await chart.boundingBox())!;
  await swipe(box.x + box.width * 0.45, box.y + 6, box.x + box.width * 0.05);
  await expect(page.getByRole("link", { name: /^Today/ })).toBeVisible();
  expect(page.url()).not.toBe(here);
  const next = (await chart.boundingBox())!;
  await swipe(next.x + next.width * 0.2, next.y + 6, next.x + next.width * 0.7);
  await expect(page).toHaveURL(here);  // wait for the page itself, not a link that vanishes mid-navigation
  await expect(page.getByRole("link", { name: /^Today/ })).toHaveCount(0);

  // Anywhere else: the tabs (Timeline · Overview · Budget), keeping the range.
  const row = (await page.getByText("Posted spending", { exact: true }).boundingBox())!;
  await swipe(300, row.y + 5, 60);
  await expect(page).toHaveURL(/\/budgets\/\?period=/);
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Budget" })).toHaveAttribute("aria-current", "page");
  const heading = (await page.getByRole("heading", { name: "Categories" }).boundingBox())!;
  await swipe(60, heading.y + 5, 300);
  await expect(page).toHaveURL(here);
  const overviewRow = (await page.getByText("Posted spending", { exact: true }).boundingBox())!;
  await swipe(60, overviewRow.y + 5, 300);
  await expect(page).toHaveURL(/\/transactions\/\?start=/);
  // Settings sits in the header now, not in the tabs, so a swipe there stays put.
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  const settings = page.url();
  await swipe(300, 400, 60);
  await page.waitForTimeout(500);
  expect(page.url()).toBe(settings);
  await page.screenshot({ path: ".local/swipe-settings.png" });
});
