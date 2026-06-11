"""Structured output schema for the planner agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    """A single test case to be executed by a browser-use agent."""

    name: str = Field(description="Short descriptive name for the test case")
    description: str = Field(description="What this test validates")
    url: str = Field(description="Starting URL for the test")
    steps: list[str] = Field(description="Ordered steps for the executor to follow")
    expected_outcome: str = Field(description="Clear expected result to verify against")
    priority: Literal["critical", "high", "medium", "low"] = Field(
        default="medium", description="Severity if this test fails"
    )


class SubPage(BaseModel):
    """A sub-page discovered during planning that warrants deeper testing."""

    url: str = Field(description="Full URL of the sub-page")
    reason: str = Field(description="Why this page is worth testing")
    requires_auth: bool = Field(
        default=False, description="Whether this page requires authentication"
    )


class TestPlan(BaseModel):
    """Structured output from a planner agent for a single page."""

    test_cases: list[TestCase] = Field(
        default_factory=list, description="Test cases to execute on this page"
    )
    sub_pages: list[SubPage] = Field(
        default_factory=list, description="Sub-pages to enqueue for deeper testing"
    )
    page_summary: str = Field(
        default="", description="Brief summary of what this page contains and does"
    )
