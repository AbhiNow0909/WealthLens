from agents.state import PortfolioState


def _fallback_summary(metrics: dict) -> str:
    """Plain-text portfolio summary used when no LLM recommendation is available."""
    if not metrics:
        return (
            "I couldn't generate a recommendation right now. Please ensure your "
            "portfolio is uploaded and prices are refreshed, then try again."
        )
    tv = metrics.get("total_value", 0)
    ti = metrics.get("total_invested", 0)
    tg = metrics.get("total_gain", 0)
    pct = metrics.get("total_gain_pct", 0)
    xirr = metrics.get("portfolio_xirr", 0)
    lines = [
        "Here is a summary of your portfolio:",
        f"• Current value: ₹{tv:,.0f}",
        f"• Invested: ₹{ti:,.0f}",
        f"• Total gain: ₹{tg:,.0f} ({pct:+.2f}%)",
    ]
    if xirr:
        lines.append(f"• XIRR: {xirr:+.2f}%")
    funds = metrics.get("funds") or []
    if funds:
        lines.append(f"• Holdings analysed: {len(funds)}")
    return "\n".join(lines)


async def run(state: PortfolioState) -> PortfolioState:
    recommendation = (state.get("recommendation") or "").strip()
    metrics = state.get("metrics", {})

    response_text = recommendation or _fallback_summary(metrics)

    final_response = {
        "response_text": response_text,
        "metrics": metrics,
        "export_path": state.get("export_path"),
        "quality_check_passed": state.get("quality_check_passed", False),
    }
    return {**state, "final_response": final_response}
