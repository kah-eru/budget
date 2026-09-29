import "./app.css";
import * as Turbo from "@hotwired/turbo";
import type { Root } from "react-dom/client";

// Turbo Drive: a link swaps the page's body instead of loading a new document, so this code, the styles and the chart code
// stay loaded, a tab shows at once from its preloaded copy while the fresh one arrives, and Back is instant. Forms still load
// a whole page: Django re-renders an invalid form with 200, which Turbo won't show. So do links marked data-turbo="false".
Turbo.config.forms.mode = "off";

// Turbo prefetches a link on hover. A phone has no hover, so touching a link counts as one; moving the finger past 10px (a
// scroll or a swipe) cancels it within Turbo's 100 ms wait. The tap's own late mouseenter is skipped so it isn't fetched twice.
let touched: Element | null = null;
document.addEventListener("touchstart", (event) => {
  touched = null;
  const link = (event.target as Element).closest?.("a[href]");
  if (!link || event.touches.length !== 1) return;
  link.dispatchEvent(new MouseEvent("mouseenter"));
  touched = link;
  const { clientX: x0, clientY: y0 } = event.touches[0];
  const stop = () => ["touchmove", "touchend", "touchcancel"].forEach((type) => window.removeEventListener(type, check, true));
  const check = (e: Event) => {
    const t = (e as TouchEvent).touches[0];
    if (e.type === "touchmove" && t && Math.hypot(t.clientX - x0, t.clientY - y0) < 10) return;
    if (e.type !== "touchend") link.dispatchEvent(new MouseEvent("mouseleave"));
    stop();
  };
  ["touchmove", "touchend", "touchcancel"].forEach((type) => window.addEventListener(type, check, { capture: true, passive: true }));
}, { capture: true, passive: true });
document.addEventListener("turbo:before-prefetch", (event) => {
  if (event.target === touched) event.preventDefault();
});

// A page restored from Turbo's cache is a copy taken as it was left: drop a drag's inline offset (the page, or a chart
// swiped to another period) before it shows.
document.addEventListener("turbo:before-render", (event) => {
  const body = (event as CustomEvent<{ newBody: HTMLElement }>).detail.newBody;
  body.querySelectorAll<HTMLElement>("#main, [data-spending-chart] svg").forEach((el) => el.style.removeProperty("transform"));
});

// No global Flowbite initializer: React will own only dedicated future mounts.
// Confirmed text is always server-rendered, including when scripts fail.
const root = document.documentElement;
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Chart code loads only on pages that have a chart. The server-rendered skeleton holds its space until it mounts.
// Each chart mounts once it's visible, so one in a hidden Overview panel never measures an empty box.
const mounted = new WeakSet<HTMLElement>();
const roots = new Map<HTMLElement, Root>();
const mountCharts = () => {
  document.querySelectorAll<HTMLElement>("[data-spending-chart]").forEach((chart) => {
    const series = document.getElementById(chart.dataset.series || "daily-series");
    if (mounted.has(chart) || !series || !chart.getClientRects().length) return;
    mounted.add(chart);
    import("./spending-chart")
      .then(({ mount }) => roots.set(chart, mount(chart, JSON.parse(series.textContent || "[]"), { total: chart.dataset.totalLabel || "Running total", day: chart.dataset.dayLabel || "That day" },
        (chart.dataset.markers || "").split(" ").filter(Boolean))))
      .catch(() => chart.remove()); // the totals and the daily table stay
  });
};

// The header's Spending | Savings switch. base.html renders the mode as data-overview-mode on <html> and CSS shows the
// matching sections; without JS the switch stays hidden and both show. The mode lives in a cookie because the server
// renders the Timeline for it.
const applySwitch = (value: string) => {
  root.dataset.overviewMode = value;
  mountCharts();
  if (!reduced) document.querySelectorAll<HTMLElement>(`[data-mode="${value}"]`).forEach((panel) => panel.animate({ opacity: [0, 1] }, { duration: 150, easing: "ease-out" }));
};

