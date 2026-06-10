from typing import TypedDict


class PortfolioState(TypedDict):
    user_id: str
    user_prompt: str
    intent: str
    cas_data: dict
    nav_data: dict
    metrics: dict
    recommendation: str
    export_path: str | None
    quality_check_passed: bool
    retry_count: int
    final_response: dict
    report_id: str | None
    error: str | None
