"""
Integration tests for the LangGraph portfolio agent graph.

Gemini and Supabase are mocked so the full graph (intent_classifier →
recommender → state_update → quality_check → synthesizer → supabase_write)
runs end-to-end without external services.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agents.graph import portfolio_graph
from services.gemini_client import GeminiError


def _seed_state(prompt: str) -> dict:
    # metrics pre-seeded so the recommender doesn't hit analytics_service/Supabase
    return {
        "user_id": "test-user",
        "user_prompt": prompt,
        "intent": "",
        "cas_data": {},
        "nav_data": {},
        "metrics": {"total_value": 1000000, "total_invested": 800000,
                    "total_gain": 200000, "total_gain_pct": 25.0, "funds": []},
        "recommendation": "",
        "export_path": None,
        "quality_check_passed": False,
        "retry_count": 0,
        "final_response": {},
        "report_id": None,
        "error": None,
    }


def _mock_supabase(report_id="report-123"):
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": report_id}]
    return sb


def test_recommendation_flow_happy_path():
    with patch("agents.nodes.intent_classifier.call_gemini",
               new=AsyncMock(return_value="get_recommendation")), \
         patch("agents.nodes.recommender.call_gemini",
               new=AsyncMock(return_value="Your portfolio is well diversified across asset classes.")), \
         patch("agents.nodes.quality_check.call_gemini",
               new=AsyncMock(return_value="PASS")), \
         patch("agents.nodes.supabase_write.get_supabase",
               return_value=_mock_supabase("report-123")):
        result = asyncio.run(portfolio_graph.ainvoke(_seed_state("How is my portfolio doing?")))

    assert result["intent"] == "get_recommendation"
    assert result["quality_check_passed"] is True
    assert "diversified" in result["final_response"]["response_text"]
    assert result["report_id"] == "report-123"


def test_gemini_failure_falls_back_to_metrics_summary():
    # Recommender's Gemini fails → empty recommendation → QC fails →
    # synthesizer emits a best-effort summary built from metrics.
    with patch("agents.nodes.intent_classifier.call_gemini",
               new=AsyncMock(return_value="get_recommendation")), \
         patch("agents.nodes.recommender.call_gemini",
               new=AsyncMock(side_effect=GeminiError("boom"))), \
         patch("agents.nodes.quality_check.call_gemini",
               new=AsyncMock(return_value="FAIL")), \
         patch("agents.nodes.supabase_write.get_supabase",
               return_value=_mock_supabase()):
        result = asyncio.run(portfolio_graph.ainvoke(_seed_state("Advise me")))

    assert result["quality_check_passed"] is False
    text = result["final_response"]["response_text"]
    assert "summary of your portfolio" in text
    assert "₹10,00,000" in text or "1,000,000" in text or "10,00,000" in text


def test_intent_classifier_defaults_on_gibberish():
    # Classifier returns an unrecognised string → defaults to get_recommendation
    with patch("agents.nodes.intent_classifier.call_gemini",
               new=AsyncMock(return_value="i have no idea")), \
         patch("agents.nodes.recommender.call_gemini",
               new=AsyncMock(return_value="Here is some advice.")), \
         patch("agents.nodes.quality_check.call_gemini",
               new=AsyncMock(return_value="PASS")), \
         patch("agents.nodes.supabase_write.get_supabase",
               return_value=_mock_supabase()):
        result = asyncio.run(portfolio_graph.ainvoke(_seed_state("hello")))

    assert result["intent"] == "get_recommendation"
    assert result["final_response"]["response_text"] == "Here is some advice."
