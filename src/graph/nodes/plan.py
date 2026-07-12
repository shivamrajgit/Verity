"""Plan node — generates a TestPlan via LLM (Gemini with screenshot or legacy).

When the planner is configured with ``provider: gemini``, the node:
1. Captures a screenshot of the target URL using Playwright.
2. Sends screenshot + system prompt + user prompt to Gemini.
3. If Gemini returns ``needs_input: true``, interrupts for user clarification.
4. Parses the JSON response into a ``TestPlan``.

For non-Gemini providers, falls back to the text-only LLM call path.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langgraph.types import interrupt

from src.config import AppConfig
from src.models.test_plan import TestPlan, repair_test_plan_payload
from src.prompts import PLANNER_SYSTEM_PROMPT, build_planner_prompt
from src.utils.fallback import generate_fallback_plan

logger = logging.getLogger(__name__)


async def plan_node(state: dict[str, Any], app_config: AppConfig) -> dict[str, Any]:
    """Generate a TestPlan — Gemini multimodal path or legacy text-only path.

    Uses state-based clarification tracking so that user answers survive
    LangGraph interrupt/resume cycles.  Each call uses at most ONE
    ``interrupt()`` so the scratchpad stays in sync.

    Fallback chain:
    1. Primary planner LLM (Gemini w/ screenshot, or legacy text-only)
    2. Fallback LLM (if configured, always text-only)
    3. Generic fallback plan (no LLM)

    Args:
        state: Current LangGraph state.
        app_config: Application configuration.

    Returns:
        Updated state dict with current_test_plan set.
    """
    current_request = state["current_request"]
    url = current_request["url"]
    extra_context = state.get("planner_context", "")
    clarification_count = state.get("planner_clarification_count", 0)
    max_clarifications = 3

    logger.info(f"Planning tests for: {url}")

    task_prompt = build_planner_prompt(current_request)
    if extra_context:
        task_prompt += f"\n\nAdditional context from the user:\n{extra_context}"

    # Attempt 1: Primary planner (Gemini or legacy)
    test_plan, clarification = await _call_primary_planner(url, task_prompt, app_config)

    # If Gemini asked for clarification and we haven't hit the limit, interrupt
    if test_plan is None and clarification and clarification_count < max_clarifications:
        user_answer = interrupt(
            {
                "type": "planner_clarification",
                "url": url,
                "question": clarification,
            }
        )
        # Save context to state -- will be available on next invocation
        new_context = extra_context + f"\nQ: {clarification}\nA: {user_answer}"
        return {
            "planner_context": new_context,
            "planner_clarification_count": clarification_count + 1,
        }

    # Attempt 2: Fallback LLM (text-only, non-Gemini)
    if test_plan is None and app_config.llm.fallback:
        logger.warning(f"Primary planner failed for {url}, trying fallback LLM")
        test_plan = await _call_legacy_planner(
            task_prompt,
            app_config,
            use_fallback=True,
            default_url=url,
        )

    # Attempt 3: Generic fallback plan
    if test_plan is None:
        logger.warning(f"All planners failed for {url}, using generic fallback plan")
        test_plan = generate_fallback_plan(url, current_request.get("user_instructions", ""))

    logger.info(
        f"Plan for {url}: {len(test_plan.test_cases)} test cases, "
        f"{len(test_plan.sub_pages)} sub-pages"
    )

    # Log the full plan details for visibility
    _log_test_plan(test_plan, url)

    return {
        "current_test_plan": test_plan.model_dump(),
        "planner_context": "",
        "planner_clarification_count": 0,
    }


def _log_test_plan(plan: TestPlan, url: str) -> None:
    """Log the full test plan with Rich formatting.

    Args:
        plan: The generated test plan.
        url: The target URL.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()

    # Summary
    if plan.page_summary:
        console.print(Panel(plan.page_summary, title=f"Plan: {url}", border_style="cyan"))

    # Test cases table
    table = Table(
        title="Generated Test Cases",
        show_lines=True,
        title_style="bold cyan",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Priority", width=8)
    table.add_column("Steps", ratio=2)
    table.add_column("Expected", ratio=1)

    priority_colors = {
        "critical": "red",
        "high": "yellow",
        "medium": "blue",
        "low": "dim",
    }

    for i, tc in enumerate(plan.test_cases, 1):
        steps_text = "\n".join(f"{j}. {s}" for j, s in enumerate(tc.steps, 1))
        color = priority_colors.get(tc.priority, "white")
        table.add_row(
            str(i),
            tc.name,
            Text(tc.priority.upper(), style=color),
            steps_text,
            tc.expected_outcome,
        )

    console.print(table)


async def _call_primary_planner(
    url: str,
    task_prompt: str,
    config: AppConfig,
) -> tuple[TestPlan | None, str | None]:
    """Call the primary planner — routes to Gemini or legacy based on config.

    Args:
        url: The target URL.
        task_prompt: The planner prompt.
        config: App configuration.

    Returns:
        Tuple of (Parsed TestPlan or None, clarification question or None).
    """
    provider = config.llm.planner.provider.lower()

    if provider == "gemini":
        return await _call_gemini_planner(url, task_prompt, config)
    plan = await _call_legacy_planner(
        task_prompt,
        config,
        use_fallback=False,
        default_url=url,
    )
    return (plan, None)


async def _call_gemini_planner(
    url: str,
    task_prompt: str,
    config: AppConfig,
) -> tuple[TestPlan | None, str | None]:
    """Call Gemini with a screenshot of the target URL.

    Returns either a parsed TestPlan or a clarification question (never both).
    The caller (plan_node) handles the interrupt/resume cycle via state.

    Args:
        url: The target URL to screenshot and plan.
        task_prompt: The user/task prompt (may include accumulated context).
        config: App configuration.

    Returns:
        Tuple of (TestPlan or None, clarification question or None).
    """
    from src.llm.gemini import call_gemini_planner, capture_screenshot

    # Step 1: Capture screenshot
    screenshot_bytes: bytes | None = None
    try:
        screenshot_bytes = await capture_screenshot(url, headless=config.browser.headless)
    except Exception:
        logger.warning(f"Screenshot capture failed for {url}", exc_info=True)

    # Step 2: Call Gemini (single call)
    try:
        raw_text = await call_gemini_planner(
            url=url,
            screenshot_bytes=screenshot_bytes,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_prompt=task_prompt,
            config=config.llm.planner.to_dict(),
        )
        logger.debug(f"Gemini raw response ({len(raw_text)} chars)")

        # Check if Gemini is asking for clarification
        clarification = _extract_clarification(raw_text)
        if clarification:
            return (None, clarification)

        plan = _extract_test_plan(raw_text, default_url=url)
        if plan is None:
            logger.error(
                "Gemini returned text but it could not be parsed into a TestPlan. "
                f"First 500 chars: {raw_text[:500]}"
            )
        return (plan, None)

    except Exception:
        logger.exception("Gemini planner call failed")
        return (None, None)


def _extract_clarification(text: str) -> str | None:
    """Check if the LLM response is a clarification request.

    Args:
        text: Raw LLM output text.

    Returns:
        The question string if clarification is needed, else None.
    """
    if not text or not text.strip():
        return None

    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and data.get("needs_input") is True:
            return data.get("question", "The planner needs additional information.")
    except (json.JSONDecodeError, Exception):
        pass

    return None


async def _call_legacy_planner(
    task_prompt: str,
    config: AppConfig,
    use_fallback: bool,
    default_url: str | None = None,
) -> TestPlan | None:
    """Make a text-only LLM call to produce a TestPlan (non-Gemini path).

    Args:
        task_prompt: The planner prompt.
        config: App configuration.
        use_fallback: If True, use fallback LLM config.

    Returns:
        Parsed TestPlan or None on failure.
    """
    from browser_use.llm import SystemMessage, UserMessage

    from src.llm.factory import create_llm

    try:
        llm_config = (
            config.llm.fallback.to_dict()
            if use_fallback and config.llm.fallback
            else config.llm.planner.to_dict()
        )
        llm = create_llm(llm_config)

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            UserMessage(content=task_prompt),
        ]

        if llm_config.get("provider", "").lower() == "openrouter":
            try:
                response = await llm.ainvoke(messages, output_format=TestPlan)
                structured = getattr(response, "completion", response)
                if isinstance(structured, TestPlan):
                    return structured if structured.test_cases else None
                if isinstance(structured, dict):
                    repaired = repair_test_plan_payload(structured, default_url)
                    if repaired and repaired["test_cases"]:
                        return TestPlan.model_validate(repaired)
                    return None
            except Exception:
                logger.warning(
                    "Structured planner response failed; retrying with repair-capable text output",
                    exc_info=True,
                )

        response = await llm.ainvoke(messages)
        raw_text = _response_text(response)

        logger.debug(f"Planner LLM raw response length: {len(raw_text)}")
        return _extract_test_plan(raw_text, default_url=default_url)

    except Exception:
        logger.exception("Legacy planner LLM call failed")
        return None


