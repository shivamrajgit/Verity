"""Structured output schema for the planner agent."""

from __future__ import annotations

from typing import Any, Literal

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


def repair_test_plan_payload(data: Any, default_url: str | None = None) -> dict[str, Any] | None:
    """Normalize common LLM plan-shape errors before Pydantic validation.

    Repairs are limited to safe shape fixes such as missing defaults and
    string sub-page entries. Malformed test cases without actionable steps are
    discarded rather than invented.
    """
    if not isinstance(data, dict):
        return None

    raw_cases = data.get("test_cases", data.get("tests", []))
    if not isinstance(raw_cases, list):
        return None

    repaired_cases: list[dict[str, Any]] = []
    for index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            continue

        name = _text_value(raw_case.get("name")) or f"Generated test {index}"
        description = _text_value(raw_case.get("description")) or f"Validate {name}"
        url = _text_value(raw_case.get("url")) or default_url
        steps = raw_case.get("steps", [])
        if isinstance(steps, str):
            steps = [steps]
        if not isinstance(steps, list):
            continue
        clean_steps = [_text_value(step) for step in steps]
        clean_steps = [step for step in clean_steps if step]
        if not clean_steps or not url:
            continue

        priority = _text_value(raw_case.get("priority")).lower() or "medium"
        if priority not in {"critical", "high", "medium", "low"}:
            priority = "medium"

        repaired_cases.append(
            {
                "name": name,
                "description": description,
                "url": url,
                "steps": clean_steps,
                "expected_outcome": (
                    _text_value(raw_case.get("expected_outcome"))
                    or "The expected behavior is observed."
                ),
                "priority": priority,
            }
        )

    raw_sub_pages = data.get("sub_pages", data.get("subpages", []))
    if raw_sub_pages is None:
        raw_sub_pages = []
    if not isinstance(raw_sub_pages, list):
        raw_sub_pages = []

    repaired_sub_pages: list[dict[str, Any]] = []
    for raw_sub_page in raw_sub_pages:
        if isinstance(raw_sub_page, str):
            url = raw_sub_page.strip()
            reason = "Discovered internal page"
            requires_auth = False
        elif isinstance(raw_sub_page, dict):
            url = _text_value(raw_sub_page.get("url"))
            reason = (
                _text_value(raw_sub_page.get("reason"))
                or _text_value(raw_sub_page.get("description"))
                or _text_value(raw_sub_page.get("name"))
                or "Discovered internal page"
            )
            requires_auth = _bool_value(raw_sub_page.get("requires_auth", False))
        else:
            continue

        if url:
            repaired_sub_pages.append(
                {
                    "url": url,
                    "reason": reason,
                    "requires_auth": requires_auth,
                }
            )

    return {
        "page_summary": (
            _text_value(data.get("page_summary")) or _text_value(data.get("summary")) or ""
        ),
        "test_cases": repaired_cases,
        "sub_pages": repaired_sub_pages,
    }


def _text_value(value: Any) -> str:
    """Return a trimmed string for a loosely typed model field."""
    return value.strip() if isinstance(value, str) else ""


def _bool_value(value: Any) -> bool:
    """Coerce common LLM boolean spellings without arbitrary truthiness."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False
