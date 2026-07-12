"""Gemini-powered planner — multimodal LLM with website screenshot.

Uses the google-genai SDK to call Gemini models with a screenshot of the
target page + system/user prompts to produce a structured TestPlan JSON.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.llm.retry import retry_async

logger = logging.getLogger(__name__)


async def capture_screenshot(url: str, headless: bool = True) -> bytes:
    """Navigate to a URL with Playwright and capture a full-page screenshot.

    Args:
        url: The URL to screenshot.
        headless: Whether to run the browser headless.

    Returns:
        PNG screenshot bytes.

    Raises:
        RuntimeError: If screenshot capture fails.
    """
    from playwright.async_api import async_playwright

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Give JS-heavy pages a moment to render
            await page.wait_for_timeout(2000)
            screenshot = await page.screenshot(full_page=True, type="png")
            return screenshot
    except Exception as e:
        raise RuntimeError(f"Failed to capture screenshot of {url}: {e}") from e
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                logger.debug("Failed to close planner screenshot browser", exc_info=True)


async def call_gemini_planner(
    url: str,
    screenshot_bytes: bytes | None,
    system_prompt: str,
    user_prompt: str,
    config: dict[str, Any],
) -> str:
    """Call Gemini with a screenshot + prompts to produce a test plan.

    Args:
        url: The URL being planned.
        screenshot_bytes: PNG screenshot bytes (or None if capture failed).
        system_prompt: The planner system prompt.
        user_prompt: The user/task prompt.
        config: Provider config dict with 'model', 'api_key_env' etc.

    Returns:
        Raw text response from Gemini (expected to be JSON).

    Raises:
        RuntimeError: If the Gemini API call fails.
    """
    from google import genai
    from google.genai import types

    api_key_env = config.get("api_key_env", "GOOGLE_API_KEY")
    api_key = os.environ.get(api_key_env, "") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            f"Gemini API key not found. Set '{api_key_env}' or "
            f"'GOOGLE_API_KEY' environment variable."
        )

    model_name = config.get("model", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)

    # Build content parts: system prompt + screenshot + user prompt
    parts: list[types.Part] = []

    # System instruction as first text part
    parts.append(types.Part.from_text(text=system_prompt))

    # Screenshot (multimodal)
    if screenshot_bytes:
        parts.append(types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"))
        parts.append(
            types.Part.from_text(
                text=(
                    "Above is a screenshot of the website. "
                    "Use it to understand the page layout, visible elements, "
                    "and UI components when generating your test plan."
                )
            )
        )
    else:
        parts.append(
            types.Part.from_text(
                text=(
                    "(Screenshot unavailable — generate tests based on the "
                    "URL and your knowledge of common web patterns.)"
                )
            )
        )

    # User prompt with URL and instructions
    parts.append(types.Part.from_text(text=user_prompt))

    try:
        response = await retry_async(
            lambda: client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                ),
            ),
            operation_name="Gemini planner",
        )

        text = response.text or ""
        if not text.strip():
            raise RuntimeError("Gemini returned an empty response")

        return text

    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        raise RuntimeError(f"Gemini API call failed: {e}") from e
