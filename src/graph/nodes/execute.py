"""Execute node — runs parallel browser-use agents for each test case."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.config import AppConfig
from src.llm.factory import create_llm
from src.models.executor_result import ExecutorResult
from src.models.test_plan import TestPlan
from src.prompts import EXECUTOR_SYSTEM_PROMPT, build_executor_prompt

logger = logging.getLogger(__name__)


async def execute_node(state: dict[str, Any], app_config: AppConfig) -> dict[str, Any]:
    """Execute all test cases from the current test plan in parallel.

    Uses asyncio.Semaphore to bound concurrency and stagger delays to avoid
    overwhelming the target site or local resources.

    Args:
        state: Current LangGraph state.
        app_config: Application configuration.

    Returns:
        Updated state dict with current_results populated.
    """
    test_plan_dict = state.get("current_test_plan")
    if not test_plan_dict:
        logger.warning("No test plan found — skipping execution")
        return {"current_results": []}

    test_plan = TestPlan.model_validate(test_plan_dict)
    current_request = state.get("current_request", {})
    storage_state = current_request.get("parent_storage_state")

    if not test_plan.test_cases:
        logger.info("Test plan has no test cases — skipping execution")
        return {"current_results": []}

    logger.info(
        f"Executing {len(test_plan.test_cases)} test cases"
    )

    # Log executor assignments for visibility
    _log_executor_assignments(test_plan, app_config)

    semaphore = asyncio.Semaphore(app_config.concurrency.max_executors)

    # Create tasks with stagger delay
    tasks = [
        _run_executor(
            test_case=tc.model_dump(),
            semaphore=semaphore,
            stagger_index=i,
            config=app_config,
            storage_state=storage_state,
        )
        for i, tc in enumerate(test_plan.test_cases)
    ]

    # Execute all tasks, collecting results.
    # return_exceptions prevents one failure from killing others.
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict] = []
    exported_storage_state: dict | None = None

    for i, raw in enumerate(raw_results):
        if isinstance(raw, Exception):
            tc = test_plan.test_cases[i]
            logger.error(f"Executor crashed for '{tc.name}': {raw}")
            result = ExecutorResult(
                test_name=tc.name,
                status="error",
                evidence="Executor task raised an unhandled exception",
                error_detail=str(raw),
                steps_executed=[],
                duration_seconds=0.0,
            )
            results.append(result.model_dump())
        elif isinstance(raw, tuple):
            result_dict, storage = raw
            results.append(result_dict)
            # Keep the latest storage state from auth-related executors
            if storage is not None:
                exported_storage_state = storage
        else:
            results.append(raw)

    update: dict[str, Any] = {"current_results": results}

    # Store exported storage state for auth propagation to child planners
    if exported_storage_state and current_request:
        current_request["_exported_storage_state"] = exported_storage_state
        update["current_request"] = current_request

    return update


async def _run_executor(
    test_case: dict[str, Any],
    semaphore: asyncio.Semaphore,
    stagger_index: int,
    config: AppConfig,
    storage_state: dict | None,
) -> tuple[dict, dict | None]:
    """Run a single test case executor with semaphore gating and stagger delay.

    Args:
        test_case: Serialized TestCase dict.
        semaphore: Asyncio semaphore for concurrency control.
        stagger_index: Index for stagger delay calculation.
        config: Application configuration.
        storage_state: Optional browser storage state for auth.

    Returns:
        Tuple of (ExecutorResult dict, exported storage state or None).
    """
    from browser_use import Agent, BrowserSession

    test_name = test_case.get("name", "Unknown")

    # Stagger delay
    delay = stagger_index * config.concurrency.stagger_delay_seconds
    if delay > 0:
        await asyncio.sleep(delay)

    session = None
    exported_state = None
    start_time = time.time()

    async with semaphore:
        try:
            # Set up browser session — restrict navigation to the target domain
            target_domain = _extract_domain(test_case.get("url", ""))
            session_kwargs: dict[str, Any] = {"headless": config.browser.headless}
            allowed_domains = _build_allowed_domains(target_domain, config)
            if allowed_domains:
                session_kwargs["allowed_domains"] = allowed_domains
            if storage_state:
                session_kwargs["storage_state"] = storage_state
            if config.browser.proxy:
                session_kwargs["proxy"] = {"server": config.browser.proxy}

            session = BrowserSession(**session_kwargs)

            llm = create_llm(config.llm.executor.to_dict())
            task_prompt = build_executor_prompt(test_case)

            # Build fallback LLM if configured
            fallback_llm = None
            if config.llm.fallback:
                try:
                    fallback_llm = create_llm(config.llm.fallback.to_dict())
                except Exception:
                    logger.debug("Failed to create fallback LLM", exc_info=True)

            agent = Agent(
                task=task_prompt,
                llm=llm,
                browser_session=session,
                extend_system_message=EXECUTOR_SYSTEM_PROMPT,
                fallback_llm=fallback_llm,
                use_vision=True,
                flash_mode=True,
                use_thinking=False,
                use_judge=False,
                max_actions_per_step=1,
                max_failures=5,
                include_tool_call_examples=True,
            )

            logger.info(f"Starting executor: {test_name}")
            result = await asyncio.wait_for(
                agent.run(max_steps=15),
                timeout=float(config.concurrency.step_timeout),
            )
            duration = time.time() - start_time

            # Try to parse structured output
            executor_result = _parse_executor_result(result, test_name, duration)

            # Export storage state if this was an auth-related test
            if _is_auth_test(test_case) and session:
                try:
                    ctx = await session.browser_context()
                    if ctx:
                        exported_state = await ctx.storage_state()
                except Exception:
                    logger.debug("Failed to export storage state", exc_info=True)

            return (executor_result.model_dump(), exported_state)

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.error(
                f"Executor timed out for '{test_name}' after "
                f"{config.concurrency.step_timeout}s"
            )
            result = ExecutorResult(
                test_name=test_name,
                status="error",
                evidence="",
                error_detail=(
                    "Executor exceeded configured timeout "
                    f"({config.concurrency.step_timeout}s)"
                ),
                steps_executed=[],
                duration_seconds=duration,
            )
            return (result.model_dump(), None)

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Executor failed for '{test_name}': {e}")
            result = ExecutorResult(
                test_name=test_name,
                status="error",
                evidence="",
                error_detail=str(e),
                steps_executed=[],
                duration_seconds=duration,
            )
            return (result.model_dump(), None)

        finally:
            if session:
                try:
                    await session.close()
                except Exception:
                    logger.debug(f"Error closing executor session for '{test_name}'", exc_info=True)


def _parse_executor_result(result: Any, test_name: str, duration: float) -> ExecutorResult:
    """Parse ExecutorResult from agent output.

    Args:
        result: Agent.run() result.
        test_name: Name of the test case.
        duration: Execution duration in seconds.

    Returns:
        ExecutorResult instance.
    """
    # Try structured output
    if hasattr(result, "output") and result.output:
        try:
            if isinstance(result.output, ExecutorResult):
                result.output.duration_seconds = duration
                return result.output
            if isinstance(result.output, dict):
                data = result.output
                data["duration_seconds"] = duration
                return ExecutorResult.model_validate(data)
        except Exception:
            logger.debug("Failed to parse executor structured output", exc_info=True)

    # Fallback: construct from whatever info we have
    evidence = ""
    if hasattr(result, "extracted_content") and result.extracted_content:
        evidence = str(result.extracted_content)[:1000]
    elif hasattr(result, "history") and result.history:
        for entry in reversed(result.history):
            if hasattr(entry, "extracted_content") and entry.extracted_content:
                evidence = str(entry.extracted_content)[:1000]
                break

    # Determine status from agent judgment and judge verdict
    status: str = "pass"
    if hasattr(result, "is_done") and callable(result.is_done):
        if result.is_done():
            # Agent finished — check if it reported success
            if hasattr(result, "is_successful") and callable(result.is_successful):
                status = "pass" if result.is_successful() else "fail"
        else:
            # Agent hit max_steps without completing
            status = "fail"
            if not evidence:
                evidence = "Agent exhausted step budget without completing the test"
    elif hasattr(result, "final_result") and result.final_result:
        # browser-use may expose final_result with success flag
        fr = result.final_result
        if hasattr(fr, "success") and fr.success is False:
            status = "fail"

    # Override with judge verdict if available — the judge is more reliable
    # than the agent's self-assessment
    if hasattr(result, "is_validated") and callable(result.is_validated):
        judge_verdict = result.is_validated()
        if judge_verdict is not None and judge_verdict is False:
            status = "fail"
            # Append judge reasoning to evidence
            if hasattr(result, "judgement") and callable(result.judgement):
                judge_info = result.judgement()
                if judge_info and isinstance(judge_info, dict):
                    reason = judge_info.get("failure_reason", "")
                    if reason:
                        evidence = f"Judge: {reason}" + (
                            f" | Agent: {evidence}" if evidence else ""
                        )

    return ExecutorResult(
        test_name=test_name,
        status=status,
        evidence=evidence or "Test completed but no structured output was returned",
        steps_executed=[],
        duration_seconds=duration,
    )


def _log_executor_assignments(plan: TestPlan, config: AppConfig) -> None:
    """Log which test cases are assigned to executors and their prompts.

    Args:
        plan: The test plan with test cases.
        config: Application configuration.
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    executor_model = f"{config.llm.executor.provider}:{config.llm.executor.model}"

    for i, tc in enumerate(plan.test_cases, 1):
        steps_text = "\n".join(f"  {j}. {s}" for j, s in enumerate(tc.steps, 1))
        prompt_preview = (
            f"[bold]{tc.name}[/bold] → {executor_model}\n"
            f"URL: {tc.url}\n"
            f"Steps:\n{steps_text}\n"
            f"Expected: {tc.expected_outcome}"
        )
        console.print(
            Panel(
                prompt_preview,
                title=f"🤖 Executor {i}/{len(plan.test_cases)}",
                border_style="green",
            )
        )


