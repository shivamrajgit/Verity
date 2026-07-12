"""Small retry helper for transient provider failures."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


def _status_code(error: Exception) -> int | None:
    value = getattr(error, "status_code", None)
    if isinstance(value, int):
        return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    if isinstance(value, int):
        return value
    return None


def _is_retryable(error: Exception) -> bool:
    code = _status_code(error)
    if code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    message = str(error).lower()
    return any(term in message for term in ("timeout", "temporarily unavailable", "rate limit"))


def is_provider_failover_error(error: Exception) -> bool:
    """Return whether another configured provider should take over."""
    code = _status_code(error)
    if code in {408, 429, 500, 502, 503, 504}:
        return True
    message = str(error).lower()
    return any(
        term in message
        for term in (
            "quota",
            "resource exhausted",
            "rate limit",
            "temporarily unavailable",
            "service unavailable",
        )
    )


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    operation_name: str,
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
) -> T:
    """Retry only transient provider failures with bounded jittered backoff."""
    for attempt in range(attempts):
        try:
            return await operation()
        except Exception as exc:
            if attempt == attempts - 1 or not _is_retryable(exc):
                raise
            delay = min(max_delay, base_delay * (2**attempt))
            delay += random.uniform(0, delay * 0.1)
            logger.warning(
                "%s failed transiently; retrying in %.1fs (%d/%d): %s",
                operation_name,
                delay,
                attempt + 1,
                attempts,
                exc,
            )
            await asyncio.sleep(delay)
    raise RuntimeError(f"{operation_name} retry loop ended unexpectedly")
