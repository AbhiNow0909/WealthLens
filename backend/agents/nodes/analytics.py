"""
Analytics engine — pure financial-math functions plus the LangGraph node.

All formula functions are side-effect free and return values in *natural math
units* (fractions, not percentages). The service layer (services/analytics_service.py)
converts to display units and persists to the fund_metrics cache.

Conventions:
  - Daily returns are simple pct-change fractions.
  - Trailing returns are CAGR (annualised) for periods > 1 year, simple
    point-to-point otherwise.
  - Risk-free rate defaults to 6.5% p.a. (configurable via RISK_FREE_RATE env).
  - Annualisation uses 252 trading days.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import linregress

from agents.state import PortfolioState

TRADING_DAYS = 252
DEFAULT_RISK_FREE_RATE = float(os.environ.get("RISK_FREE_RATE", "0.065"))

# Trailing-return windows in calendar days
TRAILING_WINDOWS = {
    "1w": 7,
    "1m": 30,
    "3m": 91,
    "6m": 182,
    "1y": 365,
    "3y": 1095,
    "5y": 1825,
}


# ---------------------------------------------------------------------------
# XIRR
# ---------------------------------------------------------------------------

def _xnpv(rate: float, cashflows: list[tuple[date, float]]) -> float:
    """Net present value of dated cashflows at the given annual rate."""
    t0 = min(d for d, _ in cashflows)
    return sum(
        amount / (1.0 + rate) ** ((d - t0).days / 365.0)
        for d, amount in cashflows
    )


def compute_xirr(cashflows: list[tuple[date, float]]) -> float:
    """
    Internal rate of return for irregularly-spaced cashflows.

    Sign convention: money leaving the investor (purchases) is negative,
    money returning (redemptions, terminal current value) is positive.
    Returns an annualised fraction (0.12 == 12%). Returns 0.0 if it cannot
    be solved (e.g. all flows same sign, or no convergence).
    """
    if len(cashflows) < 2:
        return 0.0
    amounts = [a for _, a in cashflows]
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        return 0.0
    try:
        return float(brentq(lambda r: _xnpv(r, cashflows), -0.999999, 1000.0))
    except (ValueError, RuntimeError):
        return 0.0


def build_cashflows(
    transactions: list[dict],
    current_value: float,
    as_of: Optional[date] = None,
) -> list[tuple[date, float]]:
    """
    Convert transaction rows into signed dated cashflows for XIRR.

    `transactions` rows: {transaction_date, transaction_type, amount}.
    The terminal current_value is appended as a positive flow at `as_of`.
    """
    as_of = as_of or date.today()
    outflow_types = {"purchase", "switch_in"}
    inflow_types = {"redemption", "switch_out", "dividend"}

    cashflows: list[tuple[date, float]] = []
    for t in transactions:
        amount = float(t.get("amount") or 0.0)
        if amount == 0.0:
            continue
        ttype = t.get("transaction_type", "purchase")
        d = _to_date(t.get("transaction_date"))
        if d is None:
            continue
        if ttype in outflow_types:
            cashflows.append((d, -abs(amount)))
        elif ttype in inflow_types:
            cashflows.append((d, abs(amount)))

    if current_value and current_value > 0:
        cashflows.append((as_of, float(current_value)))
    return cashflows


# ---------------------------------------------------------------------------
# Trailing returns
# ---------------------------------------------------------------------------

def compute_trailing_return(nav_series: pd.Series, days: int) -> Optional[float]:
    """
    Point-to-point return over the trailing `days` calendar days.
    CAGR (annualised) for windows over a year, simple return otherwise.

    `nav_series` is indexed by date (ascending). Returns a fraction, or None
    when there isn't enough history to cover the window.
    """
    if nav_series.empty:
        return None
    nav_series = nav_series.sort_index()
    end_date = nav_series.index[-1]
    end_nav = float(nav_series.iloc[-1])
    target = end_date - timedelta(days=days)

    prior = nav_series[nav_series.index <= target]
    if prior.empty:
        return None  # not enough history
    start_nav = float(prior.iloc[-1])
    if start_nav <= 0:
        return None

    if days > 365:
        years = days / 365.0
        return (end_nav / start_nav) ** (1.0 / years) - 1.0
    return end_nav / start_nav - 1.0


def compute_rolling_returns(
    nav_series: pd.Series,
    window_days: int = 365,
    max_points: int = 300,
) -> list[tuple[pd.Timestamp, float]]:
    """
    Trailing `window_days` simple return computed at each date in the series,
    forming a time series (e.g. rolling 1-year returns). Returns a list of
    (date, return_fraction), downsampled to at most `max_points` points.
    """
    nav_series = nav_series.dropna().sort_index()
    n = len(nav_series)
    if n < 2:
        return []

    dates = nav_series.index
    values = nav_series.to_numpy()
    date_ints = dates.astype(np.int64)  # ns since epoch
    window_ns = window_days * 86_400 * 1_000_000_000

    results: list[tuple[pd.Timestamp, float]] = []
    for i in range(n):
        target = date_ints[i] - window_ns
        j = int(np.searchsorted(date_ints, target, side="right")) - 1
        if j < 0:
            continue
        start = values[j]
        if start > 0:
            results.append((dates[i], float(values[i] / start - 1.0)))

    if len(results) > max_points:
        step = len(results) // max_points + 1
        results = results[::step]
    return results


# ---------------------------------------------------------------------------
# Risk metrics
# ---------------------------------------------------------------------------

def compute_alpha_beta(
    fund_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> tuple[float, float]:
    """
    OLS regression of fund daily returns on benchmark daily returns.
    Returns (annualised_alpha_fraction, beta). Both 0.0 if insufficient data.
    """
    df = pd.concat([fund_returns, benchmark_returns], axis=1, join="inner").dropna()
    if len(df) < 30:
        return 0.0, 0.0
    fund = df.iloc[:, 0].to_numpy()
    bench = df.iloc[:, 1].to_numpy()
    if np.std(bench) == 0:
        return 0.0, 0.0
    slope, intercept, *_ = linregress(bench, fund)
    alpha_annual = intercept * TRADING_DAYS
    return float(alpha_annual), float(slope)


def compute_sharpe(returns: pd.Series, risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> float:
    """Annualised Sharpe ratio from daily returns."""
    returns = returns.dropna()
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / TRADING_DAYS
    std = excess.std()
    if np.isnan(std) or std < 1e-12:  # flat series → Sharpe undefined
        return 0.0
    return float((excess.mean() / std) * np.sqrt(TRADING_DAYS))


def compute_sortino(returns: pd.Series, risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> float:
    """Annualised Sortino ratio (downside deviation only) from daily returns."""
    returns = returns.dropna()
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / TRADING_DAYS
    downside = excess[excess < 0].std()
    if np.isnan(downside) or downside < 1e-12:  # no meaningful downside → undefined
        return 0.0
    return float((excess.mean() / downside) * np.sqrt(TRADING_DAYS))


def compute_max_drawdown(nav_series: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a fraction (negative). 0.0 if empty."""
    nav_series = nav_series.dropna().sort_index()
    if nav_series.empty:
        return 0.0
    roll_max = nav_series.cummax()
    drawdown = nav_series / roll_max - 1.0
    return float(drawdown.min())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def nav_rows_to_series(rows: list[dict]) -> pd.Series:
    """Convert [{nav_date, nav}] rows to a date-indexed pandas Series (ascending)."""
    if not rows:
        return pd.Series(dtype="float64")
    df = pd.DataFrame(rows)
    df["nav_date"] = pd.to_datetime(df["nav_date"])
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    s = df.set_index("nav_date")["nav"].dropna().sort_index()
    return s


def daily_returns(nav_series: pd.Series) -> pd.Series:
    """Simple daily pct-change returns from a NAV series."""
    return nav_series.sort_index().pct_change().dropna()


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

async def run(state: PortfolioState) -> PortfolioState:
    """
    Compute metrics for the user's whole portfolio and place them in state.
    Delegates the data-fetch + orchestration to the analytics service.
    """
    from services.analytics_service import compute_portfolio_metrics

    user_id = state["user_id"]
    metrics = await compute_portfolio_metrics(user_id)
    return {**state, "metrics": metrics}
