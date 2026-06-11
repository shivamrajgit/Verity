"""Report models for compiled planner results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.executor_result import ExecutorResult


class PlannerReport(BaseModel):
    """Aggregated results from a single planner run (one URL)."""

    url: str = Field(description="The URL that was tested")
    depth: int = Field(description="Recursion depth of this planner")
    page_summary: str = Field(default="", description="Summary from the planner")
    results: list[ExecutorResult] = Field(
        default_factory=list, description="All executor results for this page"
    )

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == "error")

    @property
    def skip_count(self) -> int:
        return sum(1 for r in self.results if r.status == "skip")

    @property
    def total_count(self) -> int:
        return len(self.results)
