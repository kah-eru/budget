import "./app.css";
import { animate } from "motion/mini";

// No global Flowbite initializer: React will own only dedicated future mounts.
// Confirmed text is always server-rendered, including when scripts fail.
if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.querySelectorAll<HTMLElement>("[data-feedback]").forEach((element) => {
    // Flash from the accent to the element's own themed background, so dark mode ends dark.
    const rest = getComputedStyle(element).backgroundColor;
    animate(element, { backgroundColor: [getComputedStyle(document.documentElement).getPropertyValue("--accent"), rest] }, { duration: 0.3 });
  });
}

// Chart code loads only on pages that have a chart; a load failure leaves the table in place.
const chart = document.querySelector<HTMLElement>("[data-spending-chart]");
const series = document.getElementById("daily-series");
if (chart && series) {
  import("./spending-chart").then(({ mount }) => {
    mount(chart, JSON.parse(series.textContent || "[]"));
    chart.hidden = false;
  }).catch(() => {});
}

// Theme choice for this device. base.html applies the saved value before paint; without JS the picker stays hidden.
const picker = document.querySelector<HTMLFieldSetElement>("[data-theme-picker]");
if (picker) {
  const root = document.documentElement;
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
