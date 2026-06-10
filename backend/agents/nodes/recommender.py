import logging

from agents.state import PortfolioState
from services.gemini_client import call_gemini, GeminiError

logger = logging.getLogger(__name__)

SYSTEM = """You are a seasoned Indian mutual fund advisor.
Given the portfolio metrics below, provide a clear, actionable investment recommendation.
Be specific: call out underperformers, suggest rebalancing if needed, and highlight risks.
Write in clear prose, 3–5 paragraphs. Use ₹ for amounts and cite the metrics you rely on."""


async def run(state: PortfolioState) -> PortfolioState:
    # The graph routes recommendation requests straight here, skipping the
    # analytics node — so ensure metrics are populated before advising.
    metrics = state.get("metrics") or {}
    if not metrics:
        from services.analytics_service import compute_portfolio_metrics
        try:
            metrics = await compute_portfolio_metrics(state["user_id"])
        except Exception as exc:
            logger.warning("Could not load metrics for recommender: %s", exc)
            metrics = {}

    prompt = f"Portfolio metrics:\n{metrics}\n\nUser query: {state['user_prompt']}"
    try:
        recommendation = await call_gemini(prompt, system=SYSTEM)
    except GeminiError:
        # Leave empty; quality_check fails and synthesizer produces a
        # best-effort response from the metrics alone.
        recommendation = ""

    return {**state, "metrics": metrics, "recommendation": recommendation}
