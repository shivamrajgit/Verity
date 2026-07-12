"""Thin FastAPI backend that wraps the existing CLI agent pipeline.

Streams all agent output (logs, LLM calls, browser actions, errors) to the
frontend via Server-Sent Events (SSE).

Does NOT modify any existing agent/LangGraph/browser-use code.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import hmac
import json
import logging
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.config import load_config
from src.graph.builder import build_graph
from src.models.state import PlannerRequest
from src.utils.security import UnsafeTargetError, validate_target_url

# ---------------------------------------------------------------------------
# Load environment variables (same as CLI does)
# ---------------------------------------------------------------------------
load_dotenv()

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        with contextlib.suppress(AttributeError, OSError):
            _stream.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
REPORT_DIR = Path(os.environ.get("VERITY_REPORT_DIR", BASE_DIR / "reports")).resolve()
SESSION_TTL_SECONDS = int(os.environ.get("VERITY_SESSION_TTL_SECONDS", "3600"))
MAX_ACTIVE_RUNS = int(os.environ.get("VERITY_MAX_ACTIVE_RUNS", "2"))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Verity Web UI", version="0.1.0")

# Serve static files (index.html lives in static/)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
logger = logging.getLogger(__name__)
RUN_CONTEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "verity_run_context", default=None
)


def _public_error(prefix: str, error: Exception) -> str:
    """Log full diagnostics server-side and return a safe SSE message."""
    logger.exception(prefix)
    return f"{prefix}: {type(error).__name__}: {error}"


def _require_api_token(request: Request) -> None:
    """Require an API token when configured for a deployed server.

    Local development remains convenient when no token is configured, while
    production deployments can set VERITY_API_TOKEN and protect every run
    and control endpoint without exposing secrets in query parameters.
    """
    expected = os.environ.get("VERITY_API_TOKEN", "")
    required = os.environ.get("VERITY_REQUIRE_API_TOKEN", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if not expected:
        if required:
            raise HTTPException(status_code=503, detail="API authentication is not configured")
        return

    provided = request.headers.get("x-api-key", "")
    if not provided:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            provided = authorization[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def _resolve_server_config_path(config_path: str) -> Path:
    """Resolve config files while preventing traversal outside the project."""
    candidate = Path(config_path)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(BASE_DIR)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Config path must stay inside the project",
        ) from exc
    if not candidate.is_file():
        raise HTTPException(status_code=400, detail="Config file does not exist")
    return candidate


def _cleanup_sessions() -> None:
    """Remove completed sessions after a bounded retention period."""
    now = time.time()
    expired = [
        run_id
        for run_id, session in RUN_SESSIONS.items()
        if session.finished_epoch is not None
        and now - session.finished_epoch > SESSION_TTL_SECONDS
    ]
    for run_id in expired:
        RUN_SESSIONS.pop(run_id, None)


class ClarificationResponse(BaseModel):
    """POST body for planner clarification answers."""

    answer: str = Field(default="")


class HeadlessUpdate(BaseModel):
    """POST body for updating browser headless mode during a run."""

    headless: bool


class RunSession:
    """Mutable state for one live web UI run."""

    def __init__(self, run_id: str, queue: asyncio.Queue[str]) -> None:
        self.run_id = run_id
        self.queue = queue
        self.status = "running"
        self.created_at = _timestamp()
        self.updated_at = self.created_at
        self.finished_epoch: float | None = None
        self.task: asyncio.Task[Any] | None = None
        self.config = None
        self.initial_headless: bool | None = None
        self.captcha_previous_headless: bool | None = None
        self.pending_interrupt: dict[str, Any] | None = None
        self._clarification_future: asyncio.Future[str] | None = None
        self._lock = asyncio.Lock()

    async def attach_config(self, config: Any) -> None:
        """Attach runtime config so control APIs can mutate browser mode."""
        async with self._lock:
            self.config = config
            self.initial_headless = config.browser.headless
            self.updated_at = _timestamp()

    async def wait_for_clarification(
        self,
        question: str,
        url: str,
        timeout_seconds: int,
    ) -> str:
        """Pause until UI submits planner clarification answer (or timeout)."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()

        async with self._lock:
            self.pending_interrupt = {
                "type": "planner_clarification",
                "question": question,
                "url": url,
            }
            self._clarification_future = future
            self.updated_at = _timestamp()

        try:
            answer = await asyncio.wait_for(future, timeout=float(timeout_seconds))
            return (answer or "").strip()
        except TimeoutError:
            return ""
        finally:
            async with self._lock:
                self.pending_interrupt = None
                self._clarification_future = None
                self.updated_at = _timestamp()

    async def submit_clarification(self, answer: str) -> bool:
        """Resolve a pending clarification wait with user-provided answer."""
        async with self._lock:
            if self._clarification_future is None or self._clarification_future.done():
                return False
            self._clarification_future.set_result(answer)
            self.updated_at = _timestamp()
            return True

    async def set_headless(self, headless: bool) -> tuple[bool, bool]:
        """Set runtime headless mode; takes effect for future executors."""
        async with self._lock:
            if self.config is None:
                raise ValueError("Run config is not ready yet")
            before = bool(self.config.browser.headless)
            self.config.browser.headless = headless
            self.updated_at = _timestamp()
            return before, bool(self.config.browser.headless)

    async def captcha_start(self) -> tuple[bool, bool]:
        """Temporarily force headed mode while captcha is being solved."""
        async with self._lock:
            if self.config is None:
                raise ValueError("Run config is not ready yet")
            before = bool(self.config.browser.headless)
            if self.captcha_previous_headless is None:
                self.captcha_previous_headless = before
            self.config.browser.headless = False
            self.updated_at = _timestamp()
            return before, bool(self.config.browser.headless)

    async def captcha_solved(self) -> tuple[bool, bool]:
        """Restore the headless mode that existed before captcha handling."""
        async with self._lock:
            if self.config is None:
                raise ValueError("Run config is not ready yet")
            before = bool(self.config.browser.headless)
            restore_to = (
                self.captcha_previous_headless
                if self.captcha_previous_headless is not None
                else self.initial_headless
            )
            self.config.browser.headless = bool(restore_to)
            self.captcha_previous_headless = None
            self.updated_at = _timestamp()
            return before, bool(self.config.browser.headless)

    async def snapshot(self) -> dict[str, Any]:
        """Serialize run state for UI polling/debugging."""
        async with self._lock:
            return {
                "run_id": self.run_id,
                "status": self.status,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "finished_at": (
                    datetime.fromtimestamp(self.finished_epoch, UTC).isoformat()
                    if self.finished_epoch is not None
                    else None
                ),
                "headless": (
                    bool(self.config.browser.headless) if self.config is not None else None
                ),
                "awaiting_input": self.pending_interrupt is not None,
                "pending_interrupt": self.pending_interrupt,
            }


