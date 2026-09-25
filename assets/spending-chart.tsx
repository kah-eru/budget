import { MotionConfig } from "motion/react";
import { createRoot } from "react-dom/client";
import { Area } from "@/components/charts/area";
import { AreaChart } from "@/components/charts/area-chart";
import { Grid } from "@/components/charts/grid";
import { ChartTooltip } from "@/components/charts/tooltip";
import { XAxis } from "@/components/charts/x-axis";

type Day = { day: string; posted_cents: number; cumulative_cents: number };
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

// Server-calculated series only; the daily table in the same page is the accessible equivalent.
export function mount(el: HTMLElement, days: Day[]) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const data = days.map((d) => ({ date: new Date(d.day + "T00:00:00"), total: d.cumulative_cents / 100, day: d.posted_cents / 100 }));
  createRoot(el).render(
    <MotionConfig reducedMotion="user">
      <AreaChart data={data} aspectRatio="2 / 1" animationDuration={reduced ? 0 : 600} margin={{ top: 16, right: 28, bottom: 32, left: 28 }}>
        <Grid horizontal />
        <Area dataKey="total" fill="var(--chart-1)" stroke="var(--chart-1)" fillOpacity={0.25} strokeWidth={2} />
        <XAxis numTicks={4} />
        <ChartTooltip rows={(p) => [
          { color: "var(--chart-1)", label: "Running total", value: usd.format(p.total as number) },
          { color: "var(--chart-2)", label: "That day", value: usd.format(p.day as number) },
        ]} />
      </AreaChart>
    </MotionConfig>,
  );
}
