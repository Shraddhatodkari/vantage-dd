import { ExternalLink } from "lucide-react";
import type { Evidence } from "../lib/api";
import { METRIC_LABEL, fmtValue } from "../lib/format";

export function EvidenceItem({ e }: { e: Evidence }) {
  if (e.kind === "document_excerpt") {
    return (
      <blockquote className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
        <div className="mb-1 flex flex-wrap items-center gap-x-2 font-mono text-[11px] text-slate-500">
          <span>{e.filename}</span>
          {e.accession && <span>accession {e.accession}</span>}
          {e.locator && <span>chars {e.locator.start}–{e.locator.end}</span>}
          {e.source_url && <a className="inline-flex items-center gap-0.5 text-sky-700 hover:underline" href={e.source_url} target="_blank" rel="noreferrer noopener">source<ExternalLink className="h-3 w-3" /></a>}
        </div>
        <span className="whitespace-pre-wrap">“{e.excerpt}”</span>
      </blockquote>);
  }
  if (e.kind === "reported_fact") {
    return (
      <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
        <span className="font-medium">Reported:</span> {METRIC_LABEL[e.metric] ?? e.metric} FY{e.fiscal_year} = <b>{fmtValue(e.value, e.unit)}</b>
        <div className="font-mono text-[11px] text-slate-500">
          {e.xbrl_tag ? <>{e.xbrl_tag} · {e.form} {e.accession} · filed {e.filed}</> : <>from {e.source_document}</>}
          {e.source_url && <> · <a className="text-sky-700 hover:underline" href={e.source_url} target="_blank" rel="noreferrer noopener">SEC XBRL</a></>}
        </div>
      </div>);
  }
  if (e.kind === "calculation") {
    return (
      <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
        <span className="font-medium">Calculated:</span> {METRIC_LABEL[e.metric] ?? e.metric}{e.fiscal_year ? ` FY${e.fiscal_year}` : ""} ={" "}
        <b>{e.display ?? (Array.isArray(e.value) ? e.value.map((v: number) => (Math.round(v * 10) / 10).toString()).join(", ") : String(e.value))}</b>
        {e.formula && <div className="font-mono text-[11px] text-slate-500">{e.formula}</div>}
        {Array.isArray(e.inputs) && e.inputs.length > 0 && e.inputs[0].metric && (
          <div className="font-mono text-[11px] text-slate-500">inputs: {e.inputs.map((i: any) =>
            `${METRIC_LABEL[i.metric] ?? i.metric}${i.fiscal_year ? ` FY${i.fiscal_year}` : ""} = ${i.unit ? fmtValue(i.value, i.unit) : i.value}`).join("; ")}</div>)}
        {Array.isArray(e.inputs) && e.inputs.some((i: any) => typeof i.value === "number" && i.unit) && typeof e.value === "number" && (
          <div className="text-[11px] text-slate-400" data-testid="exact-values">exact: {e.inputs.filter((i: any) => typeof i.value === "number").map((i: any) =>
            i.value.toLocaleString("en-US", { maximumFractionDigits: 3 })).join("; ")} → {e.value.toLocaleString("en-US", { maximumFractionDigits: 4 })}
            {" "}(each displayed figure is rounded separately)</div>)}
      </div>);
  }
  if (e.kind === "assumption") {
    return <div className="rounded-lg border border-dashed border-slate-300 p-3 text-xs text-slate-600"><span className="font-medium">Assumption:</span> {e.name} = {e.value} ({e.basis})</div>;
  }
  if (e.kind === "macro_series") {
    return (
      <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
        <span className="font-medium">FRED {e.series_id}:</span> {e.observations.map((o: any) => `${o.date.slice(0, 7)} ${o.value}%`).join(" → ")}
        <div className="font-mono text-[11px] text-slate-500">retrieved {e.retrieved_at} · <a className="text-sky-700 hover:underline" href={`https://fred.stlouisfed.org/series/${e.series_id}`} target="_blank" rel="noreferrer noopener">FRED series</a></div>
      </div>);
  }
  return null;
}