def _is_auth_test(test_case: dict[str, Any]) -> bool:
    """Heuristic check if a test case involves authentication.

    Args:
        test_case: Serialized TestCase dict.

    Returns:
        True if the test likely involves authentication.
    """
    auth_keywords = {"login", "auth", "sign in", "signin", "sign-in", "register", "signup"}
    name_lower = test_case.get("name", "").lower()
    desc_lower = test_case.get("description", "").lower()
    url_lower = test_case.get("url", "").lower()

    combined = f"{name_lower} {desc_lower} {url_lower}"
    return any(kw in combined for kw in auth_keywords)


def _extract_domain(url: str) -> str | None:
    """Extract the domain (host) from a URL for allowed_domains filtering.

    Args:
        url: A full URL string.

    Returns:
        The domain string, or None if the URL is empty/unparseable.
    """
    if not url:
        return None
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.hostname or None
    except Exception:
        return None


def _build_allowed_domains(target_domain: str | None, config: AppConfig) -> list[str]:
    """Build a de-duplicated allowlist for browser navigation domains.

    Args:
        target_domain: Domain extracted from the test case URL.
        config: Application configuration.

    Returns:
        Ordered list of allowed domains.
    """
    domains: list[str] = []

    if target_domain:
        domains.append(target_domain.lower())

    for domain in config.browser.allowed_domains_extra:
        d = (domain or "").strip().lower()
        if d:
            domains.append(d)

    seen: set[str] = set()
    deduped: list[str] = []
    for domain in domains:
        if domain not in seen:
            seen.add(domain)
            deduped.append(domain)

    return deduped
