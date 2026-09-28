import "./app.css";

// No global Flowbite initializer: React will own only dedicated future mounts.
// Confirmed text is always server-rendered, including when scripts fail.
const root = document.documentElement;
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!reduced) {
  document.querySelectorAll<HTMLElement>("[data-feedback]").forEach((element) => {
    // Flash from the accent to the element's own themed background, so dark mode ends dark.
    const rest = getComputedStyle(element).backgroundColor;
    // Native Web Animations (what motion/mini wraps): importing Motion here would make the chart chunk import app.js,
    // and in production Django serves app.<hash>.js, so the entry would load and run twice.
    element.animate({ backgroundColor: [getComputedStyle(document.documentElement).getPropertyValue("--accent"), rest] }, { duration: 300, easing: "ease-out" });
  });
}

// Chart code loads only on pages that have a chart. The server-rendered skeleton holds its space until it mounts.
// Each chart mounts once it's visible, so one in a hidden Overview panel never measures an empty box.
const mounted = new Set<HTMLElement>();
const mountCharts = () => {
  document.querySelectorAll<HTMLElement>("[data-spending-chart]").forEach((chart) => {
    const series = document.getElementById(chart.dataset.series || "daily-series");
    if (mounted.has(chart) || !series || !chart.getClientRects().length) return;
    mounted.add(chart);
    import("./spending-chart")
      .then(({ mount }) => mount(chart, JSON.parse(series.textContent || "[]"), { total: chart.dataset.totalLabel || "Running total", day: chart.dataset.dayLabel || "That day" }))
      .catch(() => chart.remove()); // the totals and the daily table stay
  });
};

// Switches: the header's Spending | Savings (overviewMode) and Overview's Chart | Budgets (overview). base.html applies the
// choices before paint as data attributes on <html>, and CSS shows the matching panels; without JS the switches stay hidden
// and every panel shows. The mode lives in a cookie because the server renders the Timeline for it.
document.querySelectorAll<HTMLFieldSetElement>("[data-switch]").forEach((fieldset) => {
  const key = fieldset.dataset.switch as "overview" | "overviewMode";
  const current = fieldset.querySelector<HTMLInputElement>(`input[value="${root.dataset[key]}"]`);
  if (current) current.checked = true;
  fieldset.hidden = false;
  fieldset.addEventListener("change", (event) => {
    const value = (event.target as HTMLInputElement).value;
    if (fieldset.dataset.cookie) {
      document.cookie = `${fieldset.dataset.cookie}=${value}; path=/; max-age=31536000; samesite=lax`;
      // A tab page prefetched before the switch would open in the old mode, so prefetch again.
      const rules = document.querySelector('script[type="speculationrules"]');
      if (rules) {
        const fresh = document.createElement("script");
        fresh.type = "speculationrules";
        fresh.textContent = rules.textContent;
        rules.replaceWith(fresh);
      }
      if (fieldset.dataset.reload !== undefined) {
        // The ticked accounts differ between modes, and a page cursor belongs to the old list.
        const url = new URL(location.href);
        ["account", "before", "rev"].forEach((name) => url.searchParams.delete(name));
        location.replace(url);
        return;
      }
    } else {
      try {
        localStorage.setItem(key, value);
      } catch {
        // Storage blocked: the choice holds until the page changes.
      }
    }
    root.dataset[key] = value;
    mountCharts();
    if (!reduced) document.querySelectorAll<HTMLElement>(`[data-panel="${value}"], [data-mode="${value}"]`).forEach((panel) => panel.animate({ opacity: [0, 1] }, { duration: 150, easing: "ease-out" }));
  });
});
mountCharts();

// Menus are native popovers (Escape and outside taps close them). Placed under their button, along its left edge when it's
// on the left of the screen and its right edge otherwise, in page coordinates so the menu scrolls with its button; without
// JS the browser centres them.
document.querySelectorAll<HTMLElement>(".menu[popover]").forEach((menu) => {
  const button = document.querySelector<HTMLElement>(`[popovertarget="${menu.id}"]`);
  menu.addEventListener("beforetoggle", (event) => {
    if ((event as ToggleEvent).newState !== "open" || !button) return;
    const r = button.getBoundingClientRect();
    const side = r.left < root.clientWidth / 2 ? { left: `${Math.max(8, r.left)}px`, transformOrigin: "top left" } : { right: `${Math.max(8, root.clientWidth - r.right)}px` };
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

// Plaid Link (and Plaid's own script) load only on the Connect a bank page.
const plaidLink = document.querySelector<HTMLElement>("[data-plaid-link]");
if (plaidLink) import("./plaid-link").then(({ setup }) => setup(plaidLink)).catch(() => {});

// Money lines load only on the Timeline's Side by side layout.
const lanes = document.querySelector<HTMLElement>("[data-lanes]");
if (lanes) import("./flows").then(({ setup }) => setup(lanes)).catch(() => {});

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
