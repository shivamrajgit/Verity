import sys

from src.config import load_config
from src.main import _apply_provider_override, parse_args


def test_gemini_flag_overrides_all_roles_and_keeps_openrouter_fallback() -> None:
    config = load_config("config.yaml")

    _apply_provider_override(config, use_gemini=True)

    assert config.llm.planner.provider == "gemini"
    assert config.llm.executor.provider == "gemini"
    assert config.llm.summarizer.provider == "gemini"
    assert config.llm.planner.model == "gemini-2.5-flash"
    assert config.llm.fallback.provider == "openrouter"
    assert config.llm.fallback.model == "openrouter/auto"


def test_gemini_flag_is_available_in_cli(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["verity", "--Gemini"])

    args = parse_args()

    assert args.gemini is True
