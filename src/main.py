"""CLI entry point for Verity, the autonomous website testing agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Any

from dotenv import load_dotenv
from langgraph.types import Command
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from src.config import AppConfig, LLMProviderConfig, load_config
from src.graph.builder import build_graph
from src.models.state import PlannerRequest
from src.utils.security import UnsafeTargetError, validate_target_url
from src.utils.url import normalize_url

console = Console()


def setup_logging() -> None:
    """Configure logging with rich handler."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Verity — Autonomous Website Testing Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Override target URL from config",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve all sub-page planners (overrides config)",
    )
    parser.add_argument(
        "--gemini",
        "--Gemini",
        dest="gemini",
        action="store_true",
        help="Use Gemini for all LLM roles instead of the default OpenRouter Auto Router",
    )
    parser.add_argument(
        "--instructions",
        "-i",
        type=str,
        default=None,
        help="Testing instructions (skip interactive prompt)",
    )
    parser.add_argument(
        "--urls",
        nargs="+",
        type=str,
        default=None,
        help="Additional URLs (paths or full URLs) to seed into the planner queue",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    return parser.parse_args()


async def async_input_with_timeout(prompt: str, timeout: float, default: bool = False) -> bool:
    """Prompt the user for input with a timeout.

    Args:
        prompt: Text to display.
        timeout: Seconds before auto-answering with default.
        default: Default answer on timeout.

    Returns:
        True for approval, False for decline.
    """
    loop = asyncio.get_event_loop()

    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: input(prompt)),
            timeout=timeout,
        )
        return response.strip().lower() in ("y", "yes", "1", "true")
    except TimeoutError:
        default_text = "approved" if default else "declined"
        console.print(f"\n[yellow]Timeout — auto-{default_text}[/yellow]")
        return default


async def run_agent(args: argparse.Namespace) -> int:
    """Run the testing agent pipeline.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = all pass, 1 = failures exist).
    """
    # Load config
    config = load_config(args.config)

    # Apply CLI overrides
    if args.auto_approve:
        config.approval.mode = "auto_approve"
    _apply_provider_override(config, use_gemini=args.gemini)

    target_url = args.url or config.target_url
    try:
        validate_target_url(
            target_url,
            allow_private=config.security.allow_private_targets,
            allowed_domains=config.security.allowed_target_domains,
        )
    except UnsafeTargetError as exc:
        console.print(f"[red]Unsafe target URL:[/red] {exc}")
        return 2
    config.target_url = target_url

    # ── Gather user instructions (CLI flag → interactive prompt) ──
    if args.instructions is not None:
        user_instructions = args.instructions.strip()
    else:
        console.print(
            Panel.fit(
                f"[bold]Target:[/bold] [green]{target_url}[/green]\n"
                "[dim]What would you like to test? Press Enter to skip "
                "(the planner will decide on its own).[/dim]",
                title="🧪 Testing Instructions",
                border_style="cyan",
            )
        )
        try:
            raw = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("Instructions: ")
            )
            user_instructions = raw.strip()
        except (EOFError, KeyboardInterrupt):
            user_instructions = ""

    if user_instructions:
        console.print(f"[cyan]Instructions:[/cyan] {user_instructions}")
    else:
        console.print("[dim]No instructions — planner will auto-detect tests.[/dim]")

    console.print(
        Panel.fit(
            f"[bold blue]Verity Autonomous Website Testing Agent[/bold blue]\n"
            f"Target: [green]{target_url}[/green]\n"
            f"Max depth: {config.depth.max_depth} | "
            f"Max executors: {config.concurrency.max_executors} | "
            f"Approval: {config.approval.mode}",
            title="🧪 Verity Web Test Agent",
        )
    )

    # Build the graph
    graph = build_graph(config)

    # Seed initial state — build queue from target_url + config extra_urls + CLI --urls
    seed_urls = [target_url]
    raw_extras = list(config.extra_urls or [])
    if args.urls:
        raw_extras.extend(args.urls)
    for u in raw_extras:
        # Support bare paths like /products → resolve against target_url
        if u.startswith("/"):
            base = target_url.rstrip("/")
            seed_urls.append(f"{base}{u}")
        elif u.startswith(("http://", "https://")):
            seed_urls.append(u)
        else:
            base = target_url.rstrip("/")
            seed_urls.append(f"{base}/{u}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    seed_queue: list[dict] = []
    for url in seed_urls:
        normalized = normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            req = PlannerRequest(
                url=url,
                depth=0,
                user_instructions=user_instructions,
            )
            seed_queue.append(req.to_dict())

    if len(seed_queue) > 1:
        console.print(f"[cyan]Seeded {len(seed_queue)} URLs into planner queue:[/cyan]")
        for i, sq in enumerate(seed_queue, 1):
            console.print(f"  {i}. {sq['url']}")

    initial_state = {
        "queue": seed_queue,
        "visited_urls": [],
        "reports": [],
        "current_request": None,
        "current_test_plan": None,
        "current_results": [],
        "final_report": None,
        "total_cost": 0.0,
        "planner_context": "",
        "planner_clarification_count": 0,
    }

    # Thread config for checkpointing
    thread_id = uuid.uuid4().hex
    graph_config = {"configurable": {"thread_id": thread_id}}

    # Run the graph with interrupt handling
    input_data: dict | Command = initial_state
    result: dict[str, Any] = {}
    pipeline_failed = False
    while True:
        try:
            result = await graph.ainvoke(input_data, graph_config)

            # Check for interrupts
            snapshot = await graph.aget_state(graph_config)
            if not snapshot.next:
                # Graph completed — exit loop
                break

            # Find the first pending interrupt across all tasks
            interrupt_data = _find_first_interrupt(snapshot.tasks)
            if interrupt_data is None:
                logging.warning("Graph paused but no interrupts found — terminating")
                break

            itype = interrupt_data.get("type", "approval")

            if itype == "planner_clarification":
                # Planner needs user input
                question = interrupt_data.get("question", "")
                url = interrupt_data.get("url", "")
                console.print(
                    Panel(
                        f"[yellow]{question}[/yellow]",
                        title=f"🤔 Planner needs input — {url}",
                        border_style="magenta",
                    )
                )
                try:
                    answer = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("Your answer: ")
                    )
                except (EOFError, KeyboardInterrupt):
                    answer = ""
                input_data = Command(resume=answer.strip())
            else:
                # Approval interrupt
                url = interrupt_data.get("url", "unknown")
                depth = interrupt_data.get("depth", "?")
                reason = interrupt_data.get("reason", "")

                console.print(
                    Panel(
                        f"[yellow]{reason}[/yellow]\nURL: [cyan]{url}[/cyan] | Depth: {depth}",
                        title="🔔 Approval Required",
                    )
                )

                approved = await async_input_with_timeout(
                    "Approve? [y/N]: ",
                    timeout=config.approval.timeout_seconds,
                    default=False,
                )
                input_data = Command(resume=approved)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            pipeline_failed = True
            break
        except Exception:
            logging.exception("Pipeline error")
            pipeline_failed = True
            break

    # Display results
    reports = result.get("reports", []) if isinstance(result, dict) else []

    _display_summary(reports, config.report.output_path)

    # Return exit code based on results
    has_failures = any(
        any(r.get("status") in ("fail", "error") for r in report.get("results", []))
        for report in reports
    )
    return 1 if pipeline_failed or has_failures or not reports else 0


