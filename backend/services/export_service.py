"""
Export orchestration — gathers portfolio data, generates a narrative, builds
the requested file, uploads it to Supabase Storage, and returns a signed URL.

Storage: files go to the `reports` bucket under `<user_id>/<uuid>.<ext>`.
Create a private `reports` bucket in Supabase before using this.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from services.supabase_client import get_supabase
from services.analytics_service import compute_portfolio_metrics
from agents.nodes.export import build_excel, build_word, build_ppt

logger = logging.getLogger(__name__)

REPORTS_BUCKET = "reports"
SIGNED_URL_TTL = 3600  # 1 hour

_FORMATS = {
    "excel": (
        "xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        build_excel,
    ),
    "word": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        build_word,
    ),
    "ppt": (
        "pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        build_ppt,
    ),
}

_NARRATIVE_SYSTEM = """You are a seasoned Indian mutual fund advisor writing the
analysis section of a portfolio report. Given the metrics, write 3–4 concise
paragraphs: overall health, notable out/under-performers, risk observations, and
one or two actionable suggestions. Plain prose, no markdown headings."""


def _build_report_data(user_id: str) -> dict:
    supabase = get_supabase()
    holdings_rows = (
        supabase.table("holdings")
        .select("isin,scheme_name,units_held,current_nav,invested_value,current_value")
        .eq("user_id", user_id)
        .order("current_value", desc=True)
        .execute()
        .data
        or []
    )

    holdings = []
    for h in holdings_rows:
        inv = float(h.get("invested_value") or 0)
        cur = float(h.get("current_value") or 0)
        gain = cur - inv
        holdings.append({
            "scheme_name": h.get("scheme_name", ""),
            "isin": h.get("isin", ""),
            "units_held": float(h.get("units_held") or 0),
            "current_nav": float(h.get("current_nav") or 0),
            "invested_value": inv,
            "current_value": cur,
            "gain": gain,
            "gain_pct": (gain / inv * 100) if inv > 0 else 0.0,
        })

    return holdings


async def _generate_narrative(metrics_bundle: dict) -> str:
    """Gemini-written analysis; falls back to a templated summary on failure."""
    from services.gemini_client import call_gemini, GeminiError

    try:
        prompt = f"Portfolio metrics:\n{metrics_bundle}"
        return await call_gemini(prompt, system=_NARRATIVE_SYSTEM)
    except GeminiError:
        s = metrics_bundle
        return (
            f"This portfolio holds {len(s.get('funds', []))} funds with a current "
            f"value of ₹{s.get('total_value', 0):,.0f} against ₹{s.get('total_invested', 0):,.0f} "
            f"invested — a gain of {s.get('total_gain_pct', 0):+.2f}%. "
            "Detailed AI analysis is unavailable right now; see the metrics tables for specifics."
        )


async def generate_report(user_id: str, fmt: str, prompt: str = "") -> dict:
    """
    Generate a report of the given format ('excel' | 'word' | 'ppt'), upload it,
    and return {export_url, filename, format}.
    """
    fmt = (fmt or "excel").lower()
    if fmt not in _FORMATS:
        raise ValueError(f"Unsupported export format: {fmt}")
    ext, content_type, builder = _FORMATS[fmt]

    metrics_bundle = await compute_portfolio_metrics(user_id)
    holdings = _build_report_data(user_id)

    report_data = {
        "summary": {
            "total_value": metrics_bundle.get("total_value", 0),
            "total_invested": metrics_bundle.get("total_invested", 0),
            "total_gain": metrics_bundle.get("total_gain", 0),
            "total_gain_pct": metrics_bundle.get("total_gain_pct", 0),
            "portfolio_xirr": metrics_bundle.get("portfolio_xirr", 0),
        },
        "holdings": holdings,
        "metrics": metrics_bundle.get("funds", []),
        "generated_at": date.today().isoformat(),
    }

    # Narrative only needed for Word/PPT
    narrative = ""
    if fmt in ("word", "ppt"):
        narrative = await _generate_narrative(metrics_bundle)
        content = builder(report_data, narrative)
    else:
        content = builder(report_data)

    filename = f"WealthLens_Report_{date.today().isoformat()}.{ext}"
    storage_path = f"{user_id}/{uuid.uuid4()}.{ext}"

    supabase = get_supabase()
    supabase.storage.from_(REPORTS_BUCKET).upload(
        path=storage_path,
        file=content,
        file_options={"content-type": content_type},
    )
    signed = supabase.storage.from_(REPORTS_BUCKET).create_signed_url(storage_path, SIGNED_URL_TTL)
    url = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")

    # Log the export as a report row (best-effort)
    try:
        supabase.table("reports").insert({
            "user_id": user_id,
            "prompt": prompt or f"Export {fmt} report",
            "intent": "export_report",
            "response_text": f"Generated {fmt} report",
            "export_path": storage_path,
        }).execute()
    except Exception as exc:
        logger.warning("Failed to log export report: %s", exc)

    return {"export_url": url, "filename": filename, "format": fmt}


def _parse_ts(value: str) -> datetime | None:
    """Parse a Supabase ISO timestamp (e.g. '2026-06-10T17:26:55.527Z')."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def cleanup_old_reports(days: int | None = None) -> int:
    """
    Delete report files older than `days` (default REPORT_RETENTION_DAYS or 7).
    Files live at `<user_id>/<uuid>.<ext>`; signed URLs expire in an hour, so a
    few days of retention is plenty. Returns the number of files removed.
    """
    retention = days if days is not None else int(os.environ.get("REPORT_RETENTION_DAYS", "7"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)

    supabase = get_supabase()
    bucket = supabase.storage.from_(REPORTS_BUCKET)
    list_opts = {"limit": 1000}

    # Root entries are per-user folders (id is None).
    try:
        folders = bucket.list(options=list_opts) or []
    except Exception as exc:
        logger.warning("Report cleanup: could not list bucket: %s", exc)
        return 0

    stale: list[str] = []
    for folder in folders:
        if folder.get("id") is not None:
            continue  # a file at the root (unexpected) — skip
        prefix = folder.get("name")
        if not prefix:
            continue
        try:
            files = bucket.list(prefix, options=list_opts) or []
        except Exception as exc:
            logger.warning("Report cleanup: could not list %s: %s", prefix, exc)
            continue
        for f in files:
            if f.get("id") is None:
                continue  # nested folder
            created = _parse_ts(f.get("created_at") or f.get("updated_at") or "")
            if created and created < cutoff:
                stale.append(f"{prefix}/{f['name']}")

    if not stale:
        return 0

    removed = 0
    for i in range(0, len(stale), 100):
        batch = stale[i : i + 100]
        try:
            bucket.remove(batch)
            removed += len(batch)
        except Exception as exc:
            logger.warning("Report cleanup: failed to remove batch: %s", exc)

    logger.info("Report cleanup: removed %d file(s) older than %d days", removed, retention)
    return removed
