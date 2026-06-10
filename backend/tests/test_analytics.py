"""
Unit tests for the analytics formula functions.

Each test uses inputs whose expected output is derived independently of the
implementation (closed-form math), so they verify correctness, not just
regression stability.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from agents.nodes.analytics import (
    build_cashflows,
    compute_alpha_beta,
    compute_max_drawdown,
    compute_rolling_returns,
    compute_sharpe,
    compute_sortino,
    compute_trailing_return,
    compute_xirr,
)


# ---------------------------------------------------------------------------
# XIRR
# ---------------------------------------------------------------------------

def test_xirr_simple_10pct_over_one_year():
    # Invest ₹1000, receive ₹1100 exactly 365 days later → 10% annualised.
    cashflows = [
        (date(2023, 1, 1), -1000.0),
        (date(2024, 1, 1), 1100.0),  # 2023 is not a leap year → 365 days
    ]
    assert compute_xirr(cashflows) == pytest.approx(0.10, abs=1e-4)


def test_xirr_zero_when_no_gain():
    cashflows = [
        (date(2023, 1, 1), -1000.0),
        (date(2024, 1, 1), 1000.0),
    ]
    assert compute_xirr(cashflows) == pytest.approx(0.0, abs=1e-4)


def test_xirr_returns_zero_for_same_sign_flows():
    # All outflows → unsolvable → 0.0
    assert compute_xirr([(date(2023, 1, 1), -100.0), (date(2023, 6, 1), -100.0)]) == 0.0


def test_build_cashflows_sign_convention():
    txns = [
        {"transaction_date": "2023-01-01", "transaction_type": "purchase", "amount": 5000},
        {"transaction_date": "2023-06-01", "transaction_type": "redemption", "amount": 1000},
    ]
    flows = build_cashflows(txns, current_value=6000.0, as_of=date(2024, 1, 1))
    assert flows[0][1] == -5000.0     # purchase is outflow
    assert flows[1][1] == 1000.0      # redemption is inflow
    assert flows[-1] == (date(2024, 1, 1), 6000.0)  # terminal value appended


# ---------------------------------------------------------------------------
# Trailing returns
# ---------------------------------------------------------------------------

def test_trailing_return_simple_under_one_year():
    idx = pd.date_range("2023-01-01", periods=801, freq="D")
    nav = pd.Series(123.0, index=idx)          # filler values are irrelevant
    nav.iloc[700] = 100.0                       # value 100 days before the end
    nav.iloc[-1] = 150.0
    # window = 100 days → idx[-1] - 100 == idx[700]; simple return = 50%
    assert compute_trailing_return(nav, 100) == pytest.approx(0.50, abs=1e-6)


def test_trailing_return_cagr_over_two_years():
    idx = pd.date_range("2023-01-01", periods=801, freq="D")
    nav = pd.Series(123.0, index=idx)
    nav.iloc[70] = 100.0                        # 730 days before the end (idx[800]-730 == idx[70])
    nav.iloc[-1] = 200.0                        # doubled over 2 years
    # CAGR = 2^(1/2) - 1 ≈ 0.41421
    assert compute_trailing_return(nav, 730) == pytest.approx(2 ** 0.5 - 1, abs=1e-4)


def test_trailing_return_none_when_insufficient_history():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    nav = pd.Series(range(100, 110), index=idx, dtype="float64")
    assert compute_trailing_return(nav, 365) is None


# ---------------------------------------------------------------------------
# Rolling returns
# ---------------------------------------------------------------------------

def test_rolling_returns_flat_series_is_zero():
    idx = pd.date_range("2022-01-01", periods=400, freq="D")
    nav = pd.Series(100.0, index=idx)
    res = compute_rolling_returns(nav, window_days=365)
    # Points exist only for the 35 days that have a value 365 days earlier
    assert len(res) == 35
    assert all(abs(r) < 1e-12 for _, r in res)


def test_rolling_returns_known_endpoint():
    idx = pd.date_range("2022-01-01", periods=400, freq="D")
    nav = pd.Series(100.0, index=idx)
    nav.iloc[-1] = 120.0  # last day 20% above its value 365 days prior
    res = compute_rolling_returns(nav, window_days=365)
    assert res[-1][1] == pytest.approx(0.20, abs=1e-9)


def test_rolling_returns_empty_for_short_series():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    nav = pd.Series(range(100, 110), index=idx, dtype="float64")
    assert compute_rolling_returns(nav) == []


# ---------------------------------------------------------------------------
# Max drawdown
# ---------------------------------------------------------------------------

def test_max_drawdown_known_series():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    nav = pd.Series([100.0, 120.0, 90.0, 130.0], index=idx)
    # peak 120 → trough 90 = -25%
    assert compute_max_drawdown(nav) == pytest.approx(-0.25, abs=1e-9)


def test_max_drawdown_monotonic_increase_is_zero():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    nav = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=idx)
    assert compute_max_drawdown(nav) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Alpha / Beta
# ---------------------------------------------------------------------------

def test_beta_two_alpha_zero_when_fund_is_2x_benchmark():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2023-01-01", periods=300, freq="D")
    bench = pd.Series(rng.normal(0.0005, 0.01, 300), index=idx)
    fund = 2.0 * bench  # perfect linear relationship, no intercept
    alpha, beta = compute_alpha_beta(fund, bench)
    assert beta == pytest.approx(2.0, abs=1e-6)
    assert alpha == pytest.approx(0.0, abs=1e-6)


def test_alpha_beta_zero_when_insufficient_data():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    s = pd.Series(np.zeros(10), index=idx)
    assert compute_alpha_beta(s, s) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# Sharpe / Sortino
# ---------------------------------------------------------------------------

def test_sharpe_zero_for_constant_returns():
    # Zero volatility → guard returns 0.0
    s = pd.Series([0.001] * 50)
    assert compute_sharpe(s) == 0.0


def test_sharpe_matches_manual_formula():
    returns = pd.Series([0.01, -0.005, 0.02, 0.0, 0.015, -0.01])
    rf = 0.065
    excess = returns - rf / 252
    expected = (excess.mean() / excess.std()) * np.sqrt(252)
    assert compute_sharpe(returns, rf) == pytest.approx(expected, rel=1e-9)


def test_sortino_only_penalises_downside():
    returns = pd.Series([0.01, -0.005, 0.02, 0.0, 0.015, -0.01])
    rf = 0.065
    excess = returns - rf / 252
    downside = excess[excess < 0].std()
    expected = (excess.mean() / downside) * np.sqrt(252)
    assert compute_sortino(returns, rf) == pytest.approx(expected, rel=1e-9)


def test_sortino_zero_when_no_downside():
    s = pd.Series([0.02, 0.03, 0.01, 0.04])  # all above rf/252 → no downside deviation
    assert compute_sortino(s) == 0.0
