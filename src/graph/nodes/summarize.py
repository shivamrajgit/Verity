"""Summarize node — generates the final Markdown report via LLM.

Uses a direct Ollama / Gemini call (no browser-use wrappers) so the
summarizer is a plain text-in / text-out LLM invocation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.llm.chat import call_llm_chat
from src.prompts import SUMMARIZER_SYSTEM_PROMPT, build_summarizer_prompt

logger = logging.getLogger(__name__)


async def summarize_node(state: dict[str, Any], app_config: AppConfig) -> dict[str, Any]:
    """Generate a severity-classified Markdown report from all planner results.

    Args:
        state: Current LangGraph state.
        app_config: Application configuration.

    Returns:
        Updated state dict with final_report set.
    """
    reports = state.get("reports", [])

    if not reports:
        logger.warning("No reports to summarize — generating empty report")
        final_report = _generate_empty_report(app_config.target_url)
    else:
        final_report = await _generate_report_via_llm(reports, app_config)

    # Write report to file
    output_path = Path(app_config.report.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_report, encoding="utf-8")

    return {"final_report": final_report}


async def _generate_report_via_llm(reports: list[dict[str, Any]], config: AppConfig) -> str:
    """Generate the report using the summarizer LLM.

    Falls back to a simple concatenation if LLM fails.

    Args:
        reports: List of serialized PlannerReport dicts.
        config: Application configuration.

    Returns:
        Markdown report string.
    """
    try:
        provider_config = config.llm.summarizer.to_dict()
        prompt = build_summarizer_prompt(reports)

        raw_text = await call_llm_chat(
            system_prompt=SUMMARIZER_SYSTEM_PROMPT,
            user_prompt=prompt,
            provider_config=provider_config,
        )
        if not raw_text or not raw_text.strip():
            raise ValueError("Summarizer LLM returned empty response")
        return raw_text

    except Exception:
        logger.exception("Summarizer LLM failed — generating fallback report")
        return _generate_fallback_report(reports)


def _generate_empty_report(target_url: str) -> str:
    """Generate a report when no tests were executed."""
    return f"""# Website Test Report

**Target:** {target_url}
**Status:** No tests were executed.

No planner reports were generated. This may indicate:
- The target URL was unreachable
- All planner agents failed
- The queue was empty
"""


def _generate_fallback_report(reports: list[dict[str, Any]]) -> str:
    """Generate a simple report without LLM when the summarizer fails.

    Args:
        reports: List of serialized PlannerReport dicts.

    Returns:
        Markdown report string.
    """
    total_tests = 0
    total_pass = 0
    total_fail = 0
    total_error = 0

    sections = []
    for report in reports:
        url = report.get("url", "unknown")
        results = report.get("results", [])
        p = sum(1 for r in results if r.get("status") == "pass")
        f = sum(1 for r in results if r.get("status") == "fail")
        e = sum(1 for r in results if r.get("status") == "error")

        total_tests += len(results)
        total_pass += p
        total_fail += f
        total_error += e

        section = f"## {url}\n\n"
        section += f"**Summary:** {report.get('page_summary', 'N/A')}\n\n"
        section += "| Test | Status | Evidence |\n|---|---|---|\n"
        for r in results:
            status_icon = {"pass": "✅", "fail": "❌", "error": "⚠️", "skip": "⏭️"}.get(
                r.get("status", ""), "❓"
            )
            evidence = (r.get("evidence", "") or "")[:100]
            name = r.get("test_name", "Unknown")
            status = r.get("status", "")
            section += f"| {name} | {status_icon} {status} | {evidence} |\n"
        sections.append(section)

    return f"""# Website Test Report (Fallback)

> ⚠️ This report was generated without the summarizer LLM. Results are presented raw.

## Executive Summary

- **Total tests:** {total_tests}
- **Passed:** {total_pass}
- **Failed:** {total_fail}
- **Errors:** {total_error}
- **Pass rate:** {(total_pass / total_tests * 100) if total_tests else 0:.1f}%

{"".join(sections)}
"""
