import json

import pytest

from src.config import load_config
from src.graph.nodes.plan import _call_legacy_planner, _extract_test_plan
from src.models.test_plan import TestPlan as PlanModel


def test_plan_parser_repairs_common_openrouter_subpage_shapes() -> None:
    payload = {
        "page_summary": "A product listing page",
        "test_cases": [
            {
                "name": "Check product cards",
                "steps": ["Open the page", "Verify a product card is visible"],
                "expected_outcome": "A product card is visible",
                "priority": "urgent",
            }
        ],
        "sub_pages": [
            "https://example.com/category",
            {"name": "Product details", "url": "https://example.com/product"},
        ],
    }

    plan = _extract_test_plan(json.dumps(payload), default_url="https://example.com/")

    assert plan is not None
    assert isinstance(plan, PlanModel)
    assert plan.test_cases[0].url == "https://example.com/"
    assert plan.test_cases[0].description == "Validate Check product cards"
    assert plan.test_cases[0].priority == "medium"
    assert plan.sub_pages[0].reason == "Discovered internal page"
    assert plan.sub_pages[1].reason == "Product details"
    assert plan.sub_pages[0].requires_auth is False


def test_plan_parser_rejects_payload_without_actionable_tests() -> None:
    payload = {
        "page_summary": "Missing steps",
        "test_cases": [{"name": "Incomplete", "steps": []}],
        "sub_pages": [],
    }

    assert _extract_test_plan(json.dumps(payload), default_url="https://example.com/") is None


@pytest.mark.asyncio
async def test_openrouter_planner_requests_structured_output(monkeypatch) -> None:
    class FakeResponse:
        completion = PlanModel(
            page_summary="A page",
            test_cases=[
                {
                    "name": "Load page",
                    "description": "Verify the page loads",
                    "url": "https://example.com/",
                    "steps": ["Open the page"],
                    "expected_outcome": "The page loads",
                    "priority": "high",
                }
            ],
            sub_pages=[],
        )

    class FakeLLM:
        provider = "openrouter"

        def __init__(self) -> None:
            self.output_format = None

        async def ainvoke(self, messages, **kwargs):
            self.output_format = kwargs.get("output_format")
            return FakeResponse()

    fake_llm = FakeLLM()
    monkeypatch.setattr("src.llm.factory.create_llm", lambda config: fake_llm)

    plan = await _call_legacy_planner(
        "URL to test: https://example.com/",
        load_config("config.yaml"),
        use_fallback=False,
        default_url="https://example.com/",
    )

    assert plan is not None
    assert fake_llm.output_format is PlanModel
