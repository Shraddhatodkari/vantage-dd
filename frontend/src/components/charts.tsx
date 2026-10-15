// Financial trend charts. Rules (see docs/METHODOLOGY.md, "Charts"): one y-axis per chart (no dual axes),
// one measure per chart, missing values are gaps (never drawn as 0), a legend whenever there are 2+ series,
// a tooltip with the formatted and exact value, and every chart has a table view elsewhere on the same page.
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtValue } from "../lib/format";

// Validated categorical slots (dataviz default palette, light mode): blue, orange, aqua — checked with
// validate_palette.js (CVD ΔE ≥ 9.2, normal-vision ΔE ≥ 27.6); contrast relief = legend + table view.
// six distinct, colour-blind-safe series colours (five verified companies + headroom); cycled if ever exceeded
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#8b5cf6", "#334155", "#c9a227"];

export interface Series { key: string; label: string }
type Row = Record<string, number | string | null>;

function Tip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-xs">
      <div className="font-medium text-ink-900">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-slate-700">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
          {p.name}: <b>{p.value == null ? "n/a" : fmtValue(p.value, unit)}</b>
          {typeof p.value === "number" && <span className="text-slate-400">({p.value.toLocaleString("en-US", { maximumFractionDigits: 3 })})</span>}
        </div>))}
    </div>);
}

export function TrendChart({ title, data, series, unit, kind = "line", log = false, note, height = 190, testId }:
  { title: string; data: Row[]; series: Series[]; unit: string; kind?: "line" | "bar"; log?: boolean; note?: string; height?: number; testId?: string }) {
  const hasData = data.some(r => series.some(s => typeof r[s.key] === "number"));
  // axis ticks: round numbers only (the exact values are in the tooltip and the table)
  const tick = (v: number) => unit === "USD_millions" ? `${v < 0 ? "-" : ""}$${Math.round(Math.abs(v)).toLocaleString("en-US")}M`
    : unit === "pct" ? `${Math.round(v)}%` : unit === "x" ? `${Math.abs(v) >= 10 ? Math.round(v).toLocaleString("en-US") : v.toFixed(1)}x`
    : fmtValue(v, unit);
  const common = { data, margin: { top: 8, right: 12, left: 4, bottom: 0 } };
  const axes = [
    <CartesianGrid key="g" stroke="#eef2f6" vertical={false} />,
    <XAxis key="x" dataKey="year" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={{ stroke: "#cbd5e1" }} tickLine={false} />,
    <YAxis key="y" tick={{ fontSize: 11, fill: "#64748b" }} tickFormatter={tick} width={72} axisLine={false} tickLine={false}
      scale={log ? "log" : "auto"} domain={log ? ["auto", "auto"] : undefined} allowDataOverflow={log} />,
    <Tooltip key="t" content={<Tip unit={unit} />} cursor={{ stroke: "#94a3b8", fill: "#f1f5f9" }} />,
    ...(series.length > 1 ? [<Legend key="l" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }}
      formatter={(v: string) => <span style={{ color: "#334155" }}>{v}</span>} />] : []),
    ...(!log ? [<ReferenceLine key="z" y={0} stroke="#94a3b8" />] : []),
  ];
  return (
    <figure className="card p-4" data-testid={testId}>
      <figcaption className="text-sm font-semibold text-ink-900">{title}</figcaption>
      {note && <p className="text-[11px] text-slate-500">{note}</p>}
      {!hasData ? <p className="py-10 text-center text-xs text-slate-400">No data for this measure (n/a — not shown as zero).</p> :
        <ResponsiveContainer width="100%" height={height}>
          {kind === "bar" ? (
            <BarChart {...common} barGap={2}>{axes}
              {series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.label} fill={SERIES[i % SERIES.length]} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />)}
            </BarChart>) : (
            <LineChart {...common}>{axes}
              {series.map((s, i) => <Line key={s.key} dataKey={s.key} name={s.label} stroke={SERIES[i % SERIES.length]} strokeWidth={2} dot={{ r: 4 }}
                connectNulls={false} isAnimationActive={false} />)}
            </LineChart>)}
        </ResponsiveContainer>}
    </figure>);
}

// facts -> rows keyed by fiscal year, with null for missing / not meaningful values
export function rowsFor(facts: { metric: string; fiscal_year: number; value: number | null }[], metrics: Record<string, string>): Row[] {
  const years = [...new Set(facts.map(f => f.fiscal_year))].sort();
  return years.map(y => {
    const r: Row = { year: `FY${y}` };
    for (const [m, key] of Object.entries(metrics)) {
      const f = facts.find(x => x.metric === m && x.fiscal_year === y);
      r[key] = f && f.value != null ? f.value : null;
    }
    return r;
  });
}
