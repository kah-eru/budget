import { MotionConfig } from "motion/react";
import { createRoot } from "react-dom/client";
import { Area } from "@/components/charts/area";
import { AreaChart } from "@/components/charts/area-chart";
import { useChartStable } from "@/components/charts/chart-context";
import { ChartTooltip } from "@/components/charts/tooltip";

type Day = { day: string; posted_cents: number; cumulative_cents: number };
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

// Faint dashed time lines (views.chart_markers); their labels sit in the row under the chart.
function TimeMarkers({ dates }: { dates: Date[] }) {
  const { xScale, innerHeight } = useChartStable();
  return (
    <g aria-hidden="true">
      {dates.map((date) => (
        <line key={date.getTime()} x1={xScale(date)} x2={xScale(date)} y1={0} y2={innerHeight} stroke="var(--chart-grid)" strokeDasharray="3,4" />
      ))}
    </g>
  );
}

// Server-calculated series only; the daily table in the same page is the accessible equivalent.
export function mount(el: HTMLElement, days: Day[], labels = { total: "Running total", day: "That day" }, markers: string[] = []) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const data = days.map((d) => ({ date: new Date(d.day + "T00:00:00"), total: d.cumulative_cents / 100, day: d.posted_cents / 100 }));
  createRoot(el).render(
    <MotionConfig reducedMotion="user">
      <AreaChart data={data} aspectRatio="2.8 / 1" style={{ maxHeight: "13rem" }} animationDuration={reduced ? 0 : 600} margin={{ top: 12, right: 4, bottom: 4, left: 4 }}>
        {/* No axes: the number above is the headline, the tooltip gives the date, and faint lines mark the time. */}
        <TimeMarkers dates={markers.map((day) => new Date(day + "T00:00:00"))} />
        <Area dataKey="total" fill="var(--chart-1)" stroke="var(--chart-1)" fillOpacity={0.08} strokeWidth={2.5} />
        <ChartTooltip rows={(p) => [
          { color: "var(--chart-1)", label: labels.total, value: usd.format(p.total as number) },
          { color: "var(--chart-2)", label: labels.day, value: usd.format(p.day as number) },
        ]} />
      </AreaChart>
    </MotionConfig>,
  );
}
