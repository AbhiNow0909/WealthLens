from fastapi import APIRouter, Depends
from pydantic import BaseModel
from services.auth_middleware import get_current_user

router = APIRouter()


class AgentRequest(BaseModel):
    prompt: str


@router.post("/run")
async def run_agent(
    body: AgentRequest,
    user: dict = Depends(get_current_user),
):
    # TODO: Step 6 — invoke LangGraph portfolio_graph
    return {"response_text": "", "export_url": None, "report_id": None}
