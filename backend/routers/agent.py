import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth_middleware import get_current_user
from agents.graph import portfolio_graph
from agents.state import PortfolioState

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentRequest(BaseModel):
    prompt: str


class AgentResponse(BaseModel):
    response_text: str
    export_url: str | None = None
    report_id: str | None = None


def _initial_state(user_id: str, prompt: str) -> PortfolioState:
    return {
        "user_id": user_id,
        "user_prompt": prompt,
        "intent": "",
        "cas_data": {},
        "nav_data": {},
        "metrics": {},
        "recommendation": "",
        "export_path": None,
        "quality_check_passed": False,
        "retry_count": 0,
        "final_response": {},
        "report_id": None,
        "error": None,
    }


@router.post("/run", response_model=AgentResponse)
async def run_agent(
    body: AgentRequest,
    user: dict = Depends(get_current_user),
):
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    try:
        result = await portfolio_graph.ainvoke(_initial_state(user["id"], prompt))
    except Exception as exc:
        logger.exception("Agent graph execution failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The assistant could not process your request. Please try again.",
        )

    final = result.get("final_response", {})
    return AgentResponse(
        response_text=final.get("response_text", ""),
        export_url=final.get("export_path"),
        report_id=result.get("report_id"),
    )
