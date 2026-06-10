"""
CAS PDF parser — thin normalization layer over the `casparser` library.

`casparser` (https://github.com/codereverser/casparser) is a battle-tested
parser that handles CAMS, KFintech, and NSDL/CDSL statements across their many
format variations. Rather than maintain our own brittle regex parser, we call
it and normalize its typed output into our own dataclasses.

Key fields we rely on from casparser's Scheme.valuation:
  - valuation.cost  → invested value (the "Cost Value" column in the CAS summary)
  - valuation.value → current market value (the "Market Value" column)
  - valuation.nav   → latest NAV
  - scheme.close    → closing unit balance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from typing import Optional

from casparser import read_cas_pdf
from casparser.exceptions import IncorrectPasswordError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models (unchanged public interface — router depends on these)
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


# Re-export so callers that catch password errors keep working
PasswordError = IncorrectPasswordError


# ---------------------------------------------------------------------------
# Transaction type mapping: casparser enum value → our schema value
# ---------------------------------------------------------------------------

# DB transaction_type allows: purchase | redemption | switch_in | switch_out | dividend
_TXN_TYPE_MAP = {
    "PURCHASE": "purchase",
    "PURCHASE_SIP": "purchase",
    "REDEMPTION": "redemption",
    "SWITCH_IN": "switch_in",
    "SWITCH_IN_MERGER": "switch_in",
    "SWITCH_OUT": "switch_out",
    "SWITCH_OUT_MERGER": "switch_out",
    "DIVIDEND_PAYOUT": "dividend",
    "DIVIDEND_REINVEST": "dividend",
}

# Tax / bookkeeping rows carry no units and are not real investment activity
_SKIP_TXN_TYPES = {
    "STT_TAX", "STAMP_DUTY_TAX", "TDS_TAX",
    "SEGREGATION", "MISC", "UNKNOWN", "REVERSAL",
}


def _f(value) -> float:
    """Coerce Decimal | None | str to float, defaulting to 0.0."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _txn_enum_value(txn_type) -> str:
    """casparser may give an enum member or a plain string — normalize to its value."""
    return getattr(txn_type, "value", txn_type) or "UNKNOWN"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_cas_pdf(pdf_bytes: bytes, password: str = "") -> CASData:
    """
    Parse a CAS PDF and return normalized portfolio data.

    Raises IncorrectPasswordError if the password is wrong (the router maps
    this to a friendly 422 message).
    """
    raw = read_cas_pdf(BytesIO(pdf_bytes), password or "")

    investor = raw.investor_info
    period = raw.statement_period

    cas = CASData(
        investor_name=getattr(investor, "name", "") or "",
        investor_email=getattr(investor, "email", "") or "",
        investor_pan="",  # PAN lives per-folio in casparser; filled below if present
        statement_period_from=str(getattr(period, "from_", "") or ""),
        statement_period_to=str(getattr(period, "to", "") or ""),
    )

    holdings: list[Holding] = []
    pan_seen = ""

    for folio in raw.folios:
        folio_no = (folio.folio or "").strip()
        if not pan_seen and getattr(folio, "PAN", None):
            pan_seen = folio.PAN

        for scheme in folio.schemes:
            holding = _normalize_scheme(scheme, folio_no)
            if holding:
                holdings.append(holding)

    cas.investor_pan = pan_seen
    cas.holdings = holdings

    if raw.parse_warnings:
        logger.warning("casparser warnings: %s", raw.parse_warnings)
    logger.info("Parsed CAS: %d holdings, investor=%r", len(holdings), cas.investor_name)
    return cas


def _normalize_scheme(scheme, folio_no: str) -> Optional[Holding]:
    isin = (scheme.isin or "").strip()
    amfi_code = (scheme.amfi or "").strip()
    scheme_name = (scheme.scheme or "Unknown Fund").strip()

    # Closing unit balance
    units_held = _f(scheme.close)

    # Statement-reported valuation (authoritative — matches the CAS summary page)
    val = scheme.valuation
    current_nav = _f(getattr(val, "nav", None))
    invested_value = _f(getattr(val, "cost", None))
    current_value = _f(getattr(val, "value", None))

    # --- Transactions ---
    transactions: list[Transaction] = []
    for txn in scheme.transactions or []:
        type_value = _txn_enum_value(txn.type)
        if type_value in _SKIP_TXN_TYPES:
            continue
        mapped = _TXN_TYPE_MAP.get(type_value, "purchase")
        transactions.append(
            Transaction(
                transaction_date=str(txn.date),
                transaction_type=mapped,
                amount=_f(txn.amount),
                units=_f(txn.units),
                nav=_f(txn.nav),
                balance=_f(txn.balance),
            )
        )

    # Skip schemes with no position and no history (fully redeemed, never held)
    if units_held == 0.0 and not transactions and current_value == 0.0:
        return None

    # Fallback chains if the valuation block was absent
    if current_value == 0.0 and units_held and current_nav:
        current_value = round(units_held * current_nav, 2)
    if invested_value == 0.0 and transactions:
        invested_value = max(
            sum(t.amount for t in transactions if t.transaction_type in ("purchase", "switch_in"))
            - sum(t.amount for t in transactions if t.transaction_type in ("redemption", "switch_out")),
            0.0,
        )

    # average_nav = total cost / units held (reflects all historical buys)
    average_nav = round(invested_value / units_held, 4) if units_held > 0 else 0.0

    return Holding(
        scheme_name=scheme_name,
        isin=isin,
        amfi_code=amfi_code,
        folio_number=folio_no,
        units_held=units_held,
        average_nav=average_nav,
        current_nav=current_nav,
        invested_value=round(invested_value, 2),
        current_value=round(current_value, 2),
        transactions=transactions,
    )
