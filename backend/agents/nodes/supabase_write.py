from agents.state import PortfolioState
from services.supabase_client import get_supabase


async def run(state: PortfolioState) -> PortfolioState:
    supabase = get_supabase()
    supabase.table("reports").insert({
        "user_id": state["user_id"],
        "prompt": state["user_prompt"],
        "intent": state.get("intent", ""),
        "response_text": state["final_response"].get("response_text", ""),
        "export_path": state.get("export_path"),
    }).execute()
    return state
