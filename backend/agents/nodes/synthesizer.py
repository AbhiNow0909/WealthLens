from agents.state import PortfolioState


async def run(state: PortfolioState) -> PortfolioState:
    final_response = {
        "response_text": state.get("recommendation", ""),
        "metrics": state.get("metrics", {}),
        "export_path": state.get("export_path"),
        "quality_check_passed": state.get("quality_check_passed", False),
    }
    return {**state, "final_response": final_response}
