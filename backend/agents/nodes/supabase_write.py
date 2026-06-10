import logging

from agents.state import PortfolioState
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)


async def run(state: PortfolioState) -> PortfolioState:
    report_id = None
    try:
        supabase = get_supabase()
        result = supabase.table("reports").insert({
            "user_id": state["user_id"],
            "prompt": state["user_prompt"],
            "intent": state.get("intent", ""),
            "response_text": state["final_response"].get("response_text", ""),
            "export_path": state.get("export_path"),
        }).execute()
        if result.data:
            report_id = result.data[0].get("id")
    except Exception as exc:
        logger.warning("Failed to persist report: %s", exc)

    return {**state, "report_id": report_id}
