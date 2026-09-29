import { test as base, expect, type Locator, type Page } from "@playwright/test";

// Turbo swaps pages without a browser navigation, so Playwright's click doesn't wait for the next page and the next step
// would find the old one. Turbo marks <html aria-busy> from the click until the new page is in; every click waits that out.
// A locator wait also survives a whole-page load (forms), where an evaluate would lose its page.
export const settled = (page: Page) => page.locator("html:not([aria-busy])").waitFor({ state: "attached" });

export const test = base.extend({
  page: async ({ page }, use) => {
    const proto = Object.getPrototypeOf(page.locator("html")) as Locator & { turboWait?: true };
    if (!proto.turboWait) {
      const click = proto.click;
      proto.click = async function (this: Locator, ...args: Parameters<Locator["click"]>) {
        await click.apply(this, args);
        await settled(this.page());
      };
      proto.turboWait = true;
    }
    await use(page);
  },
});

export { expect };
