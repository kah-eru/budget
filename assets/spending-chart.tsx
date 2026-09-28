import { MotionConfig } from "motion/react";
import { createRoot } from "react-dom/client";
import { Area } from "@/components/charts/area";
import { AreaChart } from "@/components/charts/area-chart";
import { ChartTooltip } from "@/components/charts/tooltip";

type Day = { day: string; posted_cents: number; cumulative_cents: number };
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

// Server-calculated series only; the daily table in the same page is the accessible equivalent.
export function mount(el: HTMLElement, days: Day[]) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const data = days.map((d) => ({ date: new Date(d.day + "T00:00:00"), total: d.cumulative_cents / 100, day: d.posted_cents / 100 }));
  createRoot(el).render(
    <MotionConfig reducedMotion="user">
      <AreaChart data={data} aspectRatio="2.4 / 1" animationDuration={reduced ? 0 : 600} margin={{ top: 12, right: 4, bottom: 12, left: 4 }}>
        {/* Bare line, no axes: the number above is the headline and the tooltip gives the date. */}
        <Area dataKey="total" fill="var(--chart-1)" stroke="var(--chart-1)" fillOpacity={0.08} strokeWidth={2.5} />
        <ChartTooltip rows={(p) => [
          { color: "var(--chart-1)", label: "Running total", value: usd.format(p.total as number) },
          { color: "var(--chart-2)", label: "That day", value: usd.format(p.day as number) },
        ]} />
      </AreaChart>
    </MotionConfig>,
  );
}
