"""Structured output schema for executor agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExecutorResult(BaseModel):
    """Result from a single test case execution."""

    test_name: str = Field(description="Name of the test case that was executed")
    status: Literal["pass", "fail", "error", "skip"] = Field(
        description="Outcome of the test execution"
    )
    evidence: str = Field(
        default="", description="Extracted text, observations, or screenshot description"
    )
    error_detail: str | None = Field(default=None, description="Error message if status is 'error'")
    steps_executed: list[str] = Field(
        default_factory=list, description="Steps that were actually performed"
    )
    duration_seconds: float = Field(
        default=0.0, description="Wall-clock time for this test execution"
    )
    cost_usd: float = Field(
        default=0.0, ge=0.0, description="Provider-reported execution cost when available"
    )
