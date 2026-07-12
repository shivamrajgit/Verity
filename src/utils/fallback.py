"""Fallback test plan generation when LLM planner fails."""

from __future__ import annotations

from src.models.test_plan import TestCase, TestPlan


def generate_fallback_plan(url: str, user_instructions: str = "") -> TestPlan:
    """Generate a fallback test plan when the planner LLM fails.

    If user_instructions are provided, generates a single focused test case.
    Otherwise generates a minimal set of generic checks.

    Args:
        url: The URL to generate fallback tests for.
        user_instructions: Optional user focus text.

    Returns:
        A TestPlan with targeted or generic test cases.
    """
    if user_instructions:
        # User told us what to test — generate focused test cases
        test_cases = _build_focused_test_cases(url, user_instructions)
        return TestPlan(
            page_summary=f"Fallback plan for {url} — focused on: {user_instructions}",
            test_cases=test_cases,
            sub_pages=[],
        )

    # No instructions — minimal generic checks
    return TestPlan(
        page_summary=f"Fallback generic test plan for {url}",
        test_cases=[
            TestCase(
                name="Page loads successfully",
                description="Verify the page loads without errors",
                url=url,
                steps=[
                    f"Navigate to {url}",
                    "Wait for page to load",
                    "Check the page title is not empty",
                ],
                expected_outcome="Page loads and has a non-empty title",
                priority="high",
            ),
            TestCase(
                name="Page renders without visible errors",
                description=(
                    "Verify the page renders its primary content without visible error states"
                ),
                url=url,
                steps=[
                    f"Navigate to {url}",
                    "Wait for page to fully load",
                    "Check that the main content is visible",
                    "Check for visible error messages or broken layout",
                ],
                expected_outcome="The main content is visible and no obvious error state is shown",
                priority="medium",
            ),
        ],
        sub_pages=[],
    )


def _build_focused_test_cases(url: str, instructions: str) -> list[TestCase]:
    """Build concrete, actionable test cases based on user instructions.

    Detects common patterns (login, search, cart, etc.) and produces specific
    browser steps instead of vague "find the relevant element" instructions.

    Args:
        url: Target URL.
        instructions: User-provided testing focus text.

    Returns:
        List of TestCase objects with concrete steps.
    """
    lower = instructions.lower().strip()

    # Login / auth pattern. Never invent credentials: the fallback planner has
    # no trusted test-data source and must not submit guesses to a real site.
    if any(kw in lower for kw in ("login", "sign in", "signin", "sign-in", "auth")):
        return [
            TestCase(
                name="Login form renders without unsafe submission",
                description="Verify that the login form is visible without guessing credentials",
                url=url,
                steps=[
                    f"Navigate to {url}",
                    "Wait for the page to fully load",
                    "Locate the username and password fields if present",
                    "Do not enter credentials or submit the form",
                ],
                expected_outcome="The login form renders and no guessed credentials are submitted",
                priority="high",
            ),
        ]

    # Generic focused test — still more concrete than before
    return [
        TestCase(
            name=f"Test: {instructions}",
            description=f"Verify: {instructions}",
            url=url,
            steps=[
                f"Navigate to {url}",
                "Wait for the page to fully load",
                f"Look for UI elements related to: {instructions}",
                f"Interact with the feature: {instructions}",
                "Observe the result and check for expected behavior",
            ],
            expected_outcome=f"The feature '{instructions}' works correctly",
            priority="high",
        ),
    ]
