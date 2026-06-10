import re
import uuid
import logging
from datetime import date
from io import BytesIO
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel

import pdfplumber

from services.auth_middleware import get_current_user
from services.supabase_client import get_supabase
from services.cas_parser_service import parse_cas_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    upload_id: str
    status: str
    funds_found: int
    transactions_found: int


class HoldingOut(BaseModel):
    id: str
    isin: str
    scheme_name: str
    amfi_code: str | None
    folio_number: str | None
    units_held: float
    average_nav: float
    current_nav: float
    current_value: float
    invested_value: float


class PortfolioSummaryOut(BaseModel):
    total_value: float
    total_invested: float
    total_gain: float
    total_gain_pct: float
    holdings_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
async def upload_cas(
    file: UploadFile = File(...),
    password: str = Form(default=""),
    user: dict = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 20 * 1024 * 1024:  # 20 MB guard
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 20 MB limit",
        )

    user_id: str = user["id"]
    supabase = get_supabase()
    upload_id = str(uuid.uuid4())
    storage_path = f"{user_id}/{upload_id}.pdf"

    # 1. Upload PDF to Supabase Storage
    try:
        supabase.storage.from_("cas-pdfs").upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf"},
        )
    except Exception as exc:
        logger.exception("Storage upload failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store PDF")

    # 2. Log the upload
    supabase.table("cas_uploads").insert({
        "id": upload_id,
        "user_id": user_id,
        "storage_path": storage_path,
        "status": "parsing",
    }).execute()

    # 3. Parse the PDF
    try:
        cas = parse_cas_pdf(pdf_bytes, password=password)
    except Exception as exc:
        logger.exception("CAS parse error: %s", exc)
        supabase.table("cas_uploads").update({"status": "failed"}).eq("id", upload_id).execute()
        supabase.storage.from_("cas-pdfs").remove([storage_path])
        if "PDFPasswordIncorrect" in type(exc).__name__ or "password" in str(exc).lower():
            raise HTTPException(
                status_code=422,
                detail=(
                    "Incorrect PDF password. "
                    "NSDL CAS: use your registered email address. "
                    "CAMS / KFintech CAS: use your PAN number (uppercase)."
                ),
            )
        raise HTTPException(status_code=422, detail=f"Could not parse CAS PDF: {exc}")

    # 4. Upsert holdings
    total_transactions = 0
    for h in cas.holdings:
        # Upsert holding row (unique on user_id + isin)
        holding_data = {
            "user_id": user_id,
            "isin": h.isin or f"UNKNOWN_{h.folio_number}",
            "scheme_name": h.scheme_name,
            "amfi_code": h.amfi_code or None,
            "folio_number": h.folio_number,
            "units_held": h.units_held,
            "average_nav": h.average_nav,
            "current_nav": h.current_nav,
            "current_value": h.current_value,
            "invested_value": h.invested_value,
            "last_updated": date.today().isoformat(),
        }
        try:
            supabase.table("holdings").upsert(
                holding_data, on_conflict="user_id,isin"
            ).execute()
        except Exception as exc:
            logger.warning("Failed to upsert holding %s: %s", h.isin, exc)
            continue

        # Insert transactions (skip duplicates on date + type + units)
        for t in h.transactions:
            txn_data = {
                "user_id": user_id,
                "isin": h.isin or f"UNKNOWN_{h.folio_number}",
                "folio_number": h.folio_number,
                "transaction_date": t.transaction_date,
                "transaction_type": t.transaction_type,
                "amount": t.amount,
                "units": t.units,
                "nav": t.nav,
            }
            try:
                supabase.table("transactions").insert(txn_data).execute()
                total_transactions += 1
            except Exception:
                pass  # likely a duplicate — skip silently

    # 5. Mark upload as parsed and delete the PDF from storage
    supabase.table("cas_uploads").update({
        "status": "parsed",
        "statement_date": cas.statement_period_to or None,
        "parsed_at": "now()",
    }).eq("id", upload_id).execute()

    supabase.storage.from_("cas-pdfs").remove([storage_path])

    return UploadResponse(
        upload_id=upload_id,
        status="parsed",
        funds_found=len(cas.holdings),
        transactions_found=total_transactions,
    )


@router.get("/holdings")
async def get_holdings(user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    result = (
        supabase.table("holdings")
        .select("*")
        .eq("user_id", user["id"])
        .order("scheme_name")
        .execute()
    )
    return result.data


@router.post("/debug-parse")
async def debug_parse_pdf(
    file: UploadFile = File(...),
    password: str = Form(default=""),
    user: dict = Depends(get_current_user),
):
    """
    Returns raw extracted text from the first 5 pages of the PDF.
    Use this to diagnose CAS parser issues — call once, paste output.
    """
    pdf_bytes = await file.read()
    pages_text: list[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes), password=password or None) as pdf:
        for i, page in enumerate(pdf.pages[:5]):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            pages_text.append(f"\n\n===PAGE {i+1}===\n{text}")
    full_text = "".join(pages_text)
    isin_hits = re.findall(r'INF[A-Z0-9]{9}', full_text)
    folio_hits = re.findall(r'(?i)folio\s*no\.?\s*[:\-]\s*\S+', full_text)
    return {
        "total_pages_sampled": len(pages_text),
        "isins_found": isin_hits,
        "folio_lines_found": folio_hits,
        "text_preview": full_text[:8000],
    }


@router.get("/summary")
async def get_summary(user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    result = (
        supabase.table("holdings")
        .select("current_value,invested_value,scheme_name")
        .eq("user_id", user["id"])
        .execute()
    )
    rows = result.data or []

    total_value = sum(r["current_value"] or 0 for r in rows)
    total_invested = sum(r["invested_value"] or 0 for r in rows)
    total_gain = total_value - total_invested
    total_gain_pct = (total_gain / total_invested * 100) if total_invested > 0 else 0.0

    return {
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "total_gain": round(total_gain, 2),
        "total_gain_pct": round(total_gain_pct, 2),
        "holdings_count": len(rows),
        "allocation": [
            {"name": r["scheme_name"], "value": r["current_value"] or 0}
            for r in rows
        ],
    }