def _extract_test_plan(text: str, default_url: str | None = None) -> TestPlan | None:
    """Extract a TestPlan JSON from LLM text output.

    Tries multiple strategies: direct parse, code-block extraction, brace matching.

    Args:
        text: Raw LLM output text.

    Returns:
        Parsed TestPlan or None.
    """
    if not text or not text.strip():
        return None

    # Strategy 1: The entire response might be valid JSON
    try:
        data = json.loads(text.strip())
        return _validate_repaired_plan(data, default_url)
    except (json.JSONDecodeError, Exception):
        pass

    # Strategy 2: Extract from markdown code blocks
    patterns = [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                return _validate_repaired_plan(data, default_url)
            except (json.JSONDecodeError, Exception):
                continue

    # Strategy 3: Find the outermost { ... } containing "test_cases"
    if "test_cases" in text:
        brace_start = text.find("{")
        if brace_start != -1:
            depth = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[brace_start : i + 1]
                        try:
                            data = json.loads(candidate)
                            return _validate_repaired_plan(data, default_url)
                        except (json.JSONDecodeError, Exception):
                            pass
                        break

    return None


def _validate_repaired_plan(data: Any, default_url: str | None = None) -> TestPlan | None:
    """Repair a decoded planner payload, then enforce the application schema."""
    repaired = repair_test_plan_payload(data, default_url=default_url)
    if repaired is None or not repaired["test_cases"]:
        return None
    try:
        return TestPlan.model_validate(repaired)
    except Exception:
        logger.debug("Repaired planner payload still failed validation", exc_info=True)
        return None


def _response_text(response: Any) -> str:
    """Extract text from browser-use and OpenAI-compatible response objects."""
    content = getattr(response, "completion", None)
    if content is None:
        content = getattr(response, "content", None)
    return content if isinstance(content, str) else str(content or response)
