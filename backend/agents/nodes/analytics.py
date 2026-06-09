from agents.state import PortfolioState


async def run(state: PortfolioState) -> PortfolioState:
    # TODO: Step 5 — compute XIRR, trailing returns, Alpha/Beta, Sharpe, Sortino, etc.
    return {**state, "metrics": {}}
