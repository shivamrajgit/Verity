"""Compile node — aggregates results and enqueues sub-page planners."""

from __future__ import annotations

import logging
from typing import Any

from src.config import AppConfig
from src.models.executor_result import ExecutorResult
from src.models.report import PlannerReport
from src.models.state import PlannerRequest
from src.models.test_plan import TestPlan
from src.utils.url import is_same_domain, normalize_url, resolve_url

logger = logging.getLogger(__name__)


def compile_node(state: dict[str, Any], app_config: AppConfig) -> dict[str, Any]:
    """Compile executor results into a PlannerReport and enqueue discovered sub-pages.

    Args:
        state: Current LangGraph state.
        app_config: Application configuration.

    Returns:
        Updated state dict with report appended, sub-pages enqueued, and current items cleared.
    """
    current_request = state.get("current_request", {})
    test_plan_dict = state.get("current_test_plan", {})
    results_list = state.get("current_results", [])

    url = current_request.get("url", "unknown")
    depth = current_request.get("depth", 0)

    # Build PlannerReport
    results = [ExecutorResult.model_validate(r) for r in results_list]
    page_summary = test_plan_dict.get("page_summary", "") if test_plan_dict else ""

    report = PlannerReport(
        url=url,
        depth=depth,
        page_summary=page_summary,
        results=results,
    )

    # Accumulate reports
    reports = list(state.get("reports", []))
    reports.append(report.model_dump())

    # Enqueue sub-pages for deeper testing
    queue = list(state.get("queue", []))
    visited_urls = list(state.get("visited_urls", []))
    enqueued_sub_pages: list[str] = []

    if test_plan_dict:
        test_plan = TestPlan.model_validate(test_plan_dict)
        new_depth = depth + 1

        if not _should_enqueue_sub_pages(current_request):
            _log_queue_status(url, [], queue)
            return {
                "queue": queue,
                "visited_urls": visited_urls,
                "reports": reports,
                "current_request": None,
                "current_test_plan": None,
                "current_results": [],
                "planner_context": "",
                "planner_clarification_count": 0,
            }

        # Determine storage state for child planners
        child_storage_state = current_request.get("parent_storage_state")
        exported_storage = current_request.get("_exported_storage_state")
        if exported_storage:
            child_storage_state = exported_storage

        for sub_page in test_plan.sub_pages:
            # Resolve relative URLs
            resolved_url = resolve_url(sub_page.url, url)
            normalized = normalize_url(resolved_url)

            # Skip if already visited
            if normalized in visited_urls:
                continue

            # Skip if exceeds max depth
            if new_depth > app_config.depth.max_depth:
                continue

            # Skip if different domain
            if not is_same_domain(resolved_url, app_config.target_url):
                continue

            # Determine storage state for this sub-page
            sp_storage = child_storage_state if sub_page.requires_auth else None

            request = PlannerRequest(
                url=resolved_url,
                depth=new_depth,
                parent_storage_state=sp_storage,
                user_instructions=current_request.get("user_instructions", ""),
            )
            queue.append(request.to_dict())
            enqueued_sub_pages.append(resolved_url)

    # Rich log the sub-page queue status
    _log_queue_status(url, enqueued_sub_pages, queue)

    return {
        "queue": queue,
        "visited_urls": visited_urls,
        "reports": reports,
        "current_request": None,
        "current_test_plan": None,
        "current_results": [],
        "planner_context": "",
        "planner_clarification_count": 0,
    }


def _log_queue_status(
    parent_url: str,
    enqueued: list[str],
    full_queue: list[dict],
) -> None:
    """Display the sub-page queue with Rich formatting.

    Args:
        parent_url: The URL that discovered these sub-pages.
        enqueued: List of newly enqueued sub-page URLs.
        full_queue: The full remaining queue.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    if enqueued:
        table = Table(
            title=f"Sub-pages discovered from {parent_url}",
            show_lines=False,
            title_style="bold magenta",
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("URL", style="cyan")

        for i, sp_url in enumerate(enqueued, 1):
            table.add_row(str(i), sp_url)

        console.print(table)
    else:
        console.print(f"[dim]No sub-pages discovered from {parent_url}[/dim]")

    if full_queue:
        pending = "\n".join(
            f"  {i}. {q.get('url', '?')} (depth {q.get('depth', '?')})"
            for i, q in enumerate(full_queue, 1)
        )
        console.print(
            Panel(
                pending,
                title=f"📋 Planner Queue ({len(full_queue)} pending)",
                border_style="yellow",
            )
        )


def _should_enqueue_sub_pages(current_request: dict[str, Any]) -> bool:
    """Return True when recursion should continue for discovered sub-pages.

    If the user gave a narrow objective (e.g., "test login flow"), avoid
    recursive crawling unless they explicitly ask for deep/full-site coverage.
    """
    instructions = (current_request.get("user_instructions") or "").strip().lower()
    if not instructions:
        return True

    broad_signals = (
        "full site",
        "entire site",
        "all pages",
        "deep",
        "crawl",
        "explore",
        "end-to-end",
        "e2e",
        "regression",
        "sub-page",
        "subpage",
    )

    return any(signal in instructions for signal in broad_signals)
