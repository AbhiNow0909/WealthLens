from fastapi import APIRouter, Depends, UploadFile, File
from services.auth_middleware import get_current_user

router = APIRouter()


@router.post("/upload")
async def upload_cas(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    # TODO: Step 3 — trigger cas_parser agent
    return {"upload_id": None, "status": "pending"}


@router.get("/holdings")
async def get_holdings(user: dict = Depends(get_current_user)):
    # TODO: Step 7 — query holdings from Supabase
    return []


@router.get("/summary")
async def get_summary(user: dict = Depends(get_current_user)):
    # TODO: Step 7 — compute total value, XIRR, gain/loss
    return {}
