"""Thin FastAPI backend that wraps the existing CLI agent pipeline.

Streams all agent output (logs, LLM calls, browser actions, errors) to the
frontend via Server-Sent Events (SSE).

Does NOT modify any existing agent/LangGraph/browser-use code.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import sys
import traceback
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from src.config import load_config
from src.graph.builder import build_graph
from src.models.state import PlannerRequest

# ---------------------------------------------------------------------------
# Load environment variables (same as CLI does)
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Cragent Web UI", version="0.1.0")

# Serve static files (index.html lives in static/)
app.mount("/static", StaticFiles(directory="static"), name="static")


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
        loop = asyncio.get_event_loop()
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
        except asyncio.TimeoutError:
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
        return FileResponse("static/index.html", media_type="text/html")
    except Exception:
        traceback.print_exc()
        return HTMLResponse("<h1>Error loading frontend</h1>", status_code=500)


# ---------------------------------------------------------------------------
# SSE streaming helpers
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


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

    def __init__(self, queue: asyncio.Queue[str]) -> None:
        super().__init__()
        self._queue = queue
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def emit(self, record: logging.Record) -> None:
        try:
            msg = self.format(record)
            payload = _sse_msg("log", msg)
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)
            else:
                try:
                    self._queue.put_nowait(payload)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Stdout/Stderr captor that also writes to a queue
# ---------------------------------------------------------------------------

class StreamCaptor(io.TextIOBase):
    """Wraps an original stream; copies writes to an asyncio.Queue as SSE messages."""

    def __init__(
        self,
        original: Any,
        queue: asyncio.Queue[str],
        stream_name: str,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._original = original
        self._queue = queue
        self._stream_name = stream_name
        self._loop = loop

    def write(self, s: str) -> int:
        if s and s.strip():
            payload = _sse_msg("stdout" if self._stream_name == "stdout" else "stderr", s.rstrip())
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)
            else:
                try:
                    self._queue.put_nowait(payload)
                except Exception:
                    pass
        # Also write to the original stream so server console still works
        if self._original is not None:
            try:
                return self._original.write(s)
            except Exception:
                return len(s) if s else 0
        return len(s) if s else 0

    def flush(self) -> None:
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass

    def fileno(self) -> int:
        if self._original is not None:
            return self._original.fileno()
        raise io.UnsupportedOperation("fileno")

    @property
    def encoding(self) -> str:
        if hasattr(self._original, "encoding"):
            return self._original.encoding
        return "utf-8"


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
    queue_handler = QueueLogHandler(queue)
    queue_handler.set_loop(loop)
    queue_handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
    queue_handler.setLevel(logging.INFO)
    root_logger.addHandler(queue_handler)
    original_level = root_logger.level
    root_logger.setLevel(logging.INFO)

    # Install stdout/stderr captors
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout_captor = StreamCaptor(original_stdout, queue, "stdout", loop)
    stderr_captor = StreamCaptor(original_stderr, queue, "stderr", loop)
    sys.stdout = stdout_captor  # type: ignore[assignment]
    sys.stderr = stderr_captor  # type: ignore[assignment]

    try:
        # ── Step 1: Load config ──
        await queue.put(_sse_msg("status", "Loading configuration..."))
        try:
            config = load_config(config_path)
        except Exception:
            tb = traceback.format_exc()
            await queue.put(_sse_msg("error", f"Failed to load config:\n{tb}"))
            session.status = "failed"
            return

        await session.attach_config(config)

        # ── Step 2: Apply overrides ──
        if url:
            config.target_url = url
        # Force auto-approve for web UI (no interactive prompts)
        config.approval.mode = "auto_approve"

        target_url = config.target_url
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
        except Exception:
            tb = traceback.format_exc()
            await queue.put(_sse_msg("error", f"Failed to build graph:\n{tb}"))
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

        thread_id = hashlib.md5(target_url.encode()).hexdigest()
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
                    await queue.put(_sse_msg("status", "Graph paused with no interrupts — terminating."))
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
                                "No clarification answer received in time; continuing with empty response.",
                            )
                        )
                    input_data = Command(resume=answer)
                else:
                    # Approval interrupt — auto-approve
                    approve_url = interrupt_data.get("url", "unknown")
                    depth = interrupt_data.get("depth", "?")
                    reason = interrupt_data.get("reason", "")
                    await queue.put(_sse_msg("status", f"Auto-approving sub-page: {approve_url} (depth={depth})"))
                    input_data = Command(resume=True)

            except Exception:
                tb = traceback.format_exc()
                await queue.put(_sse_msg("error", f"Pipeline error:\n{tb}"))
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
        await queue.put(_sse_msg("summary", summary, pass_count=total_pass, fail_count=total_fail, error_count=total_error))

        await queue.put(_sse_msg("done", "Agent run completed."))
        session.status = "completed"

    except Exception:
        tb = traceback.format_exc()
        await queue.put(_sse_msg("error", f"Unhandled error:\n{tb}"))
        await queue.put(_sse_msg("done", "Agent run finished with errors."))
        session.status = "failed"

    finally:
        # Restore stdout/stderr and remove logging handler
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        root_logger.removeHandler(queue_handler)
        root_logger.setLevel(original_level)
        session.updated_at = _timestamp()


def _find_first_interrupt(tasks: Any) -> dict[str, Any] | None:
    """Extract the first interrupt value from LangGraph snapshot tasks.

    Same logic as src/main.py:_find_first_interrupt().
    """
    try:
        for task in tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                return task.interrupts[0].value
    except Exception:
        traceback.print_exc()
    return None


# ---------------------------------------------------------------------------
# API endpoint — run agent and stream results via SSE
# ---------------------------------------------------------------------------

@app.get("/api/run")
async def run_agent_sse(url: str, instructions: str = "", config: str = "config.yaml"):
    """Start an agent run and stream all output via SSE.

    Query params:
        url: Target URL to test.
        instructions: Testing instructions (optional).
        config: Path to config YAML (default: config.yaml).
    """

    event_queue: asyncio.Queue[str] = asyncio.Queue()
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
            _run_agent_pipeline(url, instructions, config, event_queue, session)
        )

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
                except asyncio.TimeoutError:
                    # Send a heartbeat to keep the connection alive
                    yield {"data": _sse_msg("heartbeat", "")}

                    # Check if the task is done (e.g. crashed without sending "done")
                    if task.done():
                        exc = task.exception()
                        if exc:
                            tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                            yield {"data": _sse_msg("error", f"Agent task crashed:\n{tb_str}")}
                            session.status = "failed"
                        yield {"data": _sse_msg("done", "Agent run finished.")}
                        break

        except asyncio.CancelledError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        except Exception:
            tb = traceback.format_exc()

            yield {"data": _sse_msg("error", f"SSE error:\n{tb}")}
            yield {"data": _sse_msg("done", "Agent run finished with errors.")}

    try:
        return EventSourceResponse(event_generator())
    except Exception:
        traceback.print_exc()
        return {"error": "Failed to start SSE stream"}


@app.get("/api/runs/{run_id}/state")
async def run_state(run_id: str):
    """Get current state for a run session."""
    session = _get_run_session(run_id)
    return await session.snapshot()


@app.post("/api/runs/{run_id}/respond")
async def run_respond(run_id: str, payload: ClarificationResponse):
    """Submit answer for a pending planner clarification interrupt."""
    session = _get_run_session(run_id)
    accepted = await session.submit_clarification(payload.answer)
    if not accepted:
        raise HTTPException(status_code=409, detail="No pending clarification interrupt")

    session.queue.put_nowait(_sse_msg("status", "Planner clarification answer submitted from UI."))
    return {"ok": True}


@app.post("/api/runs/{run_id}/headless")
async def run_set_headless(run_id: str, payload: HeadlessUpdate):
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
async def run_captcha_start(run_id: str):
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
async def run_captcha_solved(run_id: str):
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
    print(f"[{_timestamp()}] Starting Cragent Web UI server...")
    print(f"[{_timestamp()}] Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
