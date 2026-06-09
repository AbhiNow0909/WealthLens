from agents.state import PortfolioState
from services.gemini_client import call_gemini

SYSTEM = """You are a quality checker for financial AI outputs.
Review the recommendation below and reply with only "PASS" or "FAIL".
PASS if it is coherent, factually grounded, and relevant to the user query.
FAIL if it is off-topic, contradictory, or empty."""


async def run(state: PortfolioState) -> PortfolioState:
    prompt = f"User query: {state['user_prompt']}\n\nRecommendation:\n{state['recommendation']}"
    verdict = await call_gemini(prompt, system=SYSTEM)
    passed = verdict.strip().upper().startswith("PASS")
    return {
        **state,
        "quality_check_passed": passed,
        "retry_count": state.get("retry_count", 0) + (0 if passed else 1),
    }
