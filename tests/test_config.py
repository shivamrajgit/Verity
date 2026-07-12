from copy import deepcopy

import pytest

from src.config import AppConfig, load_config


def test_config_loads_current_configuration() -> None:
    config = load_config("config.yaml")

    assert config.target_url.startswith("https://")
    assert config.llm.planner.provider == "openrouter"
    assert config.llm.planner.model == "openrouter/auto"
    assert config.llm.executor.provider == "openrouter"
    assert config.llm.summarizer.provider == "openrouter"
    assert config.llm.fallback.provider == "openrouter"
    assert config.llm.fallback.model == "openrouter/auto"
    assert config.llm.fallback.fallback_models == []
    assert config.security.allow_private_targets is False


def test_config_rejects_invalid_target_url() -> None:
    data = load_config("config.yaml").model_dump()
    data["target_url"] = "https://"

    with pytest.raises(ValueError, match=r"absolute http\(s\) URL"):
        AppConfig.model_validate(data)


def test_config_rejects_unknown_provider() -> None:
    data = deepcopy(load_config("config.yaml").model_dump())
    data["llm"]["executor"]["provider"] = "not-a-provider"

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        AppConfig.model_validate(data)
