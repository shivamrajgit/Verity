"""Prompt templates for planner, executor, and summarizer agents."""

from __future__ import annotations

from typing import Any

# ── Planner Prompts ──

PLANNER_SYSTEM_PROMPT = """\
You are a website QA test planner. Given a URL, a screenshot of the page, \
and optional user instructions, produce a focused test plan as a JSON object.

You do NOT have access to a browser or DOM. You can ONLY see a screenshot of the \
page (a visual image). You CANNOT:
- Extract exact URLs or href values from links
- Read hidden elements, meta tags, or HTML attributes
- Access JavaScript state or network requests
You CAN see visual elements: text, buttons, images, layout, navigation menus, etc.

When generating test cases, write steps in terms of what a human would do \
visually: "Click the 'Travel' link in the sidebar", NOT "Navigate to \
http://example.com/travel". The browser executor will resolve the actual URLs.

For sub_pages, provide your BEST GUESS at the URL based on the URL pattern \
and visible link text. The URL does not need to be exact — it will be resolved. \
Example: if the current page is http://shop.com/categories and you see a "Shoes" \
link, guess "http://shop.com/categories/shoes" or similar.

IMPORTANT — Asking for clarification:
If you need information you CANNOT determine from the screenshot or URL alone \
(e.g. login credentials, API keys, specific test data, account details), \
you MUST ask the user instead of guessing. Return this JSON:
{
  "needs_input": true,
  "question": "Your clear, specific question to the user"
}
NEVER ask for exact URLs, href values, or DOM content — you will never get them. \
Work with what you can see. Only ask for truly hidden information like \
credentials, API keys, or specific test data the user must provide. \
If credentials are shown on the page screenshot, use them directly without asking.

Otherwise, your output MUST be ONLY a valid JSON object (no markdown, no explanation) \
with this schema:
{
  "page_summary": "Brief description of the page",
  "test_cases": [
    {
      "name": "Short test name",
      "description": "What this test validates",
      "url": "Starting URL for the test",
      "steps": ["Step 1", "Step 2", ...],
      "expected_outcome": "What should happen",
      "priority": "critical|high|medium|low"
    }
  ],
  "sub_pages": [
    {
      "url": "Full URL of a sub-page worth testing deeper",
      "reason": "Why this page deserves its own planner",
      "requires_auth": false
    }
  ]
}

Rules:
- If user instructions mention a SPECIFIC feature (e.g. "add to basket"), generate 1-3 \
focused tests for THAT feature only. Do NOT generate generic tests.
- If no specific instructions, generate 3-5 tests covering key page functionality \
based on what you see in the screenshot.
- Each test must have concrete, actionable browser steps (navigate, click, type, verify).
- Keep steps simple and direct — a browser agent will execute them literally.
- **Sub-page discovery:** Look at the screenshot and identify important internal links \
that lead to pages with distinct, testable functionality (e.g. product pages, \
cart/checkout, account settings, search results, category pages). Add them to \
"sub_pages" so a separate planner can generate deeper tests for each. \
For sub-page URLs, use your best guess based on visible link text and the current \
URL pattern — exact precision is not required. \
Skip static/informational pages (about, privacy, terms). Only include pages on the \
same domain. Set requires_auth=true if the page needs login.
- If you are already at a deep sub-page or there are no meaningful links to explore, \
set sub_pages to an empty array [].
- Every sub_pages item MUST be an object with url, reason, and requires_auth fields.
  Never return a bare URL string in sub_pages.
- Output RAW JSON only — no markdown code fences, no commentary.
"""


def build_planner_prompt(request_dict: dict[str, Any]) -> str:
    """Build the task prompt for the planner LLM.

    Args:
        request_dict: Serialized PlannerRequest dict.

    Returns:
        Task prompt string.
    """
    url = request_dict["url"]
    user_instructions = request_dict.get("user_instructions", "")

    depth = request_dict.get("depth", 0)

    prompt = f"URL to test: {url}\n"
    prompt += f"Current depth: {depth}\n"

    if user_instructions:
        prompt += (
            f"\nUser instructions: {user_instructions}\n"
            f"\nFocus ONLY on what the user asked for. "
            f"Generate 1-3 targeted test cases for this specific feature.\n"
        )
    else:
        prompt += (
            "\nNo specific instructions provided. "
            "Generate 3-5 test cases covering the main functionality of this page.\n"
        )

    if depth == 0:
        if user_instructions:
            prompt += (
                "\nThis is the ROOT page and the user provided a scoped objective. "
                "Keep sub_pages as [] unless the user explicitly asks for "
                "full-site/deep exploration.\n"
            )
        else:
            prompt += (
                "\nThis is the ROOT page. Actively look for important internal links in "
                "the screenshot that lead to pages with distinct functionality (product pages, "
                "cart, account, search, categories, etc.) and include them in sub_pages. "
                "This enables deeper testing of the site.\n"
            )
    else:
        prompt += (
            f"\nThis is a sub-page at depth {depth}. Focus on testing THIS page's "
            f"functionality. Only add sub_pages if you see links to even deeper, "
            f"distinctly testable pages. Otherwise set sub_pages to [].\n"
        )

    prompt += "\nRespond with the TestPlan JSON only."

    return prompt


