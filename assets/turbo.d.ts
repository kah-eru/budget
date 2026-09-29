// Turbo ships no types; only what app.tsx uses.
declare module "@hotwired/turbo" {
  export const config: { forms: { mode: "on" | "off" | "optin" } };
  export const cache: { clear(): void };
  export const session: { preloadOnLoadLinksForView(element: Element): void };
  export function visit(location: string, options?: { action?: "advance" | "replace" }): void;
}
