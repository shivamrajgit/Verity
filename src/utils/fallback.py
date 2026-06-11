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
                name="No JavaScript console errors",
                description="Check the browser console for JavaScript errors",
                url=url,
                steps=[
                    f"Navigate to {url}",
                    "Wait for page to fully load",
                    "Check browser console for error-level messages",
                ],
                expected_outcome="No JavaScript errors in the browser console",
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

    # Login / auth pattern
    if any(kw in lower for kw in ("login", "sign in", "signin", "sign-in", "auth")):
        return [
            TestCase(
                name="Valid login with correct credentials",
                description="Enter valid username and password, submit the form, verify redirect",
                url=url,
                steps=[
                    f"Navigate to {url}",
                    "Click on the username input field",
                    "Type 'standard_user' into the username field",
                    "Click on the password input field",
                    "Type 'secret_sauce' into the password field",
                    "Click the login/submit button",
                    "Verify the page navigates away from the login page",
                ],
                expected_outcome="User is logged in and redirected to the main/inventory page",
                priority="critical",
            ),
            TestCase(
                name="Login fails with invalid credentials",
                description="Enter wrong credentials to verify error handling",
                url=url,
                steps=[
                    f"Navigate to {url}",
                    "Click on the username input field",
                    "Type 'invalid_user' into the username field",
                    "Click on the password input field",
                    "Type 'wrong_password' into the password field",
                    "Click the login/submit button",
                    "Look for an error message on the page",
                ],
                expected_outcome="An error message is displayed indicating invalid credentials",
                priority="high",
            ),
            TestCase(
                name="Login fails with empty fields",
                description="Submit login form without entering credentials",
                url=url,
                steps=[
                    f"Navigate to {url}",
                    "Click the login/submit button without entering any credentials",
                    "Look for a validation or error message",
                ],
                expected_outcome="An error message is displayed about required fields",
                priority="medium",
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