// Everything below binds to the page's own elements, so it runs for each page Turbo shows, once per body.
const ready = new WeakSet<HTMLElement>();
function setupPage() {
  if (ready.has(document.body)) return;
  ready.add(document.body);
  roots.forEach((chart, el) => {
    if (el.isConnected) return;
    chart.unmount();
    roots.delete(el);
  });

  if (!reduced) {
    document.querySelectorAll<HTMLElement>("[data-feedback]").forEach((element) => {
      // Flash from the accent to the element's own themed background, so dark mode ends dark.
      const rest = getComputedStyle(element).backgroundColor;
      // Native Web Animations (what motion/mini wraps): importing Motion here would make the chart chunk import app.js,
      // and in production Django serves app.<hash>.js, so the entry would load and run twice.
      element.animate({ backgroundColor: [getComputedStyle(document.documentElement).getPropertyValue("--accent"), rest] }, { duration: 300, easing: "ease-out" });
      element.removeAttribute("data-feedback"); // once: not again when Back restores this page
    });
  }

  document.querySelectorAll<HTMLFieldSetElement>("[data-switch]").forEach((fieldset) => {
    const current = fieldset.querySelector<HTMLInputElement>(`input[value="${root.dataset.overviewMode}"]`);
    if (current) current.checked = true;
    fieldset.hidden = false;
    fieldset.addEventListener("change", (event) => {
      const value = (event.target as HTMLInputElement).value;
      document.cookie = `${fieldset.dataset.cookie}=${value}; path=/; max-age=31536000; samesite=lax`;
      // Pages kept or preloaded before the switch are in the old mode.
      Turbo.cache.clear();
      if (fieldset.dataset.reload !== undefined) {
        // Turbo keeps <html>, so its mode must change here too. The ticked accounts differ between modes, and a page cursor
        // belongs to the old list.
        root.dataset.overviewMode = value;
        const url = new URL(location.href);
        ["account", "before", "rev"].forEach((name) => url.searchParams.delete(name));
        Turbo.visit(url.href, { action: "replace" });
        return;
      }
      applySwitch(value);
      Turbo.session.preloadOnLoadLinksForView(document.body);
    });
  });
  mountCharts();

  // Menus are native popovers (Escape and outside taps close them). Placed under their button, along its left edge when it's
  // on the left of the screen and its right edge otherwise, in page coordinates so the menu scrolls with its button; without
  // JS the browser centres them.
  // A hero note's tip spans the phone's width under its (i) and also closes when focus leaves the (i).
  document.querySelectorAll<HTMLElement>(".menu[popover], .tip[popover]").forEach((menu) => {
    const button = document.querySelector<HTMLElement>(`[popovertarget="${menu.id}"]`);
    const tip = menu.classList.contains("tip");
    if (tip) button?.addEventListener("blur", () => menu.matches(":popover-open") && menu.hidePopover());
    menu.addEventListener("beforetoggle", (event) => {
      if ((event as ToggleEvent).newState !== "open") {
        if (tip) menu.removeAttribute("style"); // a wider screen shows the note inline, where the placement would misplace it
        return;
      }
      if (!button) return;
      const r = button.getBoundingClientRect();
      const side = tip ? { left: "1rem", right: "1rem" } : r.left < root.clientWidth / 2 ? { left: `${Math.max(8, r.left)}px`, transformOrigin: "top left" } : { right: `${Math.max(8, root.clientWidth - r.right)}px` };
      Object.assign(menu.style, { position: "absolute", inset: "auto", margin: "0", top: `${r.bottom + window.scrollY + 6}px`, ...side });
    });
  });

  // Timeline Filters: a disclosure button. CSS hides the panel once JS runs, so it never flashes; without JS it stays open.
  const filtersButton = document.querySelector<HTMLButtonElement>("[data-filters-toggle]");
  const filtersPanel = document.getElementById(filtersButton?.getAttribute("aria-controls") || "");
  if (filtersButton && filtersPanel) {
    filtersButton.addEventListener("click", () => {
      const open = filtersPanel.classList.toggle("is-open");
      filtersButton.setAttribute("aria-expanded", String(open));
      if (open && !reduced) filtersPanel.animate({ opacity: [0, 1], transform: ["translateY(-4px)", "none"] }, { duration: 150, easing: "ease-out" });
    });
  }

  // Timeline "Go to" a day: scroll to it when that day is on this page (or the nearest earlier one), else load the list from it.
  document.querySelectorAll<HTMLFormElement>("[data-day-picker]").forEach((form) => {
    const input = form.querySelector<HTMLInputElement>('input[name="day"]');
    input?.addEventListener("change", () => {
      const day = input.value;
      const lines = [...document.querySelectorAll<HTMLElement>("[data-day]")];
      if (!day || !lines.length) return;
      const newest = lines[0].dataset.day!, oldest = lines[lines.length - 1].dataset.day!;
      const onPage = (day <= newest || !("paged" in form.dataset)) && (day >= oldest || !("more" in form.dataset));
      const target = lines.find((line) => line.dataset.day! <= day) ?? lines[lines.length - 1];
      if (!onPage) return form.requestSubmit();
      target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
      if (!reduced) target.animate({ backgroundColor: [getComputedStyle(document.documentElement).getPropertyValue("--accent-soft"), "transparent"] }, { duration: 900, easing: "ease-out" });
    });
  });

  // Select all / Clear all for the Timeline's account tick boxes.
  document.querySelectorAll<HTMLElement>("[data-accounts]").forEach((set) => {
    const button = set.querySelector<HTMLButtonElement>("[data-select-all]");
    const boxes = Array.from(set.querySelectorAll<HTMLInputElement>("input[type=checkbox]"));
    if (!button) return;
    const count = set.querySelector("[data-account-count]");
    const label = () => {
      const ticked = boxes.filter((b) => b.checked).length;
      button.textContent = ticked === boxes.length ? "Clear all" : "Select all";
      if (count) count.textContent = ticked ? `${ticked} of ${boxes.length}` : "All";
    };
    button.addEventListener("click", () => {
      const all = !boxes.every((b) => b.checked);
      boxes.forEach((b) => (b.checked = all));
      label();
    });
    set.addEventListener("change", label);
    label();
    button.hidden = false;
  });

  // Push notification controls exist only on Settings when the server has push keys.
  const pushSection = document.querySelector<HTMLElement>("[data-push]");
  if (pushSection) import("./push").then(({ setup }) => setup(pushSection)).catch(() => {});

  // Plaid Link (and Plaid's own script) load only on the Connect a bank page, which always loads as a whole page.
  const plaidLink = document.querySelector<HTMLElement>("[data-plaid-link]");
  if (plaidLink) import("./plaid-link").then(({ setup }) => setup(plaidLink)).catch(() => {});

  // Money lines load only on the Timeline's Side by side layout.
  const lanes = document.querySelector<HTMLElement>("[data-lanes]");
  if (lanes) import("./flows").then(({ setup }) => setup(lanes)).catch(() => {});
  // Chart swipes between periods.
  import("./swipe").then(({ setupCharts }) => setupCharts()).catch(() => {});

  // Theme choice for this device. base.html applies the saved value before paint; without JS the picker stays hidden.
  const picker = document.querySelector<HTMLFieldSetElement>("[data-theme-picker]");
  if (picker) {
    const current = picker.querySelector<HTMLInputElement>(`input[value="${root.dataset.theme || "system"}"]`);
    if (current) current.checked = true;
    picker.hidden = false;
    picker.addEventListener("change", (event) => {
      const value = (event.target as HTMLInputElement).value;
      if (value === "system") delete root.dataset.theme;
      else root.dataset.theme = value;
      try {
        if (value === "system") localStorage.removeItem("theme");
        else localStorage.setItem("theme", value);
      } catch {
        // Storage blocked: the choice still applies until the page changes.
      }
    });
  }
}

// Phone swipes between tabs; the module checks the width on each touch. A page reached by a swipe slides in on its first
// render, which is the preloaded copy when there is one, so it doesn't slide in again when the fresh copy replaces it.
import("./swipe").then(({ setup, enter }) => {
  setup();
  enter();
  document.addEventListener("turbo:render", enter);
}).catch(() => {});
setupPage();
document.addEventListener("turbo:load", setupPage);
