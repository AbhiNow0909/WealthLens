"""
Analytics service — orchestrates data fetch + metric computation.

Routers and the LangGraph analytics node call into here. This module owns all
Supabase access for analytics; the pure math lives in agents/nodes/analytics.py.

All returns/XIRR/alpha/drawdown are returned in *percent* (e.g. 12.34 == 12.34%)
to match the frontend formatters. Beta/Sharpe/Sortino are plain ratios.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import pandas as pd

from services.supabase_client import get_supabase
from agents.nodes.analytics import (
    TRAILING_WINDOWS,
    build_cashflows,
    compute_alpha_beta,
    compute_max_drawdown,
    compute_rolling_returns,
    compute_sharpe,
    compute_sortino,
    compute_treynor,
    compute_trailing_return,
    compute_xirr,
    daily_returns,
    nav_rows_to_series,
)

logger = logging.getLogger(__name__)

BENCHMARK_INDEX = "nifty50"


def _pct(value: Optional[float]) -> Optional[float]:
    """Fraction → percent, rounded to 4 dp. None for null/non-finite (NaN/inf)."""
    if value is None:
        return None
    f = float(value)
    if not math.isfinite(f):
        return None
    return round(f * 100.0, 4)


def _num(value: Optional[float], decimals: int = 4) -> Optional[float]:
    """Round a ratio metric; None for null/non-finite so JSON stays valid."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, decimals)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_PAGE = 1000  # Supabase/PostgREST returns at most 1000 rows per request


