from agents.state import PortfolioState
from services.gemini_client import call_gemini, GeminiError

VALID_INTENTS = (
    "new_cas_upload",
    "refresh_data",
    "get_analytics",
    "get_recommendation",
    "export_report",
)

SYSTEM = """You are an intent classifier for a mutual fund portfolio tracker.
Classify the user prompt into exactly one of these intents:
new_cas_upload | refresh_data | get_analytics | get_recommendation | export_report

Reply with only the intent string, nothing else."""


async def run(state: PortfolioState) -> PortfolioState:
    try:
        raw = await call_gemini(state["user_prompt"], system=SYSTEM)
    except GeminiError:
        # Most chat queries are recommendation requests — sensible default
        return {**state, "intent": "get_recommendation"}

    text = raw.lower()
    intent = next((v for v in VALID_INTENTS if v in text), "get_recommendation")
    return {**state, "intent": intent}
