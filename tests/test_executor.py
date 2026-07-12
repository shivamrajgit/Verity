from src.graph.nodes.execute import _parse_executor_result
from src.llm.factory import create_llm


class UnknownResult:
    pass


class DoneResult:
    def is_done(self) -> bool:
        return True

    def is_successful(self) -> bool:
        return True


class FailedResult:
    def is_done(self) -> bool:
        return True

    def is_successful(self) -> bool:
        return False


def test_unknown_executor_result_is_not_a_pass() -> None:
    result = _parse_executor_result(UnknownResult(), "unknown", 0.1)

    assert result.status == "error"
    assert result.error_detail


def test_executor_verdicts_are_preserved() -> None:
    assert _parse_executor_result(DoneResult(), "pass", 0.1).status == "pass"
    assert _parse_executor_result(FailedResult(), "fail", 0.1).status == "fail"


def test_gemini_executor_factory_uses_browser_use_wrapper(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    llm = create_llm({"provider": "gemini", "model": "gemini-2.5-flash"})

    assert llm.provider == "google"
    assert llm.model == "gemini-2.5-flash"


def test_openrouter_factory_configures_model_fallbacks(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    llm = create_llm(
        {
            "provider": "openrouter",
            "model": "qwen/qwen3-vl-32b-instruct",
            "fallback_models": [
                "qwen/qwen3.5-flash-02-23",
                "mistralai/mistral-small-3.2-24b-instruct",
            ],
        }
    )

    assert llm.provider == "openrouter"
    assert llm.model == "qwen/qwen3-vl-32b-instruct"
    assert llm.extra_body["models"] == [
        "qwen/qwen3.5-flash-02-23",
        "mistralai/mistral-small-3.2-24b-instruct",
    ]
