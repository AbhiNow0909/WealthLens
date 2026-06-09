from langgraph.graph import StateGraph, END
from agents.state import PortfolioState
from agents.nodes import (
    intent_classifier,
    cas_parser,
    data_fetcher,
    analytics,
    recommender,
    export,
    quality_check,
    synthesizer,
    supabase_write,
)

INTENT_ROUTES = {
    "new_cas_upload": "cas_parser",
    "refresh_data": "data_fetcher",
    "get_analytics": "analytics",
    "get_recommendation": "recommender",
    "export_report": "export",
}


def route_by_intent(state: PortfolioState) -> str:
    return INTENT_ROUTES.get(state.get("intent", ""), END)


def route_quality_check(state: PortfolioState) -> str:
    if state.get("quality_check_passed"):
        return "synthesizer"
    if state.get("retry_count", 0) >= 1:
        return "synthesizer"
    return "state_update"


def build_graph() -> StateGraph:
    g = StateGraph(PortfolioState)

    g.add_node("intent_classifier", intent_classifier.run)
    g.add_node("cas_parser", cas_parser.run)
    g.add_node("data_fetcher", data_fetcher.run)
    g.add_node("analytics", analytics.run)
    g.add_node("recommender", recommender.run)
    g.add_node("export", export.run)
    g.add_node("state_update", lambda s: s)
    g.add_node("quality_check", quality_check.run)
    g.add_node("synthesizer", synthesizer.run)
    g.add_node("supabase_write", supabase_write.run)

    g.set_entry_point("intent_classifier")
    g.add_conditional_edges("intent_classifier", route_by_intent)

    for node in ["cas_parser", "data_fetcher", "analytics", "recommender", "export"]:
        g.add_edge(node, "state_update")

    g.add_edge("state_update", "quality_check")
    g.add_conditional_edges("quality_check", route_quality_check)
    g.add_edge("synthesizer", "supabase_write")
    g.add_edge("supabase_write", END)

    return g.compile()


portfolio_graph = build_graph()
