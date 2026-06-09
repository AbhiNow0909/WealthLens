from agents.state import PortfolioState


async def run(state: PortfolioState) -> PortfolioState:
    # TODO: Step 3 — pdfplumber extraction of holdings and transactions
    return {**state, "cas_data": {}}
