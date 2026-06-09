from agents.state import PortfolioState
from services.gemini_client import call_gemini

SYSTEM = """You are a seasoned Indian mutual fund advisor.
Given the portfolio metrics below, provide a clear, actionable investment recommendation.
Be specific: call out underperformers, suggest rebalancing if needed, and highlight risks.
Write in clear prose, 3–5 paragraphs."""


async def run(state: PortfolioState) -> PortfolioState:
    prompt = f"Portfolio metrics:\n{state['metrics']}\n\nUser query: {state['user_prompt']}"
    recommendation = await call_gemini(prompt, system=SYSTEM)
    return {**state, "recommendation": recommendation}
