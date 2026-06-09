from fastapi import APIRouter, Depends, Query
from services.auth_middleware import get_current_user

router = APIRouter()


@router.get("/trailing-returns")
async def get_trailing_returns(user: dict = Depends(get_current_user)):
    # TODO: Step 5 — return trailing returns table for all portfolio funds
    return []


@router.get("/compare")
async def compare_funds(
    isins: str = Query(..., description="Comma-separated ISINs"),
    user: dict = Depends(get_current_user),
):
    # TODO: Step 5 — return risk metrics for selected funds
    return []


@router.get("/{isin}")
async def get_fund_analytics(isin: str, user: dict = Depends(get_current_user)):
    # TODO: Step 5 — return full metrics for one fund
    return {}
