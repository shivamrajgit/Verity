"""LangGraph state schema and supporting models."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class PlannerRequest(BaseModel):
    """A request to plan tests for a specific URL at a given depth."""

    url: str = Field(description="URL to plan tests for")
    depth: int = Field(default=0, description="Current recursion depth")
    parent_storage_state: dict[str, Any] | None = Field(
        default=None,
        description=("Browser storage state (cookies, localStorage) for auth propagation"),
    )
    user_instructions: str = Field(
        default="", description="Optional user-provided scope/focus instructions"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict for LangGraph state."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlannerRequest:
        """Deserialize from dict."""
        return cls.model_validate(data)


class GraphState(TypedDict):
    """LangGraph state schema. All fields must be JSON-serializable."""

    # FCFS queue of planner requests
    queue: list[dict]  # list[PlannerRequest.to_dict()]

    # Already-visited URLs (normalized) to prevent duplicates
    visited_urls: list[str]

    # Accumulated planner reports (serialized PlannerReport)
    reports: list[dict]

    # Current working items (cleared after each planner cycle)
    current_request: dict | None  # PlannerRequest.to_dict() or None
    current_test_plan: dict | None  # TestPlan.model_dump() or None
    current_results: list[dict]  # list[ExecutorResult.model_dump()]

    # Planner clarification context (survives interrupt/resume cycles)
    planner_context: str  # Accumulated Q&A from user clarifications
    planner_clarification_count: int  # Number of clarification rounds used

    # Final output
    final_report: str | None

    # Cost tracking
    total_cost: float
