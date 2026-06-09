from agents.state import PortfolioState


async def run(state: PortfolioState) -> PortfolioState:
    # TODO: Step 10 — generate Excel / Word / PPT and upload to Supabase Storage
    return {**state, "export_path": None}