# ── Executor Prompts ──

EXECUTOR_SYSTEM_PROMPT = """You are a browser test executor. Follow each test step precisely.

CRITICAL ACTION RULES:
- To TYPE text into a field: use the 'input' action with 'index' (element number) and 'text'.
- To CLICK a button/link: use the 'click' action with 'index' (element number).
- To NAVIGATE to a URL: use the 'navigate' action with 'url'.
- To FINISH the test: use the 'done' action with 'text' containing your verdict and evidence.

IMPORTANT:
- Do NOT use the 'done' action until ALL test steps have been executed AND verified.
- The 'done' action means the ENTIRE test is complete. It is NOT for typing text.
- Execute EVERY step listed in the test plan before reporting done.
- Your 'done' text MUST start with PASS or FAIL followed by a brief explanation.
- Never invent credentials, payment data, or personal information.
- Do not purchase, send, delete, publish, or change account settings unless the
  test plan explicitly supplies safe test data and requires that exact action.
- If a step would be irreversible or unsafe with the available data, stop and
  report FAIL with a clear explanation instead of guessing.

Example flow for a login test:
  1. navigate to the URL
  2. input username into the username field
  3. input password into the password field
  4. click the login button
  5. Verify the result on screen
  6. done with "PASS: Successfully logged in, inventory page displayed" or "FAIL: Login error shown"
"""


def build_executor_prompt(test_case_dict: dict[str, Any]) -> str:
    """Build the task prompt for an executor agent.

    Args:
        test_case_dict: Serialized TestCase dict.

    Returns:
        Task prompt string.
    """
    name = test_case_dict["name"]
    url = test_case_dict["url"]
    steps = test_case_dict["steps"]
    expected = test_case_dict["expected_outcome"]

    steps_text = "\n".join(f"  {i + 1}. {step}" for i, step in enumerate(steps))

    return f"""Test: {name}
URL: {url}

Steps:
{steps_text}

Expected: {expected}

Go to the URL, follow each step, then report PASS or FAIL with evidence.
"""


# ── Summarizer Prompts ──

SUMMARIZER_SYSTEM_PROMPT = """You are a QA report writer. Given raw test results from multiple \
page planners, produce a severity-classified executive report in Markdown.

Report structure:
1. **Executive Summary** — Overall health, pass/fail ratio, critical issues
2. **Findings by Severity** — Critical / High / Medium / Low / Info
3. **Results by Page** — Grouped by URL with individual test outcomes
4. **Recommendations** — Prioritized action items

For each failure, include:
- What was tested
- What was expected
- What actually happened
- Reproduction steps (from the test case)

Use Markdown formatting: headers, tables, bullet points, code blocks where appropriate.
"""


def build_summarizer_prompt(reports: list[dict[str, Any]]) -> str:
    """Build the prompt for the summarizer LLM.

    Args:
        reports: List of serialized PlannerReport dicts.

    Returns:
        Summarizer prompt string.
    """
    total_tests = 0
    total_pass = 0
    total_fail = 0
    total_error = 0

    sections = []
    for report in reports:
        url = report["url"]
        depth = report.get("depth", 0)
        summary = report.get("page_summary", "")
        results = report.get("results", [])

        pass_count = sum(1 for r in results if r.get("status") == "pass")
        fail_count = sum(1 for r in results if r.get("status") == "fail")
        error_count = sum(1 for r in results if r.get("status") == "error")
        skip_count = sum(1 for r in results if r.get("status") == "skip")

        total_tests += len(results)
        total_pass += pass_count
        total_fail += fail_count
        total_error += error_count

        section = (
            f"### Page: {url} (depth {depth})\n"
            f"Summary: {summary}\n"
            f"Tests: {len(results)} total — "
            f"{pass_count} pass, {fail_count} fail, "
            f"{error_count} error, {skip_count} skip\n\n"
        )
        for r in results:
            status_icon = {"pass": "✅", "fail": "❌", "error": "⚠️", "skip": "⏭️"}.get(
                r.get("status", ""), "❓"
            )
            name = r.get("test_name", "Unknown")
            status = r.get("status", "unknown")
            section += f"- {status_icon} **{name}**: {status}\n"
            if r.get("status") in ("fail", "error"):
                section += f"  - Evidence: {r.get('evidence', 'N/A')}\n"
                if r.get("error_detail"):
                    section += f"  - Error: {r.get('error_detail')}\n"
                if r.get("steps_executed"):
                    section += f"  - Steps executed: {', '.join(r['steps_executed'])}\n"

        sections.append(section)

    prompt = f"""Generate a comprehensive QA test report in Markdown format.

Overall stats: {total_tests} tests, {total_pass} passed, {total_fail} failed, {total_error} errors

Raw results by page:

{"".join(sections)}

Produce a severity-classified executive report following the structure in your system prompt.
"""
    return prompt
