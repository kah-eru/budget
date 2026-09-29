// Side by side: a curved line between the two sides of each transfer, in one SVG over the lanes. Decoration only:
// every row already says in words where its money went, so nothing is lost without this script.
const NS = "http://www.w3.org/2000/svg";
const STUB = 16; // under half the gutter: a stub never reaches the next lane
const HEAD = "url(#flow-head)";
const AWAY = "url(#flow-away)";
const KEY = "budget-flows";

export function setup(lanes: HTMLElement) {
  lanes.querySelector(":scope > svg.flows")?.remove(); // a copy restored by Back still has the old lines
  const svg = document.createElementNS(NS, "svg");
  svg.classList.add("flows");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = '<defs><marker id="flow-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="flow-head" d="M0,1 L9,5 L0,9 z"/></marker><marker id="flow-away" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6"><circle class="flow-away" cx="5" cy="5" r="3.5"/></marker></defs>';
  lanes.prepend(svg);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let off = false;
  try {
    off = localStorage.getItem(KEY) === "off";
  } catch {
    // Storage blocked: lines start on.
  }

  const draw = (animate: boolean) => {
    svg.querySelectorAll("path:not(.flow-head)").forEach((p) => p.remove());
    svg.setAttribute("width", "0");
    svg.setAttribute("height", "0");
    const width = lanes.scrollWidth;
    const box = lanes.getBoundingClientRect();
    // Row edges, at the height of the row's amount, in the lanes' scrolled coordinates.
    const at = (row: HTMLElement) => {
      const r = row.getBoundingClientRect();
      const amount = (row.querySelector(".amount") || row).getBoundingClientRect();
      const left = r.left - box.left - lanes.clientLeft + lanes.scrollLeft;
      return { left, right: left + r.width, y: amount.top + amount.height / 2 - box.top - lanes.clientTop + lanes.scrollTop };
    };
    const line = (d: string, kind: string[], ends: [string, string], pair?: string) => {
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", d);
      if (ends[0]) path.setAttribute("marker-start", ends[0]);
      if (ends[1]) path.setAttribute("marker-end", ends[1]);
      path.classList.add(...kind);
      if (pair) path.dataset.pair = pair;
      svg.append(path);
      return path;
    };
    const drawn: SVGPathElement[] = [];
    lanes.querySelectorAll<HTMLElement>(".lane-row[data-flow]").forEach((row) => {
      const partner = row.dataset.partner ? document.getElementById(row.dataset.partner) : null;
      const pending = row.hasAttribute("data-pending") ? ["is-pending"] : [];
      const a = at(row);
      if (partner && lanes.contains(partner)) {
        if (row.dataset.flow !== "out") return; // each pair is drawn once, from where the money left
        const b = at(partner);
        const rightward = b.left >= a.right;
        const x1 = rightward ? a.right : a.left;
        const x2 = rightward ? b.left : b.right;
        const bend = Math.max(20, Math.abs(x2 - x1) / 2) * (rightward ? 1 : -1);
        drawn.push(line(`M${x1},${a.y} C${x1 + bend},${a.y} ${x2 - bend},${b.y} ${x2},${b.y}`, ["flow", ...pending], ["", HEAD], `${row.id} ${partner.id}`));
      } else {
        // The other side is elsewhere or off this page: a short stub into the gutter (left of the last lane) that ends in
        // a small open circle, so it never looks like it points at the next lane. Money leaving ends at the circle;
        // money arriving starts from it and arrows into the row.
        const x = a.right + STUB > width ? a.left : a.right;
        const away = x + (x === a.right ? STUB : -STUB);
        drawn.push(row.dataset.flow === "out" ? line(`M${x},${a.y} H${away}`, ["is-stub", ...pending], ["", AWAY])
                                              : line(`M${away},${a.y} H${x}`, ["is-stub", ...pending], [AWAY, HEAD]));
      }
    });
    svg.setAttribute("width", String(lanes.scrollWidth));
    svg.setAttribute("height", String(lanes.scrollHeight));
    if (!animate || reduced || off) return;
    for (const path of drawn) {
      if (path.classList.contains("flow") && !path.classList.contains("is-pending")) {
        const length = path.getTotalLength();
        path.animate({ strokeDasharray: [`${length}`, `${length}`], strokeDashoffset: [length, 0] }, { duration: 450, easing: "cubic-bezier(0.2, 0, 0, 1)" });
      } else {
        path.animate({ opacity: [0, 0.6] }, { duration: 300, easing: "ease-out" });
      }
    }
  };

  // Redraw when the lanes change size (rotation, window resize); the first callback repeats the first draw, so skip it.
  let size = "";
  let queued = 0;
  const observer = new ResizeObserver(([entry]) => {
    const next = `${entry.contentRect.width}x${entry.contentRect.height}`;
    if (next === size || queued) return;
    size = next;
    queued = requestAnimationFrame(() => {
      queued = 0;
      draw(false);
    });
  });
  document.fonts.ready.then(() => {
    draw(true);
    size = `${lanes.clientWidth}x${lanes.clientHeight}`;
    observer.observe(lanes);
  });

  // Hover or focus a transfer: it, its other side and its line light up.
  const lit: Element[] = [];
  const clear = () => {
    lit.forEach((el) => el.classList.remove("flow-active"));
    lit.length = 0;
  };
  const light = (event: Event) => {
    clear();
    const row = (event.target as Element).closest<HTMLElement>(".lane-row[data-partner]");
    if (!row) return;
    for (const el of [row, document.getElementById(row.dataset.partner!), svg.querySelector(`path[data-pair~="${row.id}"]`)]) {
      if (el) {
        el.classList.add("flow-active");
        lit.push(el);
      }
    }
  };
  lanes.addEventListener("pointerover", light);
  lanes.addEventListener("focusin", light);
  lanes.addEventListener("pointerleave", clear);

  // Show money moving: remembered on this device; the switch appears only when this script runs.
  const toggle = document.querySelector<HTMLElement>("[data-flow-toggle]");
  const box = toggle?.querySelector("input");
  svg.classList.toggle("is-off", off);
  if (toggle && box) {
    box.checked = !off;
    toggle.hidden = false;
    box.addEventListener("change", () => {
      off = !box.checked;
      svg.classList.toggle("is-off", off);
      try {
        if (off) localStorage.setItem(KEY, "off");
        else localStorage.removeItem(KEY);
      } catch {
        // Storage blocked: the choice holds until the page changes.
      }
    });
  }
}
