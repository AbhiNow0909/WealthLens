"""
LangGraph node: data_fetcher.

Loads nav_history and benchmark_history from Supabase for the current user's
holdings and puts them into state["nav_data"] for the analytics node.
"""

from __future__ import annotations

from agents.state import PortfolioState
from services.supabase_client import get_supabase


async def run(state: PortfolioState) -> PortfolioState:
    user_id: str = state.get("user_id", "")
    supabase = get_supabase()

    # Get the user's ISINs
    holdings_result = (
        supabase.table("holdings")
        .select("isin,units_held,invested_value")
        .eq("user_id", user_id)
        .execute()
    )
    holdings = holdings_result.data or []
    if not holdings:
        return {**state, "nav_data": {}}

    isins = [h["isin"] for h in holdings]

    # Fetch last 400 trading days (~18 months) of NAV history for each ISIN
    nav_data: dict[str, list[dict]] = {}
    for isin in isins:
        rows = (
            supabase.table("nav_history")
            .select("nav_date,nav")
            .eq("isin", isin)
            .order("nav_date", desc=True)
            .limit(400)
            .execute()
            .data or []
        )
        # Reverse so chronological order (oldest → newest)
        nav_data[isin] = list(reversed(rows))

    # Fetch benchmark (last 400 days)
    benchmark = (
        supabase.table("benchmark_history")
        .select("price_date,close_price")
        .eq("index_name", "nifty50")
        .order("price_date", desc=True)
        .limit(400)
        .execute()
        .data or []
    )
    benchmark = list(reversed(benchmark))

    return {
        **state,
        "nav_data": {
            "holdings": holdings,
            "nav_history": nav_data,
            "benchmark": benchmark,
        },
    }
