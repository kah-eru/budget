// Phone swipes. On a chart, away from its line: the next or previous month or year (the Period bar's arrows). Anywhere
// else: the next or previous tab (Overview, Timeline, Settings). The content follows the finger after a 10px direction
// lock, rubber-bands where there's nowhere to go, and commits on distance or a flick in the same direction. A touch on
// the line stays with the chart's own scrubbing tooltip.
const phone = window.matchMedia("(max-width: 639px)");
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
const EASE = "cubic-bezier(0.25, 1, 0.5, 1)"; // settles without overshoot
const LOCK = 10;
const NEAR_LINE = 24;
const EDGE = 20; // iOS takes edge swipes for back and forward

type Target = (direction: 1 | -1) => HTMLAnchorElement | null;

// Progressive resistance past a boundary: the further, the less it follows.
const rubberband = (dx: number, width: number) => (dx * width * 0.55) / (width + 0.55 * Math.abs(dx));

const visible = (el: Element | null) => !!el && (el as HTMLElement).getClientRects().length > 0;

// Next or previous month or year: the visible Period bar's arrows.
const periodLink: Target = (direction) =>
  [...document.querySelectorAll<HTMLAnchorElement>(`nav[aria-label="Period"] a[aria-label^="${direction > 0 ? "Next" : "Previous"} "]`)].find(visible) ?? null;

// Next or previous tab in the bottom navigation.
const tabLink: Target = (direction) => {
  const tabs = [...document.querySelectorAll<HTMLAnchorElement>(".nav-link")];
  const here = tabs.findIndex((tab) => tab.getAttribute("aria-current") === "page");
  return here < 0 ? null : tabs[here + direction] ?? null;
};

// Within NEAR_LINE px of the chart's line (its longest stroked, unfilled path), in screen pixels.
function nearLine(slot: HTMLElement, x: number, y: number) {
  const paths = [...slot.querySelectorAll<SVGPathElement>("svg path")].filter((path) => {
    const style = getComputedStyle(path);
    return ["none", "transparent", "rgba(0, 0, 0, 0)"].includes(style.fill) && style.stroke !== "none";
  });
  const line = paths.sort((a, b) => b.getTotalLength() - a.getTotalLength())[0];
  const matrix = line?.getScreenCTM();
  if (!line || !matrix) return false;
  const length = line.getTotalLength();
  for (let i = 0; i <= 80; i++) {
    const at = line.getPointAtLength((length * i) / 80);
    const p = new DOMPoint(at.x, at.y).matrixTransform(matrix);
    if (Math.hypot(p.x - x, p.y - y) < NEAR_LINE) return true;
  }
  return false;
}

// A horizontally scrollable ancestor (Timeline lanes, tables) keeps its own sideways drag.
function scrollsSideways(el: Element | null): boolean {
  for (; el && el !== document.body; el = el.parentElement) {
    const overflow = getComputedStyle(el).overflowX;
    if ((overflow === "auto" || overflow === "scroll") && el.scrollWidth > el.clientWidth) return true;
  }
  return false;
}

function track(start: TouchEvent, moving: HTMLElement, target: Target, own: boolean) {
  const touch = start.touches[0];
  const x0 = touch.clientX;
  const y0 = touch.clientY;
  const width = moving.getBoundingClientRect().width || window.innerWidth;
  let locked: boolean | null = own ? true : null; // null until the direction is clear; false hands the touch back
  let dx = 0;
  let history: { x: number; t: number }[] = [{ x: x0, t: start.timeStamp }];

  const move = (event: TouchEvent) => {
    if (own) event.stopPropagation();
    const t = event.touches[0];
    if (!t) return;
    const mx = t.clientX - x0;
    const my = t.clientY - y0;
    if (locked === null) {
      if (Math.hypot(mx, my) < LOCK) return;
      locked = Math.abs(mx) > Math.abs(my);
      if (!locked) return end();
    }
    if (!locked) return;
    dx = mx;
    history = [...history.slice(-4), { x: t.clientX, t: event.timeStamp }];
    const shown = target(dx < 0 ? 1 : -1) ? dx : rubberband(dx, width);
    if (!reduced.matches) moving.style.transform = `translateX(${shown}px)`;
  };

  const end = (event?: TouchEvent) => {
    if (own) event?.stopPropagation();
    window.removeEventListener("touchmove", move, true);
    window.removeEventListener("touchend", end, true);
    window.removeEventListener("touchcancel", end, true);
    if (!locked || dx === 0) return;
    const first = history[0];
    const last = history[history.length - 1];
    const velocity = (last.x - first.x) / Math.max(1, last.t - first.t); // px/ms, from the last few moves
    const direction = dx < 0 ? 1 : -1;
    const link = target(direction);
    // Commit on distance, or on a flick, but only when the flick still points the same way as the drag.
    const commit = link && Math.sign(velocity || dx) === Math.sign(dx) && (Math.abs(dx) > width * 0.25 || Math.abs(velocity) > 0.4);
    const from = moving.style.transform || "translateX(0px)";
    if (commit) {
      try {
        sessionStorage.setItem("swipe", direction > 0 ? "left" : "right");
      } catch {
        // Storage blocked: the next page just appears.
      }
      if (reduced.matches) return link.click();
      // Load the next page right away; the slide-out plays while it arrives.
      moving.animate({ transform: [from, `translateX(${-direction * width}px)`], opacity: [1, 0] }, { duration: 180, easing: EASE, fill: "forwards" });
      link.click();
    } else {
      moving.animate({ transform: [from, "translateX(0px)"] }, { duration: 300, easing: EASE });
      moving.style.transform = "";
    }
  };

  window.addEventListener("touchmove", move, { capture: true, passive: true });
  window.addEventListener("touchend", end, true);
  window.addEventListener("touchcancel", end, true);
}

export function setup() {
  // A page reached by a swipe enters from the side the finger came from.
  let entered: string | null = null;
  try {
    entered = sessionStorage.getItem("swipe");
    sessionStorage.removeItem("swipe");
  } catch {
    // Storage blocked: no entrance.
  }
  const main = document.getElementById("main");
  // Back to a page kept in the back-forward cache: undo the slide-out it left on.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) document.getAnimations().forEach((animation) => animation.cancel());
  });
  if (entered && main && !reduced.matches) {
    main.animate({ transform: [`translateX(${entered === "left" ? 40 : -40}px)`, "translateX(0px)"], opacity: [0, 1] }, { duration: 250, easing: EASE });
  }

  // Charts: capture runs before the chart's own touch handlers, so a swipe away from the line never shows the tooltip.
  document.querySelectorAll<HTMLElement>("[data-spending-chart]").forEach((slot) => {
    slot.addEventListener("touchstart", (event) => {
      const t = event.touches[0];
      if (!phone.matches || event.touches.length !== 1 || nearLine(slot, t.clientX, t.clientY)) return;
      event.stopPropagation();
      track(event, slot.querySelector<HTMLElement>("svg") ?? slot, periodLink, true);
    }, { capture: true, passive: true });
  });

  // Everywhere else: tabs.
  document.addEventListener("touchstart", (event) => {
    const t = event.touches[0];
    const el = event.target as Element;
    if (!phone.matches || !main || event.touches.length !== 1 || t.clientX < EDGE || t.clientX > window.innerWidth - EDGE) return;
    if (!main.contains(el) || el.closest("[data-spending-chart], input, select, textarea, label, [popover], dialog") || scrollsSideways(el)) return;
    track(event, main, tabLink, false);
  }, { passive: true });
}
