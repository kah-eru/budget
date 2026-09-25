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
