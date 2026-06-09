from agents.state import PortfolioState


async def run(state: PortfolioState) -> PortfolioState:
    # TODO: Step 4 — fetch NAV history and benchmark data
    return {**state, "nav_data": {}}
