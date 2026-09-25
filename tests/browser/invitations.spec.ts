import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";

// Synthetic local console email only; runserver stdout goes to this ignored file.
async function latestMailLink(route: string) {
  let links: RegExpMatchArray | null = null;
  await expect.poll(() => {
    links = readFileSync(".local/browser-server.log", "utf8").match(new RegExp(`http://127\\.0\\.0\\.1:8000/${route}/[^\\s]+`, "g"));
    return links?.length ?? 0;
  }).toBeGreaterThan(0);
  return links![links!.length - 1];
}

test("invited registration, email confirmation and sharing access work without JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const suffix = Date.now().toString();
  await page.goto("http://127.0.0.1:8000/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("link", { name: /^New group/ }).click();
  await page.getByLabel("Name", { exact: true }).fill("Invitation check " + suffix);
  await page.getByRole("button", { name: "Create group", exact: true }).click();
  await page.getByRole("link", { name: "Invite someone" }).click();
  await page.getByLabel("Their email address").fill(`invited-${suffix}@example.com`);
  await page.getByLabel("I understand that this person").check();
  await page.getByRole("button", { name: "Send invitation", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Invitation sent");
  for (const width of [320, 360, 390, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.screenshot({ path: ".local/invitations-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: ".local/invitations-phone.png", fullPage: true });
  const invitation = await latestMailLink("invitations");
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.goto(invitation);
  await page.getByRole("link", { name: "Create invited account" }).click();
  await page.getByRole("button", { name: "Send account setup email" }).click();
  await expect(page.getByRole("status")).toContainText("Check your email");
  await page.goto(await latestMailLink("invitations/[^/]+/register"));
  await page.getByLabel("Username", { exact: true }).fill("invited-" + suffix);
  await page.getByLabel("Password", { exact: true }).fill("Synthetic-invitation-passphrase-98");
  await page.getByLabel("Password confirmation", { exact: true }).fill("Synthetic-invitation-passphrase-98");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await page.getByLabel("Username", { exact: true }).fill("invited-" + suffix);
  await page.getByLabel("Password", { exact: true }).fill("Synthetic-invitation-passphrase-98");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("I want to join this group").check();
  await page.getByRole("button", { name: "Join group", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Invitation check " + suffix, exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Your own accounts are still private");
  await expect(page.getByRole("link", { name: "Invite someone" })).toHaveCount(0);
  await page.getByRole("button", { name: "Leave group", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your accounts" })).toBeVisible();
  await context.close();
});

test("standalone invitation creates a private login with no group access", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 360, height: 800 } });
  const page = await context.newPage();
  const suffix = Date.now().toString();
  await page.goto("http://127.0.0.1:8000/login/");
  await page.getByLabel("Username", { exact: true }).fill("browser-check");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-browser-check-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "More", exact: true }).click();
  for (const width of [320, 360]) {
    await page.setViewportSize({ width, height: 800 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.screenshot({ path: ".local/more-phone.png", fullPage: true });
  await page.getByRole("link", { name: /^Invite someone to Budget/ }).click();
  await page.getByLabel("Their email address").fill(`solo-${suffix}@example.com`);
  await page.getByLabel("I understand they get their own private login").check();
  await page.getByRole("button", { name: "Send invitation", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Invitation sent");
  const invitation = await latestMailLink("invitations");
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.goto(invitation);
  await expect(page.getByRole("heading", { name: "Create your Budget login" })).toBeVisible();
  await page.getByRole("link", { name: "Create your login" }).click();
  await page.getByRole("button", { name: "Send account setup email" }).click();
  await page.goto(await latestMailLink("invitations/[^/]+/register"));
  await page.getByLabel("Username", { exact: true }).fill("solo-" + suffix);
  await page.getByLabel("Password", { exact: true }).fill("Synthetic-solo-passphrase-42");
  await page.getByLabel("Password confirmation", { exact: true }).fill("Synthetic-solo-passphrase-42");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await page.getByLabel("Username", { exact: true }).fill("solo-" + suffix);
  await page.getByLabel("Password", { exact: true }).fill("Synthetic-solo-passphrase-42");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("I want to finish setting up").check();
  await page.getByRole("button", { name: "Finish", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Your login is ready");
  await page.getByText("Workspace:").click();
  await expect(page.getByRole("navigation", { name: "Workspaces" }).getByRole("link")).toHaveCount(1);
  await page.screenshot({ path: ".local/switcher-phone.png" });
  await context.close();
});
