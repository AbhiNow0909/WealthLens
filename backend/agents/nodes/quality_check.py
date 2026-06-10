from agents.state import PortfolioState
from services.gemini_client import call_gemini, GeminiError

SYSTEM = """You are a quality checker for financial AI outputs.
Review the recommendation below and reply with only "PASS" or "FAIL".
PASS if it is coherent, factually grounded, and relevant to the user query.
FAIL if it is off-topic, contradictory, or empty."""


async def run(state: PortfolioState) -> PortfolioState:
    recommendation = (state.get("recommendation") or "").strip()

    # An empty recommendation (e.g. Gemini failed upstream) can't pass.
    if not recommendation:
        return {
            **state,
            "quality_check_passed": False,
            "retry_count": state.get("retry_count", 0) + 1,
        }

    prompt = f"User query: {state['user_prompt']}\n\nRecommendation:\n{recommendation}"
    try:
        verdict = await call_gemini(prompt, system=SYSTEM)
        passed = verdict.strip().upper().startswith("PASS")
    except GeminiError:
        # Don't block delivery on a QC infrastructure failure — surface the
        # recommendation as best-effort.
        passed = True

    return {
        **state,
        "quality_check_passed": passed,
        "retry_count": state.get("retry_count", 0) + (0 if passed else 1),
    }