def _fetch_all(table: str, columns: str, eq_col: str, eq_val: str, order_col: str) -> list[dict]:
    """
    Fetch ALL matching rows, paging past Supabase's 1000-row response cap.
    Without this, ordered-ascending queries silently drop the newest rows for
    funds with more than 1000 NAV points (years of daily history).
    """
    supabase = get_supabase()
    rows: list[dict] = []
    start = 0
    while True:
        chunk = (
            supabase.table(table)
            .select(columns)
            .eq(eq_col, eq_val)
            .order(order_col)
            .range(start, start + _PAGE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(chunk)
        if len(chunk) < _PAGE:
            break
        start += _PAGE
    return rows


def _load_nav_series(isin: str) -> pd.Series:
    rows = _fetch_all("nav_history", "nav_date,nav", "isin", isin, "nav_date")
    return nav_rows_to_series(rows)


def _load_benchmark_series() -> pd.Series:
    rows = _fetch_all(
        "benchmark_history", "price_date,close_price", "index_name", BENCHMARK_INDEX, "price_date"
    )
    # Reuse nav_rows_to_series by renaming columns
    normalized = [{"nav_date": r["price_date"], "nav": r["close_price"]} for r in rows]
    return nav_rows_to_series(normalized)


def _load_holdings(user_id: str) -> list[dict]:
    supabase = get_supabase()
    return (
        supabase.table("holdings")
        .select("isin,scheme_name,units_held,average_nav,current_nav,current_value,invested_value")
        .eq("user_id", user_id)
        .order("scheme_name")
        .execute()
        .data
        or []
    )


def _load_transactions(user_id: str, isin: Optional[str] = None) -> list[dict]:
    supabase = get_supabase()
    query = (
        supabase.table("transactions")
        .select("isin,transaction_date,transaction_type,amount,units,nav")
        .eq("user_id", user_id)
    )
    if isin:
        query = query.eq("isin", isin)
    rows = query.order("transaction_date").execute().data or []

    # De-duplicate: re-uploading the same CAS inserts identical transaction rows.
    # Two rows with the same isin/date/type/amount/units are duplicates, not two
    # genuine same-day trades — drop the repeats so sums (invested, XIRR) are correct.
    seen: set = set()
    deduped: list[dict] = []
    for r in rows:
        key = (
            r.get("isin"),
            str(r.get("transaction_date")),
            r.get("transaction_type"),
            float(r.get("amount") or 0),
            float(r.get("units") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


# ---------------------------------------------------------------------------
# Per-fund metrics
# ---------------------------------------------------------------------------

def _compute_one_fund(
    holding: dict,
    transactions: list[dict],
    benchmark_returns: pd.Series,
) -> dict:
    isin = holding["isin"]
    nav_series = _load_nav_series(isin)

    # Trailing returns
    trailing = {}
    for label, days in TRAILING_WINDOWS.items():
        trailing[f"trailing_{label}"] = _pct(compute_trailing_return(nav_series, days))

    # Risk metrics
    fund_returns = daily_returns(nav_series)
    alpha, beta = compute_alpha_beta(fund_returns, benchmark_returns)
    sharpe = compute_sharpe(fund_returns)
    sortino = compute_sortino(fund_returns)
    treynor = compute_treynor(fund_returns, beta)
    max_dd = compute_max_drawdown(nav_series)

    # XIRR from this fund's cashflows
    cashflows = build_cashflows(transactions, holding.get("current_value") or 0.0)
    xirr = compute_xirr(cashflows)

    return {
        "isin": isin,
        "scheme_name": holding.get("scheme_name", ""),
        "xirr": _pct(xirr),
        **trailing,
        "alpha": _pct(alpha),
        "beta": _num(beta),
        "sharpe_ratio": _num(sharpe),
        "sortino_ratio": _num(sortino),
        "treynor_ratio": _pct(treynor),
        "max_drawdown": _pct(max_dd),
        # Expense & turnover are fund-factsheet figures, not derivable from NAV
        # history — surfaced as None (UI shows "—") until a data source is added.
        "expense_ratio": None,
        "turnover_ratio": None,
    }


def _persist_metrics(user_id: str, metrics: dict) -> None:
    """Upsert a computed fund's metrics into the fund_metrics cache."""
    supabase = get_supabase()
    row = {
        "user_id": user_id,
        "isin": metrics["isin"],
        "xirr": metrics["xirr"],
        "trailing_1w": metrics.get("trailing_1w"),
        "trailing_1m": metrics.get("trailing_1m"),
        "trailing_3m": metrics.get("trailing_3m"),
        "trailing_6m": metrics.get("trailing_6m"),
        "trailing_1y": metrics.get("trailing_1y"),
        "trailing_3y": metrics.get("trailing_3y"),
        "trailing_5y": metrics.get("trailing_5y"),
        "alpha": metrics["alpha"],
        "beta": metrics["beta"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "sortino_ratio": metrics["sortino_ratio"],
        "treynor_ratio": metrics.get("treynor_ratio"),
        "max_drawdown": metrics["max_drawdown"],
        "expense_ratio": metrics["expense_ratio"],
        "turnover_ratio": metrics.get("turnover_ratio"),
        "computed_at": "now()",
    }
    try:
        supabase.table("fund_metrics").upsert(row, on_conflict="user_id,isin").execute()
    except Exception as exc:
        logger.warning("Failed to cache fund_metrics for %s: %s", metrics["isin"], exc)


# ---------------------------------------------------------------------------
# Public API (called by routers and the agent node)
# ---------------------------------------------------------------------------

async def get_fund_metrics(user_id: str, isin: str) -> dict:
    """Full metrics for a single fund."""
    holdings = _load_holdings(user_id)
    holding = next((h for h in holdings if h["isin"] == isin), None)
    if not holding:
        return {}
    benchmark_returns = daily_returns(_load_benchmark_series())
    txns = _load_transactions(user_id, isin)
    metrics = _compute_one_fund(holding, txns, benchmark_returns)
    _persist_metrics(user_id, metrics)
    return metrics


# Supported rolling-window labels → calendar days
ROLLING_WINDOWS = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 1095}

# NAV price-chart ranges → calendar days ("max" = full history)
NAV_RANGES = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 1095, "max": None}


async def get_nav_series(isin: str, time_range: str = "1y") -> list[dict]:
    """
    NAV price series for a fund over the given range (1m/3m/6m/1y/3y/max),
    downsampled to ~300 points. Returns [{nav_date, nav}] ascending by date.
    """
    series = _load_nav_series(isin)
    if series.empty:
        return []

    days = NAV_RANGES.get(time_range.lower(), 365)
    if days is not None:
        cutoff = series.index[-1] - pd.Timedelta(days=days)
        series = series[series.index >= cutoff]

    # Downsample wide ranges so the payload/chart stays light, keeping the last
    if len(series) > 300:
        step = len(series) // 300 + 1
        idx = list(range(0, len(series), step))
        if idx[-1] != len(series) - 1:
            idx.append(len(series) - 1)
        series = series.iloc[idx]

    return [
        {"nav_date": d.strftime("%Y-%m-%d"), "nav": round(float(v), 4)}
        for d, v in series.items()
    ]


def _unit_delta(txn: dict) -> float:
    u = float(txn.get("units") or 0)
    return -u if txn.get("transaction_type") in ("redemption", "switch_out") else u


def _cost_delta(txn: dict) -> float:
    """Net contribution: purchases add, redemptions subtract, dividends ignored."""
    a = float(txn.get("amount") or 0)
    ttype = txn.get("transaction_type")
    if ttype in ("purchase", "switch_in"):
        return a
    if ttype in ("redemption", "switch_out"):
        return -a
    return 0.0


async def get_fund_performance(user_id: str, isin: str, time_range: str = "1y") -> list[dict]:
    """
    Invested-vs-value time series for a fund:
      - value    = cumulative units held on that date × NAV
      - invested = cumulative net amount contributed up to that date

    Pre-statement holdings (when the CAS history is partial) are seeded as an
    opening position so the series ENDS at the true units_held / invested_value.
    Returns [{date, invested, value}] over the requested range.
    """
    series = _load_nav_series(isin)
    if series.empty:
        return []

    holding = next((h for h in _load_holdings(user_id) if h["isin"] == isin), None)
    units_held = float(holding.get("units_held") or 0) if holding else 0.0
    invested_value = float(holding.get("invested_value") or 0) if holding else 0.0

    txns = _load_transactions(user_id, isin)
    parsed = sorted(
        (
            (str(t.get("transaction_date"))[:10], _unit_delta(t), _cost_delta(t))
            for t in txns
            if t.get("transaction_date")
        ),
        key=lambda x: x[0],
    )

    # Opening position = current totals minus everything we have transactions for
    opening_units = max(units_held - sum(p[1] for p in parsed), 0.0)
    opening_cost = max(invested_value - sum(p[2] for p in parsed), 0.0)

    running_units = opening_units
    running_cost = opening_cost
    ti = 0
    rows: list[tuple] = []
    for d, nav in series.items():
        dstr = d.strftime("%Y-%m-%d")
        while ti < len(parsed) and parsed[ti][0] <= dstr:
            running_units += parsed[ti][1]
            running_cost += parsed[ti][2]
            ti += 1
        rows.append((d, dstr, running_cost, running_units * float(nav)))

    # Slice to range (after accumulating, so the range start has correct totals)
    days = NAV_RANGES.get(time_range.lower(), 365)
    if days is not None:
        cutoff = series.index[-1] - pd.Timedelta(days=days)
        rows = [r for r in rows if r[0] >= cutoff]

    if len(rows) > 300:
        step = len(rows) // 300 + 1
        sampled = rows[::step]
        if sampled[-1] is not rows[-1]:
            sampled.append(rows[-1])  # always keep the latest point (current totals)
        rows = sampled

    return [
        {"date": dstr, "invested": round(cost, 2), "value": round(val, 2)}
        for (_, dstr, cost, val) in rows
    ]


async def get_rolling_returns(isin: str, window: str = "1y") -> list[dict]:
    """
    Rolling return time series for a fund over the given window (1m/3m/6m/1y/3y).
    Each point is the trailing-window return ending on that date.
    Returns [{date: 'YYYY-MM-DD', value: percent}] sorted ascending by date.
    """
    window_days = ROLLING_WINDOWS.get(window.lower(), 365)
    nav_series = _load_nav_series(isin)
    series = compute_rolling_returns(nav_series, window_days=window_days)
    return [
        {"date": d.strftime("%Y-%m-%d"), "value": round(r * 100.0, 4)}
        for d, r in series
    ]


async def get_all_fund_metrics(user_id: str, isins: Optional[list[str]] = None) -> list[dict]:
    """Metrics for all (or a subset of) the user's funds — used by /compare."""
    holdings = _load_holdings(user_id)
    if isins:
        wanted = set(isins)
        holdings = [h for h in holdings if h["isin"] in wanted]
    if not holdings:
        return []

    benchmark_returns = daily_returns(_load_benchmark_series())
    all_txns = _load_transactions(user_id)
    txns_by_isin: dict[str, list[dict]] = {}
    for t in all_txns:
        txns_by_isin.setdefault(t["isin"], []).append(t)

    results = []
    for h in holdings:
        metrics = _compute_one_fund(h, txns_by_isin.get(h["isin"], []), benchmark_returns)
        _persist_metrics(user_id, metrics)
        results.append(metrics)
    return results


async def get_trailing_returns_table(user_id: str) -> list[dict]:
    """Compact trailing-returns table for every fund (frontend TrailingReturnsRow)."""
    all_metrics = await get_all_fund_metrics(user_id)
    table = []
    for m in all_metrics:
        table.append({
            "isin": m["isin"],
            "name": m["scheme_name"],
            "1w": m.get("trailing_1w"),
            "1m": m.get("trailing_1m"),
            "3m": m.get("trailing_3m"),
            "6m": m.get("trailing_6m"),
            "1y": m.get("trailing_1y"),
            "3y": m.get("trailing_3y"),
            "5y": m.get("trailing_5y"),
        })
    return table


async def compute_portfolio_xirr(user_id: str) -> float:
    """
    Portfolio-level XIRR: all transactions across all funds as outflows/inflows,
    plus the total current portfolio value as the terminal inflow. Returns percent.
    """
    holdings = _load_holdings(user_id)
    total_value = sum(float(h.get("current_value") or 0.0) for h in holdings)
    txns = _load_transactions(user_id)
    cashflows = build_cashflows(txns, total_value)
    return round(compute_xirr(cashflows) * 100.0, 4)


async def compute_portfolio_metrics(user_id: str) -> dict:
    """
    Whole-portfolio metrics bundle for the LangGraph analytics node.
    Includes per-fund metrics, portfolio XIRR, and aggregate value/gain.
    """
    funds = await get_all_fund_metrics(user_id)
    holdings = _load_holdings(user_id)
    total_value = sum(float(h.get("current_value") or 0.0) for h in holdings)
    total_invested = sum(float(h.get("invested_value") or 0.0) for h in holdings)
    total_gain = total_value - total_invested
    portfolio_xirr = await compute_portfolio_xirr(user_id)

    return {
        "portfolio_xirr": portfolio_xirr,
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "total_gain": round(total_gain, 2),
        "total_gain_pct": round(total_gain / total_invested * 100, 4) if total_invested > 0 else 0.0,
        "funds": funds,
    }
