"""The single authoritative path for a deal's numbers:
reported facts (SEC XBRL for real companies, uploaded CSV for others) -> FinancialFact rows ->
deterministic calculations (also stored as FinancialFact rows) -> agents, API, UI and reports."""
from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy.orm import Session

from app.analytics.metrics import Calc, FactRef, Facts, compute_all
from app.db.models import Deal, FinancialFact

CSV_COLUMNS = {  # csv column -> (metric, unit)
    "revenue_musd": ("revenue", "USD_millions"), "ebitda_musd": ("ebitda", "USD_millions"),
    "operating_income_musd": ("operating_income", "USD_millions"),
    "depreciation_musd": ("depreciation_amortization", "USD_millions"),
    "interest_expense_musd": ("interest_expense", "USD_millions"), "net_income_musd": ("net_income", "USD_millions"),
    "total_debt_musd": ("total_debt", "USD_millions"), "cash_musd": ("cash", "USD_millions"),
    "current_assets_musd": ("current_assets", "USD_millions"),
    "current_liabilities_musd": ("current_liabilities", "USD_millions"),
    "receivables_musd": ("receivables", "USD_millions"),
    "operating_cash_flow_musd": ("operating_cash_flow", "USD_millions"), "capex_musd": ("capex", "USD_millions"),
    "cogs_musd": ("cogs", "USD_millions"), "opex_musd": ("operating_expenses", "USD_millions"),
    "processed_volume_busd": ("processed_volume", "USD_billions"),
    "chargeback_ratio_pct": ("chargeback_ratio_pct", "pct"), "fraud_loss_bps": ("fraud_loss_bps", "bps"),
}


class FinancialsError(ValueError):
    pass


def parse_financials_csv(text: str, filename: str) -> list[dict]:
    """Validate and parse a financial-statements CSV. Unknown columns are rejected (no silent guessing);
    blank cells become 'missing', never zero."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "fiscal_year" not in reader.fieldnames:
        raise FinancialsError("CSV must have a 'fiscal_year' column")
    unknown = [c for c in reader.fieldnames if c != "fiscal_year" and c not in CSV_COLUMNS]
    if unknown:
        raise FinancialsError(f"Unknown CSV columns: {unknown}. Allowed: {sorted(CSV_COLUMNS)}")
    rows, years = [], set()
    for line_no, row in enumerate(reader, start=2):
        try:
            fy = int(row["fiscal_year"])
        except (TypeError, ValueError) as exc:
            raise FinancialsError(f"line {line_no}: invalid fiscal_year {row['fiscal_year']!r}") from exc
        if fy in years:
            raise FinancialsError(f"line {line_no}: duplicate fiscal_year {fy}")
        years.add(fy)
        for col, (metric, unit) in CSV_COLUMNS.items():
            if col not in row:
                continue
            raw = (row[col] or "").strip()
            if raw == "":
                rows.append({"metric": metric, "fiscal_year": fy, "value": None, "unit": unit, "status": "missing",
                             "source_document": filename, "locator": f"line {line_no}, column {col}"})
                continue
            try:
                val = float(raw)
            except ValueError as exc:
                raise FinancialsError(f"line {line_no}: {col}={raw!r} is not a number") from exc
            rows.append({"metric": metric, "fiscal_year": fy, "value": val, "unit": unit, "status": "ok",
                         "source_document": filename, "locator": f"line {line_no}, column {col}"})
    return rows


def store_csv_facts(db: Session, deal: Deal, text: str, filename: str) -> int:
    rows = parse_financials_csv(text, filename)
    db.query(FinancialFact).filter_by(deal_id=deal.id).delete()
    for r in rows:
        db.add(FinancialFact(deal_id=deal.id, metric=r["metric"], fiscal_year=r["fiscal_year"], value=r["value"],
                             unit=r["unit"], currency="USD" if r["unit"].startswith("USD") else None,
                             kind="reported", status=r["status"], source_document=filename,
                             status_reason=r["locator"]))
    db.flush()
    materialize_calculations(db, deal)
    return len(rows)


def reported_facts(db: Session, deal_id: str) -> Facts:
    out: Facts = {}
    for f in db.query(FinancialFact).filter_by(deal_id=deal_id, kind="reported").all():
        out[(f.metric, f.fiscal_year)] = FactRef(f.metric, f.fiscal_year, f.value, f.unit, fact_ref(f))
    return out


def fact_ref(f: FinancialFact) -> dict:
    return {"fact_id": f.id, "xbrl_tag": f.xbrl_tag, "accession": f.accession, "form": f.form,
            "filed": f.filed.isoformat() if f.filed else None,
            "period_end": f.period_end.isoformat() if f.period_end else None,
            "source_document": f.source_document, "source_record_id": f.source_record_id}


def materialize_calculations(db: Session, deal: Deal) -> list[Calc]:
    rep = reported_facts(db, deal.id)
    years = sorted({y for _, y in rep})
    calcs = compute_all(rep, years)
    db.query(FinancialFact).filter_by(deal_id=deal.id, kind="calculated").delete()
    period = {y: f.ref.get("period_end") for (m, y), f in rep.items() if f.ref.get("period_end")}
    for (metric, y), c in calcs.items():
        db.add(FinancialFact(deal_id=deal.id, metric=metric, fiscal_year=y, value=c.value, unit=c.unit,
                             currency="USD" if c.unit.startswith("USD") else None, kind="calculated",
                             status=c.status, status_reason=c.reason, formula=c.formula, inputs=c.inputs,
                             period_end=date.fromisoformat(period[y]) if period.get(y) else None))
    db.flush()
    return list(calcs.values())


def all_facts(db: Session, deal_id: str) -> dict[tuple[str, int], FinancialFact]:
    return {(f.metric, f.fiscal_year): f for f in db.query(FinancialFact).filter_by(deal_id=deal_id).all()}
