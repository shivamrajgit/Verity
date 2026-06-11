"""Approve node — human-in-the-loop gating for sub-page planners."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import Command, interrupt

from src.config import AppConfig

logger = logging.getLogger(__name__)


def approve_node(state: dict[str, Any], app_config: AppConfig) -> dict[str, Any] | Command:
    """Gate sub-page planner requests through human approval (or auto-approve/decline).

    - Root planners (depth == 0) are always auto-approved.
    - Behavior for sub-page planners depends on app_config.approval.mode.

    Args:
        state: Current LangGraph state.
        app_config: Application configuration.

    Returns:
        Unchanged state (approved) or Command(goto="dequeue") to skip.
    """
    current_request = state.get("current_request")
    if current_request is None:
        # Shouldn't happen, but defensive
        return {}

    depth = current_request.get("depth", 0)
    url = current_request.get("url", "")

    # Root planner is always auto-approved
    if depth == 0:
        return {}

    mode = app_config.approval.mode

    if mode == "auto_approve":
        return {}

    if mode == "auto_decline":
        return Command(goto="dequeue_node")

    # mode == "interrupt" — ask the human
    approval = interrupt(
        {
            "url": url,
            "depth": depth,
            "reason": f"Sub-page planner at depth {depth} wants to test: {url}",
        }
    )

    if approval:
        return {}
    else:
        return Command(goto="dequeue_node")
