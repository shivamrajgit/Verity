"""LangGraph StateGraph builder — constructs and compiles the testing pipeline."""

from __future__ import annotations

import functools
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.config import AppConfig
from src.graph.nodes.approve import approve_node
from src.graph.nodes.compile import compile_node
from src.graph.nodes.dequeue import dequeue_node
from src.graph.nodes.execute import execute_node
from src.graph.nodes.plan import plan_node
from src.graph.nodes.summarize import summarize_node
from src.models.state import GraphState


def build_graph(config: AppConfig) -> Any:
    """Build and compile the LangGraph StateGraph for the testing pipeline.

    Graph flow:
        START → dequeue_node
        dequeue_node → approve_node    (if current_request exists)
        dequeue_node → summarize_node  (if queue empty + no current_request)
        approve_node → plan_node       (if approved — returns empty dict)
        approve_node → dequeue_node    (if declined — returns Command(goto=...))
        plan_node → execute_node       (if test plan generated)
        plan_node → plan_node          (if clarification received, retry)
        execute_node → compile_node
        compile_node → dequeue_node    (loop back)
        summarize_node → END

    Args:
        config: Application configuration.

    Returns:
        Compiled LangGraph graph ready for invocation.
    """
    # Bind config to node functions via functools.partial
    _dequeue = functools.partial(dequeue_node, app_config=config)
    _approve = functools.partial(approve_node, app_config=config)
    _plan = functools.partial(plan_node, app_config=config)
    _execute = functools.partial(execute_node, app_config=config)
    _compile = functools.partial(compile_node, app_config=config)
    _summarize = functools.partial(summarize_node, app_config=config)

    # Build the graph
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("dequeue_node", _dequeue)
    graph.add_node("approve_node", _approve)
    graph.add_node("plan_node", _plan)
    graph.add_node("execute_node", _execute)
    graph.add_node("compile_node", _compile)
    graph.add_node("summarize_node", _summarize)

    # START → dequeue
    graph.add_edge(START, "dequeue_node")

    # dequeue → conditional routing
    graph.add_conditional_edges(
        "dequeue_node",
        _route_after_dequeue,
        {
            "approve": "approve_node",
            "summarize": "summarize_node",
        },
    )

    # approve → plan (approved path — the Command(goto=...) handles decline)
    graph.add_edge("approve_node", "plan_node")

    # plan → conditional: execute if plan ready, loop back to plan if clarification
    graph.add_conditional_edges(
        "plan_node",
        _route_after_plan,
        {
            "execute": "execute_node",
            "plan": "plan_node",
        },
    )

    # execute → compile
    graph.add_edge("execute_node", "compile_node")

    # compile → dequeue (loop back)
    graph.add_edge("compile_node", "dequeue_node")

    # summarize → END
    graph.add_edge("summarize_node", END)

    # Compile with in-memory checkpointer (for interrupt/resume support)
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


def _route_after_dequeue(state: GraphState) -> str:
    """Route after dequeue: to approve if we have a request, to summarize if queue is drained.

    Args:
        state: Current graph state.

    Returns:
        "approve" or "summarize".
    """
    if state.get("current_request") is not None:
        return "approve"
    return "summarize"


def _route_after_plan(state: GraphState) -> str:
    """Route after plan: to execute if a test plan is ready, back to plan if clarification.

    When the planner asked for user clarification, it returns updated
    ``planner_context`` but leaves ``current_test_plan`` as None.  After the
    interrupt/resume cycle, the graph should re-enter plan_node with the
    accumulated context.

    Args:
        state: Current graph state.

    Returns:
        "execute" or "plan".
    """
    if state.get("current_test_plan") is not None:
        return "execute"
    return "plan"
