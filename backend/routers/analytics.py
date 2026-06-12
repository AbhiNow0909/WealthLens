from fastapi import APIRouter, Depends, HTTPException, Query

from services.auth_middleware import get_current_user
from services.analytics_service import (
    get_all_fund_metrics,
    get_fund_metrics,
    get_rolling_returns,
    get_trailing_returns_table,
)

router = APIRouter()


@router.get("/trailing-returns")
async def get_trailing_returns(user: dict = Depends(get_current_user)):
    """Trailing returns (1W–5Y) table for every fund in the portfolio."""
    return await get_trailing_returns_table(user["id"])


@router.get("/compare")
async def compare_funds(
    isins: str = Query(..., description="Comma-separated ISINs"),
    user: dict = Depends(get_current_user),
):
    """Full risk + return metrics for the selected funds, side by side."""
    isin_list = [s.strip() for s in isins.split(",") if s.strip()]
    if not isin_list:
        raise HTTPException(status_code=400, detail="No ISINs provided")
    return await get_all_fund_metrics(user["id"], isins=isin_list)


@router.get("/{isin}/rolling-returns")
async def get_fund_rolling_returns(
    isin: str,
    window: str = Query("1y", description="Rolling window: 1m | 3m | 6m | 1y | 3y"),
    user: dict = Depends(get_current_user),
):
    """Rolling return time series for a fund's detail chart, over the given window."""
    return await get_rolling_returns(isin, window)


@router.get("/{isin}")
async def get_fund_analytics(isin: str, user: dict = Depends(get_current_user)):
    """Full metrics for a single fund."""
    metrics = await get_fund_metrics(user["id"], isin)
    if not metrics:
        raise HTTPException(status_code=404, detail="Fund not found in your portfolio")
    return metrics
