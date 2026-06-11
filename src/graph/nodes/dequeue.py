"""Dequeue node — pops next planner request from the FCFS queue."""

from __future__ import annotations

import logging
from typing import Any

from src.config import AppConfig
from src.models.state import PlannerRequest
from src.utils.url import normalize_url

logger = logging.getLogger(__name__)


def dequeue_node(state: dict[str, Any], app_config: AppConfig) -> dict[str, Any]:
    """Pop the next item from the planner queue, skipping duplicates and depth violations.

    Args:
        state: Current LangGraph state.
        app_config: Application configuration.

    Returns:
        Updated state dict with current_request set (or None if queue drained).
    """
    queue: list[dict] = list(state.get("queue", []))
    visited_urls: list[str] = list(state.get("visited_urls", []))
    max_depth = app_config.depth.max_depth

    # Try to find a valid request in the queue
    while queue:
        request_dict = queue.pop(0)
        request = PlannerRequest.from_dict(request_dict)

        # Normalize URL for dedup
        normalized = normalize_url(request.url)

        # Skip if already visited
        if normalized in visited_urls:
            continue

        # Skip if exceeds max depth
        if request.depth > max_depth:
            continue

        # Valid request found — mark as visited and set as current
        visited_urls.append(normalized)

        return {
            "queue": queue,
            "visited_urls": visited_urls,
            "current_request": request.to_dict(),
            "current_test_plan": None,
            "current_results": [],
        }

    # Queue is empty — signal end
    return {
        "queue": [],
        "visited_urls": visited_urls,
        "current_request": None,
        "current_test_plan": None,
        "current_results": [],
    }
