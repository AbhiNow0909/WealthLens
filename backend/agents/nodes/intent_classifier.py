from agents.state import PortfolioState
from services.gemini_client import call_gemini

SYSTEM = """You are an intent classifier for a mutual fund portfolio tracker.
Classify the user prompt into exactly one of these intents:
new_cas_upload | refresh_data | get_analytics | get_recommendation | export_report

Reply with only the intent string, nothing else."""


async def run(state: PortfolioState) -> PortfolioState:
    intent = await call_gemini(state["user_prompt"], system=SYSTEM)
    return {**state, "intent": intent.strip()}
