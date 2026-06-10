from agents.state import PortfolioState
from services.cas_parser_service import parse_cas_pdf, CASData
import logging

logger = logging.getLogger(__name__)


def _cas_data_to_dict(cas: CASData) -> dict:
    return {
        "investor_name": cas.investor_name,
        "investor_email": cas.investor_email,
        "investor_pan": cas.investor_pan,
        "statement_period_from": cas.statement_period_from,
        "statement_period_to": cas.statement_period_to,
        "holdings": [
            {
                "scheme_name": h.scheme_name,
                "isin": h.isin,
                "amfi_code": h.amfi_code,
                "folio_number": h.folio_number,
                "units_held": h.units_held,
                "average_nav": h.average_nav,
                "current_nav": h.current_nav,
                "invested_value": h.invested_value,
                "current_value": h.current_value,
                "transactions": [
                    {
                        "transaction_date": t.transaction_date,
                        "transaction_type": t.transaction_type,
                        "amount": t.amount,
                        "units": t.units,
                        "nav": t.nav,
                        "balance": t.balance,
                    }
                    for t in h.transactions
                ],
            }
            for h in cas.holdings
        ],
    }


async def run(state: PortfolioState) -> PortfolioState:
    pdf_bytes: bytes | None = state.get("cas_data", {}).get("_pdf_bytes")
    if not pdf_bytes:
        logger.error("cas_parser node: no PDF bytes in state")
        return {**state, "error": "No PDF data to parse", "cas_data": {}}

    try:
        cas = parse_cas_pdf(pdf_bytes)
        return {**state, "cas_data": _cas_data_to_dict(cas)}
    except Exception as exc:
        logger.exception("CAS parsing failed: %s", exc)
        return {**state, "error": str(exc), "cas_data": {}}