def _apply_provider_override(config: AppConfig, *, use_gemini: bool) -> None:
    """Apply provider choices requested by the CLI without changing the YAML file."""
    if not use_gemini:
        return

    gemini_config = LLMProviderConfig(
        provider="gemini",
        model="gemini-2.5-flash",
        api_key_env="GOOGLE_API_KEY",
    )
    config.llm.planner = gemini_config.model_copy(deep=True)
    config.llm.executor = gemini_config.model_copy(deep=True)
    config.llm.summarizer = gemini_config.model_copy(deep=True)
    config.llm.fallback = LLMProviderConfig(
        provider="openrouter",
        model="openrouter/auto",
        api_key_env="OPENROUTER_API_KEY",
    )


def _find_first_interrupt(tasks: Any) -> dict[str, Any] | None:
    """Extract the first interrupt value from LangGraph snapshot tasks.

    Args:
        tasks: Snapshot tasks from ``graph.aget_state()``.

    Returns:
        The interrupt value dict, or None if no interrupts found.
    """
    for task in tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            return task.interrupts[0].value
    return None


def _display_summary(reports: list[dict], report_path: str) -> None:
    """Display a summary table in the terminal.

    Args:
        reports: List of serialized PlannerReport dicts.
        report_path: Path where the full report was written.
    """
    table = Table(title="Test Results Summary")
    table.add_column("URL", style="cyan", max_width=50)
    table.add_column("Depth", justify="center")
    table.add_column("Pass", style="green", justify="center")
    table.add_column("Fail", style="red", justify="center")
    table.add_column("Error", style="yellow", justify="center")
    table.add_column("Total", justify="center")

    total_pass = 0
    total_fail = 0
    total_error = 0
    total_tests = 0

    for report in reports:
        results = report.get("results", [])
        p = sum(1 for r in results if r.get("status") == "pass")
        f = sum(1 for r in results if r.get("status") == "fail")
        e = sum(1 for r in results if r.get("status") == "error")
        t = len(results)

        total_pass += p
        total_fail += f
        total_error += e
        total_tests += t

        table.add_row(
            report.get("url", "?"),
            str(report.get("depth", "?")),
            str(p),
            str(f),
            str(e),
            str(t),
        )

    # Totals row
    table.add_section()
    table.add_row("TOTAL", "", str(total_pass), str(total_fail), str(total_error), str(total_tests))

    console.print(table)

    if total_tests == 0:
        console.print("[yellow]No tests were executed.[/yellow]")
    elif total_fail + total_error == 0:
        console.print("[bold green]✅ All tests passed![/bold green]")
    else:
        console.print(f"[bold red]❌ {total_fail} failures, {total_error} errors[/bold red]")

    console.print(f"\n[dim]Full report: {report_path}[/dim]")


def main() -> None:
    """Main entry point."""
    load_dotenv()
    setup_logging()
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        exit_code = asyncio.run(run_agent(args))
    except Exception:
        logging.exception("Fatal application error")
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