RUN_SESSIONS: dict[str, RunSession] = {}


def _get_run_session(run_id: str) -> RunSession:
    """Fetch a run session or raise 404."""
    session = RUN_SESSIONS.get(run_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return session


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the frontend."""
    try:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")
    except Exception:
        logger.exception("Failed to load frontend")
        return HTMLResponse("<h1>Error loading frontend</h1>", status_code=500)


# ---------------------------------------------------------------------------
# SSE streaming helpers
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sse_msg(msg_type: str, content: str, **extra: Any) -> str:
    """Build a JSON payload for an SSE event."""
    payload: dict[str, Any] = {
        "type": msg_type,
        "timestamp": _timestamp(),
        "content": content,
    }
    payload.update(extra)
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Custom logging handler that pushes log records into an asyncio.Queue
# ---------------------------------------------------------------------------

class QueueLogHandler(logging.Handler):
    """Logging handler that puts formatted records into an asyncio Queue."""

    def __init__(self, queue: asyncio.Queue[str], run_id: str) -> None:
        super().__init__()
        self._queue = queue
        self._run_id = run_id
        self._loop: asyncio.AbstractEventLoop | None = None
        self.dropped_count = 0

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _enqueue(self, payload: str) -> None:
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            self.dropped_count += 1

    def emit(self, record: logging.Record) -> None:
        if RUN_CONTEXT.get() != self._run_id:
            return
        try:
            msg = self.format(record)
            payload = _sse_msg("log", msg)
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._enqueue, payload)
            else:
                self._enqueue(payload)
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Stdout/Stderr captor that also writes to a queue
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Core agent runner — mirrors src/main.py:run_agent() logic without modification
# ---------------------------------------------------------------------------

async def _run_agent_pipeline(
    url: str,
    instructions: str,
    config_path: str,
    queue: asyncio.Queue[str],
    session: RunSession,
) -> None:
    """Run the full agent pipeline, streaming progress to the SSE queue.

    This function mirrors the logic in src/main.py:run_agent() but replaces
    interactive prompts with auto-approve and sends all output via the queue.
    """
    loop = asyncio.get_event_loop()

    # Install logging handler
    root_logger = logging.getLogger()
    run_context_token = RUN_CONTEXT.set(session.run_id)
    queue_handler = QueueLogHandler(queue, session.run_id)
    queue_handler.set_loop(loop)
    queue_handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
    queue_handler.setLevel(logging.INFO)
    root_logger.addHandler(queue_handler)
    original_level = root_logger.level
    root_logger.setLevel(logging.INFO)

    # Do not replace process-global stdout/stderr. Multiple web runs can be
    # active concurrently; global stream replacement mixes their output and
    # can restore the wrong stream. Structured logs are captured per run.
    pipeline_failed = False

    try:
        # ── Step 1: Load config ──
        await queue.put(_sse_msg("status", "Loading configuration..."))
        try:
            config = load_config(config_path)
        except Exception as exc:
            await queue.put(_sse_msg("error", _public_error("Failed to load config", exc)))
            session.status = "failed"
            return

        await session.attach_config(config)

        # ── Step 2: Apply overrides ──
        target_url = url or config.target_url
        try:
            validate_target_url(
                target_url,
                allow_private=config.security.allow_private_targets,
                allowed_domains=config.security.allowed_target_domains,
            )
        except UnsafeTargetError as exc:
            await queue.put(_sse_msg("error", f"Unsafe target URL: {exc}"))
            session.status = "failed"
            return
        config.target_url = target_url
        config.report.output_path = str(REPORT_DIR / f"{session.run_id}.md")
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        # Force auto-approve for web UI (no interactive prompts)
        config.approval.mode = "auto_approve"

        user_instructions = instructions.strip() if instructions else ""

        await queue.put(_sse_msg("status", f"Target URL: {target_url}"))
        if user_instructions:
            await queue.put(_sse_msg("status", f"Instructions: {user_instructions}"))
        else:
            await queue.put(_sse_msg("status", "No instructions — planner will auto-detect tests."))

        # ── Step 3: Build the LangGraph graph ──
        await queue.put(_sse_msg("status", "Building agent graph..."))
        try:
            graph = build_graph(config)
        except Exception as exc:
            await queue.put(_sse_msg("error", _public_error("Failed to build graph", exc)))
            session.status = "failed"
            return

        # ── Step 4: Seed initial state — same logic as run_agent() ──
        seed_urls = [target_url]
        raw_extras = list(config.extra_urls or [])
        for u in raw_extras:
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
        for u in seed_urls:
            normalized = u.rstrip("/").lower()
            if normalized not in seen:
                seen.add(normalized)
                req = PlannerRequest(
                    url=u,
                    depth=0,
                    user_instructions=user_instructions,
                )
                seed_queue.append(req.to_dict())

        await queue.put(_sse_msg("status", f"Seeded {len(seed_queue)} URL(s) into planner queue"))

        initial_state: dict[str, Any] = {
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

        thread_id = session.run_id
        graph_config = {"configurable": {"thread_id": thread_id}}

        # ── Step 5: Run the graph loop — same as run_agent() ──
        await queue.put(_sse_msg("status", "Starting agent pipeline..."))

        input_data: dict | Command = initial_state
        result: dict[str, Any] = {}

        while True:
            try:
                await queue.put(_sse_msg("status", "Invoking graph (next iteration)..."))

                result = await graph.ainvoke(input_data, graph_config)

                # Check for interrupts
                snapshot = await graph.aget_state(graph_config)
                if not snapshot.next:
                    await queue.put(_sse_msg("status", "Graph execution completed."))
                    break

                # Handle interrupts (auto-approve for web UI)
                interrupt_data = _find_first_interrupt(snapshot.tasks)
                if interrupt_data is None:
                    await queue.put(
                        _sse_msg("status", "Graph paused with no interrupts — terminating.")
                    )
                    break

                itype = interrupt_data.get("type", "approval")

                if itype == "planner_clarification":
                    question = interrupt_data.get("question", "")
                    url_asking = interrupt_data.get("url", "")
                    await queue.put(
                        _sse_msg(
                            "interrupt",
                            f"Planner needs input for {url_asking}: {question}",
                            run_id=session.run_id,
                            interrupt_type="planner_clarification",
                            question=question,
                            url=url_asking,
                        )
                    )
                    answer = await session.wait_for_clarification(
                        question=question,
                        url=url_asking,
                        timeout_seconds=config.approval.timeout_seconds,
                    )
                    if not answer:
                        await queue.put(
                            _sse_msg(
                                "status",
                                "No clarification answer received in time; "
                                "continuing with empty response.",
                            )
                        )
                    input_data = Command(resume=answer)
                else:
                    # Approval interrupt — auto-approve
                    approve_url = interrupt_data.get("url", "unknown")
                    depth = interrupt_data.get("depth", "?")
                    await queue.put(
                        _sse_msg(
                            "status",
                            f"Auto-approving sub-page: {approve_url} (depth={depth})",
                        )
                    )
                    input_data = Command(resume=True)

            except Exception as exc:
                pipeline_failed = True
                await queue.put(_sse_msg("error", _public_error("Pipeline error", exc)))
                break

        # ── Step 6: Extract and send results ──
        reports = result.get("reports", []) if isinstance(result, dict) else []
        final_report = result.get("final_report", "") if isinstance(result, dict) else ""

        await queue.put(_sse_msg("status", f"Run finished. {len(reports)} report(s) generated."))

        # Send structured results
        await queue.put(_sse_msg("results", json.dumps(reports), reports=reports))

        if final_report:
            await queue.put(_sse_msg("report", final_report))

        # Summary stats
        total_pass = 0
        total_fail = 0
        total_error = 0
        for report in reports:
            results_list = report.get("results", [])
            total_pass += sum(1 for r in results_list if r.get("status") == "pass")
            total_fail += sum(1 for r in results_list if r.get("status") == "fail")
            total_error += sum(1 for r in results_list if r.get("status") == "error")

        summary = f"Total: {total_pass} pass, {total_fail} fail, {total_error} error"
        await queue.put(
            _sse_msg(
                "summary",
                summary,
                pass_count=total_pass,
                fail_count=total_fail,
                error_count=total_error,
            )
        )

        session.status = "failed" if pipeline_failed else "completed"
        await queue.put(_sse_msg("done", "Agent run completed."))

    except Exception as exc:
        await queue.put(_sse_msg("error", _public_error("Unhandled pipeline error", exc)))
        await queue.put(_sse_msg("done", "Agent run finished with errors."))
        session.status = "failed"

    finally:
        # Remove only this run's logging handler; process-global streams are
        # intentionally left untouched for concurrent requests.
        root_logger.removeHandler(queue_handler)
        root_logger.setLevel(original_level)
        RUN_CONTEXT.reset(run_context_token)
        session.updated_at = _timestamp()
        if session.status in {"completed", "failed"}:
            session.finished_epoch = time.time()


def _find_first_interrupt(tasks: Any) -> dict[str, Any] | None:
    """Extract the first interrupt value from LangGraph snapshot tasks.

    Same logic as src/main.py:_find_first_interrupt().
    """
    try:
        for task in tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                return task.interrupts[0].value
    except Exception:
        logger.exception("Failed to inspect graph interrupts")
    return None


# ---------------------------------------------------------------------------
# API endpoint — run agent and stream results via SSE
# ---------------------------------------------------------------------------

@app.get("/api/run")
async def run_agent_sse(
    url: str,
    instructions: str = "",
    config: str = "config.yaml",
    _: None = Depends(_require_api_token),
):
    """Start an agent run and stream all output via SSE.

    Query params:
        url: Target URL to test.
        instructions: Testing instructions (optional).
        config: Path to config YAML (default: config.yaml).
    """

    _cleanup_sessions()
    active_runs = sum(1 for session in RUN_SESSIONS.values() if session.status == "running")
    if active_runs >= MAX_ACTIVE_RUNS:
        raise HTTPException(status_code=429, detail="Too many active runs")
    config_path = _resolve_server_config_path(config)

    event_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=5000)
    run_id = uuid.uuid4().hex
    session = RunSession(run_id=run_id, queue=event_queue)
    RUN_SESSIONS[run_id] = session

    async def event_generator():
        """Yield SSE events from the queue."""
        # Emit run metadata first so frontend can call control APIs.
        yield {
            "data": _sse_msg(
                "run",
                "Run started",
                run_id=run_id,
            )
        }

        # Start the agent pipeline as a background task
        task = asyncio.create_task(
            _run_agent_pipeline(url, instructions, str(config_path), event_queue, session)
        )
        session.task = task

        try:
            while True:
                try:
                    # Wait for next message with a timeout
                    msg = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    yield {"data": msg}

                    # Check if this was the "done" message
                    try:
                        parsed = json.loads(msg)
                        if parsed.get("type") == "done":
                            break
                    except json.JSONDecodeError:
                        pass
                except TimeoutError:
                    # Send a heartbeat to keep the connection alive
                    yield {"data": _sse_msg("heartbeat", "")}

                    # Check if the task is done (e.g. crashed without sending "done")
                    if task.done():
                        exc = task.exception()
                        if exc:
                            yield {
                                "data": _sse_msg(
                                    "error",
                                    _public_error("Agent task crashed", exc),
                                )
                            }
                            session.status = "failed"
                        yield {"data": _sse_msg("done", "Agent run finished.")}
                        break

        except asyncio.CancelledError:
            session.status = "cancelled"
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            session.finished_epoch = time.time()
        except Exception as exc:
            yield {"data": _sse_msg("error", _public_error("SSE error", exc))}
            yield {"data": _sse_msg("done", "Agent run finished with errors.")}

    try:
        return EventSourceResponse(event_generator())
    except Exception:
        logger.exception("Failed to create SSE response")
        return {"error": "Failed to start SSE stream"}


@app.get("/api/runs/{run_id}/state")
async def run_state(run_id: str, _: None = Depends(_require_api_token)):
    """Get current state for a run session."""
    session = _get_run_session(run_id)
    return await session.snapshot()


@app.post("/api/runs/{run_id}/cancel")
async def run_cancel(run_id: str, _: None = Depends(_require_api_token)):
    """Cancel an active run and release its browser/LLM resources."""
    session = _get_run_session(run_id)
    if session.task is None or session.task.done():
        raise HTTPException(status_code=409, detail="Run is not active")
    session.status = "cancelled"
    session.task.cancel()
    session.finished_epoch = time.time()
    return {"ok": True, "status": "cancelled"}


@app.post("/api/runs/{run_id}/respond")
async def run_respond(
    run_id: str,
    payload: ClarificationResponse,
    _: None = Depends(_require_api_token),
):
    """Submit answer for a pending planner clarification interrupt."""
    session = _get_run_session(run_id)
    accepted = await session.submit_clarification(payload.answer)
    if not accepted:
        raise HTTPException(status_code=409, detail="No pending clarification interrupt")

    session.queue.put_nowait(_sse_msg("status", "Planner clarification answer submitted from UI."))
    return {"ok": True}


@app.post("/api/runs/{run_id}/headless")
async def run_set_headless(
    run_id: str,
    payload: HeadlessUpdate,
    _: None = Depends(_require_api_token),
):
    """Set runtime headless mode for future browser sessions."""
    session = _get_run_session(run_id)
    try:
        before, after = await session.set_headless(payload.headless)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    session.queue.put_nowait(
        _sse_msg(
            "status",
            f"Browser headless changed from {before} to {after}. "
            "This applies to newly started executors.",
            run_id=run_id,
            headless=after,
        )
    )
    return {"ok": True, "headless_before": before, "headless_after": after}


@app.post("/api/runs/{run_id}/captcha/start")
async def run_captcha_start(run_id: str, _: None = Depends(_require_api_token)):
    """Quick action: show browser for captcha solving (headless=False)."""
    session = _get_run_session(run_id)
    try:
        before, after = await session.captcha_start()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    session.queue.put_nowait(
        _sse_msg(
            "status",
            "Captcha mode enabled: browser switched to headed mode for upcoming executors.",
            run_id=run_id,
            headless=after,
        )
    )
    return {"ok": True, "headless_before": before, "headless_after": after}


@app.post("/api/runs/{run_id}/captcha/solved")
async def run_captcha_solved(run_id: str, _: None = Depends(_require_api_token)):
    """Quick action: restore headless mode to the pre-captcha value."""
    session = _get_run_session(run_id)
    try:
        before, after = await session.captcha_solved()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    session.queue.put_nowait(
        _sse_msg(
            "status",
            "Captcha solved: browser mode restored to previous headless setting.",
            run_id=run_id,
            headless=after,
        )
    )
    return {"ok": True, "headless_before": before, "headless_after": after}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Simple health check."""
    return {"status": "ok", "timestamp": _timestamp()}


# ---------------------------------------------------------------------------
# Main entry for `python server.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("VERITY_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"} and not os.environ.get("VERITY_API_TOKEN"):
        raise RuntimeError("VERITY_API_TOKEN is required when binding beyond localhost")
    print(f"[{_timestamp()}] Starting Verity Web UI server...")
    print(f"[{_timestamp()}] Open http://localhost:8000 in your browser")
    uvicorn.run(
        app,
        host=host,
        port=int(os.environ.get("VERITY_PORT", "8000")),
        log_level="info",
    )
