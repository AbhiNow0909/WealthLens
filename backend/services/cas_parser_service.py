"""
NSDL / CAMS / KFintech CAS PDF parser.

The NSDL CAS format looks like:
  [Scheme Name] - [Plan] - [Option] (ISIN: INFxxxxxxxxx)
  Folio No.: XXXXXXXXXX / X   KYC: OK   PAN: XXXXX1234X
  [Opening Balance line]
  Date    Description    Amount    Units    NAV    Unit Balance
  01-Jan-2024  Purchase - SIP  10,000.00  98.765  101.25  98.765
  Closing Balance               98.765  101.25  10,000.00

Primary parsing strategy: split on ISIN lines (every fund section has exactly one).
Fallback: split on Folio No lines.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Transaction:
    transaction_date: str
    transaction_type: str   # purchase | redemption | switch_in | switch_out | dividend
    amount: float
    units: float
    nav: float
    balance: float


@dataclass
class Holding:
    scheme_name: str
    isin: str
    amfi_code: str
    folio_number: str
    units_held: float
    average_nav: float
    current_nav: float
    invested_value: float
    current_value: float
    transactions: list[Transaction] = field(default_factory=list)


@dataclass
class CASData:
    investor_name: str
    investor_email: str
    investor_pan: str
    statement_period_from: str
    statement_period_to: str
    holdings: list[Holding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_ISIN_RE = re.compile(r'\bINF[A-Z0-9]{9}\b')

# Folio numbers are typically digits/slash/spaces after "Folio No:" or "Folio No.:"
_FOLIO_RE = re.compile(
    r'Folio\s+No\.?\s*[:\-]\s*'
    r'([\d][A-Z0-9/\s]*?)'
    r'(?=\s{2,}|[A-Za-z]{3,}|\s*\n|\s*$)',
    re.IGNORECASE,
)

_CAS_DATE_RE = re.compile(r'\b(\d{2}-[A-Za-z]{3}-\d{4})\b')

_PERIOD_RE = re.compile(
    r'(\d{2}-[A-Za-z]{3}-\d{4})\s+[Tt]o\s+(\d{2}-[A-Za-z]{3}-\d{4})'
)

_INVESTOR_RE = re.compile(r'(?:Dear\s+|Investor\s*[:\-]\s*)([^\n,]+)', re.IGNORECASE)
_PAN_RE = re.compile(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b')
_EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b', re.IGNORECASE)
_AMFI_RE = re.compile(r'(?:AMFI\s*[:\-]\s*|Scheme\s+Code\s*[:\-]\s*)(\d{6})', re.IGNORECASE)

# Allow leading whitespace — pdfplumber sometimes indents lines
_TXN_ROW_RE = re.compile(
    r'^\s*(\d{2}-[A-Za-z]{3}-\d{4})'   # date
    r'[ \t]+(.*?)'                       # description (no newlines)
    r'[ \t]+([\d,]+\.\d{2,4})'          # amount
    r'[ \t]+([\d,]+\.\d{2,4})'          # units
    r'[ \t]+([\d,]+\.\d{2,4})'          # nav
    r'[ \t]+([\d,]+\.\d{2,4})',         # running balance
    re.MULTILINE,
)

# Closing balance: "Closing Balance ... units  nav  value" on one line
_CLOSING_RE = re.compile(
    r'[Cc]losing\s+[Bb]alance\b[^\n]*?([\d,]+\.\d{3,4})[ \t]+([\d,]+\.\d{3,4})',
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return date_str.strip()


def _clean_number(s: str) -> float:
    try:
        return float(s.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _classify_txn_type(description: str) -> str:
    desc = description.upper()
    if any(k in desc for k in ("SWITCH IN", "SWITCH-IN", "SWI")):
        return "switch_in"
    if any(k in desc for k in ("SWITCH OUT", "SWITCH-OUT", "SWO")):
        return "switch_out"
    if any(k in desc for k in ("REDEMPTION", "REDEEM")):
        return "redemption"
    if any(k in desc for k in ("DIVIDEND", "IDCW")):
        return "dividend"
    return "purchase"


def _compute_average_nav(transactions: list[Transaction]) -> float:
    total_units = sum(t.units for t in transactions if t.transaction_type == "purchase")
    total_cost = sum(t.amount for t in transactions if t.transaction_type == "purchase")
    return total_cost / total_units if total_units > 0 else 0.0


def _compute_invested_value(transactions: list[Transaction]) -> float:
    invested = 0.0
    for t in transactions:
        if t.transaction_type in ("purchase", "switch_in"):
            invested += t.amount
        elif t.transaction_type in ("redemption", "switch_out"):
            invested -= t.amount
    return max(invested, 0.0)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_cas_pdf(pdf_bytes: bytes, password: str = "") -> CASData:
    full_text = _extract_text(pdf_bytes, password)
    cas = _parse_header(full_text)
    cas.holdings = _parse_holdings(full_text)
    logger.info(
        "Parsed CAS: %s holdings, investor=%r",
        len(cas.holdings),
        cas.investor_name,
    )
    return cas


def _extract_text(pdf_bytes: bytes, password: str = "") -> str:
    pages: list[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes), password=password or None) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    pages.append(text)
            except Exception as exc:
                logger.warning("Could not extract text from page %d: %s", i + 1, exc)
    return "\n".join(pages)


def _parse_header(text: str) -> CASData:
    name = email = pan = period_from = period_to = ""

    m = _INVESTOR_RE.search(text)
    if m:
        name = m.group(1).strip()

    m = _EMAIL_RE.search(text)
    if m:
        email = m.group(0)

    for m in _PAN_RE.finditer(text):
        if text.index(m.group(1)) < 3000:
            pan = m.group(1)
            break

    m = _PERIOD_RE.search(text)
    if m:
        period_from = _parse_date(m.group(1))
        period_to = _parse_date(m.group(2))

    return CASData(
        investor_name=name,
        investor_email=email,
        investor_pan=pan,
        statement_period_from=period_from,
        statement_period_to=period_to,
    )


def _parse_holdings(text: str) -> list[Holding]:
    """
    Primary strategy: split on lines that contain an ISIN — every fund has exactly one.
    Each block runs from 8 lines before the ISIN line to the start of the next ISIN block.
    Fallback: split on Folio No lines (older CAS formats without ISIN in scheme name).
    """
    holdings: list[Holding] = []
    lines = text.splitlines()

    # --- Strategy 1: ISIN anchors ---
    isin_anchors: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = _ISIN_RE.search(line)
        if m:
            isin_anchors.append((i, m.group(0)))

    if isin_anchors:
        logger.debug("Found %d ISIN anchors", len(isin_anchors))
        for idx, (anchor_line, isin) in enumerate(isin_anchors):
            pre_start = max(0, anchor_line - 8)
            end_line = isin_anchors[idx + 1][0] if idx + 1 < len(isin_anchors) else len(lines)
            block = "\n".join(lines[pre_start:end_line])

            folio_m = _FOLIO_RE.search(block)
            folio = folio_m.group(1).strip() if folio_m else f"NOFOL_{idx + 1}"

            try:
                holding = _parse_folio_block(block, folio, known_isin=isin)
                if holding:
                    holdings.append(holding)
            except Exception as exc:
                logger.warning("Failed to parse fund %s: %s", isin, exc)
        return holdings

    # --- Strategy 2: Folio anchors (fallback) ---
    logger.warning("No ISINs found — falling back to folio-based splitting")
    folio_anchors: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = _FOLIO_RE.search(line)
        if m:
            folio_anchors.append((i, m.group(1).strip()))

    if not folio_anchors:
        logger.warning("No folio numbers found either — check debug-parse endpoint for raw text")
        return holdings

    for idx, (start_line, folio) in enumerate(folio_anchors):
        pre_start = max(0, start_line - 8)
        end_line = folio_anchors[idx + 1][0] if idx + 1 < len(folio_anchors) else len(lines)
        block = "\n".join(lines[pre_start:end_line])
        try:
            holding = _parse_folio_block(block, folio)
            if holding:
                holdings.append(holding)
        except Exception as exc:
            logger.warning("Failed to parse folio %s: %s", folio, exc)

    return holdings


def _parse_folio_block(block: str, folio: str, known_isin: str = "") -> Optional[Holding]:
    """Parse one fund block into a Holding."""

    # --- ISIN ---
    isin = known_isin
    if not isin:
        m = _ISIN_RE.search(block)
        isin = m.group(0) if m else ""

    # --- Scheme name ---
    # The scheme name line is the one that contains the ISIN (in parentheses).
    # Extract it by stripping the ISIN annotation from that line.
    scheme_name = "Unknown Fund"
    if isin:
        for line in block.splitlines():
            if isin in line:
                # Strip "(ISIN: INFxxxxxxxxx)" or "ISIN: INFxxxxxxxxx"
                candidate = re.sub(
                    r'\s*[-–]?\s*\(?ISIN\s*[:\-]\s*INF[A-Z0-9]{9}\)?',
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip().rstrip("-–").strip()
                if len(candidate) > 5 and not _FOLIO_RE.search(candidate):
                    scheme_name = candidate
                break

    if scheme_name == "Unknown Fund":
        # Fallback: longest meaningful line in first 10 lines
        candidates = [
            l.strip() for l in block.splitlines()[:10]
            if l.strip()
            and len(l.strip()) > 10
            and not _FOLIO_RE.search(l)
            and not _ISIN_RE.search(l)
        ]
        if candidates:
            scheme_name = max(candidates, key=len)

    # --- AMFI code ---
    amfi_m = _AMFI_RE.search(block)
    amfi_code = amfi_m.group(1) if amfi_m else ""

    # --- Transactions ---
    transactions: list[Transaction] = []
    for m in _TXN_ROW_RE.finditer(block):
        date_str, desc, amount_s, units_s, nav_s, balance_s = m.groups()
        txn = Transaction(
            transaction_date=_parse_date(date_str),
            transaction_type=_classify_txn_type(desc),
            amount=_clean_number(amount_s),
            units=_clean_number(units_s),
            nav=_clean_number(nav_s),
            balance=_clean_number(balance_s),
        )
        transactions.append(txn)

    # --- Closing balance ---
    units_held = 0.0
    current_nav = 0.0
    closing_m = _CLOSING_RE.search(block)
    if closing_m:
        units_held = _clean_number(closing_m.group(1))
        current_nav = _clean_number(closing_m.group(2))
    elif transactions:
        units_held = transactions[-1].balance
        current_nav = transactions[-1].nav

    # Also try extracting closing balance from a dedicated "Closing Balance" line
    # in case the regex missed it (e.g., extra spaces or different decimal places)
    if units_held == 0.0:
        for line in block.splitlines():
            if re.search(r'[Cc]losing\s+[Bb]alance', line):
                nums = re.findall(r'[\d,]+\.\d{2,4}', line)
                if len(nums) >= 2:
                    units_held = _clean_number(nums[0])
                    current_nav = _clean_number(nums[1])
                    break

    if units_held == 0.0 and not transactions:
        return None

    avg_nav = _compute_average_nav(transactions)
    invested = _compute_invested_value(transactions)

    return Holding(
        scheme_name=scheme_name,
        isin=isin,
        amfi_code=amfi_code,
        folio_number=folio,
        units_held=units_held,
        average_nav=avg_nav,
        current_nav=current_nav,
        invested_value=invested,
        current_value=round(units_held * current_nav, 2),
        transactions=transactions,
    )
