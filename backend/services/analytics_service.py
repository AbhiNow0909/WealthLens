"""
Analytics service — orchestrates data fetch + metric computation.

Routers and the LangGraph analytics node call into here. This module owns all
Supabase access for analytics; the pure math lives in agents/nodes/analytics.py.

All returns/XIRR/alpha/drawdown are returned in *percent* (e.g. 12.34 == 12.34%)
to match the frontend formatters. Beta/Sharpe/Sortino are plain ratios.
"""

from __future__ import annotations

import logging
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
    compute_trailing_return,
    compute_xirr,
    daily_returns,
    nav_rows_to_series,
)

logger = logging.getLogger(__name__)

BENCHMARK_INDEX = "nifty50"


def _pct(value: Optional[float]) -> Optional[float]:
    """Fraction → percent, rounded to 4 dp. Passes through None."""
    if value is None:
        return None
    return round(value * 100.0, 4)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_nav_series(isin: str) -> pd.Series:
    supabase = get_supabase()
    rows = (
        supabase.table("nav_history")
        .select("nav_date,nav")
        .eq("isin", isin)
        .order("nav_date")
        .execute()
        .data
        or []
    )
    return nav_rows_to_series(rows)


def _load_benchmark_series() -> pd.Series:
    supabase = get_supabase()
    rows = (
        supabase.table("benchmark_history")
        .select("price_date,close_price")
        .eq("index_name", BENCHMARK_INDEX)
        .order("price_date")
        .execute()
        .data
        or []
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
    return query.order("transaction_date").execute().data or []


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
        "beta": round(beta, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": _pct(max_dd),
        "expense_ratio": 0.0,  # not available from MFApi; placeholder for Step 5
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
        "max_drawdown": metrics["max_drawdown"],
        "expense_ratio": metrics["expense_ratio"],
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


async def get_rolling_returns(isin: str) -> list[dict]:
    """
    Rolling 1-year return time series for a fund (for the fund detail chart).
    Returns [{date: 'YYYY-MM-DD', value: percent}] sorted ascending by date.
    """
    nav_series = _load_nav_series(isin)
    series = compute_rolling_returns(nav_series, window_days=365)
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
