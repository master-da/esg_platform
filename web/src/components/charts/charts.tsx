"use client";

import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  type TooltipContentProps,
} from "recharts";
import { CHART, compact } from "./palette";

export type Series = { key: string; label: string; color: string };
type Row = Record<string, string | number | null>;

function fmt(v: unknown, digits = 2): string {
  return typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: digits }) : String(v);
}

/** Tooltip in text tokens; a missing value reads "Missing", never 0. */
function ChartTooltip({ active, payload, label, unit, series, digits }: TooltipContentProps<number, string> & {
  unit?: string; series: Series[]; digits: number;
}) {
  if (!active) return null;
  const row = (payload?.[0]?.payload ?? {}) as Row;
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-sm">
      <div className="mb-1 font-medium text-foreground">{label}</div>
      {series.map((s) => (
        <div key={s.key} className="flex items-center gap-2 text-muted-foreground">
          <span className="inline-block size-2.5 rounded-sm" style={{ background: s.color }} />
          <span>{s.label}</span>
          <span className="ml-auto pl-3 text-foreground tabular-nums">
            {row[s.key] === null || row[s.key] === undefined ? "Missing" : `${fmt(row[s.key], digits)}${unit ? ` ${unit}` : ""}`}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Legend labels wear text ink; the swatch beside them carries the series colour. */
const legendText = (value: string) => <span style={{ color: CHART.secondary }}>{value}</span>;

const axisProps = {
  stroke: CHART.axis,
  tick: { fill: CHART.muted, fontSize: 11 },
  tickLine: false,
} as const;

/** Monthly / yearly trend. Missing points are gaps (connectNulls off), never drawn at zero. */
export function TrendLines({ data, x, series, unit, height = 220, digits = 2 }: {
  data: Row[]; x: string; series: Series[]; unit?: string; height?: number; digits?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={CHART.grid} strokeWidth={1} vertical={false} />
        <XAxis dataKey={x} {...axisProps} />
        <YAxis {...axisProps} axisLine={false} width={48} tickFormatter={(v: number) => compact(v)} />
        <Tooltip content={(p) => <ChartTooltip {...(p as TooltipContentProps<number, string>)} unit={unit} series={series} digits={digits} />} cursor={{ stroke: CHART.axis }} />
        {series.length > 1 && <Legend iconType="plainline" itemSorter={null} formatter={legendText} wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s) => (
          <Line key={s.key} dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={2} connectNulls={false}
            dot={{ r: 4, fill: s.color, stroke: CHART.surface, strokeWidth: 2 }} activeDot={{ r: 5, stroke: CHART.surface, strokeWidth: 2 }}
            strokeLinecap="round" strokeLinejoin="round" isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Stacked (or single) columns. 24px max, 4px rounded data-end, 2px surface gap between segments. */
export function StackedColumns({ data, x, series, unit, height = 240, digits = 2 }: {
  data: Row[]; x: string; series: Series[]; unit?: string; height?: number; digits?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={CHART.grid} strokeWidth={1} vertical={false} />
        <XAxis dataKey={x} {...axisProps} />
        <YAxis {...axisProps} axisLine={false} width={48} allowDecimals={digits > 0} tickFormatter={(v: number) => compact(v)} />
        <Tooltip content={(p) => <ChartTooltip {...(p as TooltipContentProps<number, string>)} unit={unit} series={series} digits={digits} />} cursor={{ fill: "rgba(11,11,11,0.04)" }} />
        {series.length > 1 && <Legend iconType="square" itemSorter={null} formatter={legendText} wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} stackId="stack" fill={s.color} maxBarSize={24}
            stroke={CHART.surface} strokeWidth={2} radius={i === series.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Horizontal magnitude bars for a breakdown (e.g. by category or facility). */
export function BreakdownBars({ data, color, unit, digits = 2 }: {
  data: { label: string; value: number }[]; color: string; unit?: string; digits?: number;
}) {
  const height = Math.max(120, data.length * 34 + 24);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, bottom: 4, left: 8 }}>
        <CartesianGrid stroke={CHART.grid} strokeWidth={1} horizontal={false} />
        <XAxis type="number" {...axisProps} tickFormatter={(v: number) => compact(v)} />
        <YAxis type="category" dataKey="label" {...axisProps} axisLine={false} width={180} />
        <Tooltip formatter={(v) => [`${fmt(v, digits)}${unit ? ` ${unit}` : ""}`, ""]} separator="" cursor={{ fill: "rgba(11,11,11,0.04)" }} />
        <Bar dataKey="value" fill={color} maxBarSize={24} radius={[0, 4, 4, 0]} isAnimationActive={false}
          label={{ position: "right", fill: CHART.secondary, fontSize: 11, formatter: (v: unknown) => compact(Number(v)) }} />
      </BarChart>
    </ResponsiveContainer>
  );
}
