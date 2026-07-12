"""LLM factory — creates provider-specific chat models from config.

Uses browser-use's native LLM wrappers (browser_use.llm) which add the
`.provider` attribute required by browser-use Agent internals.
"""

from __future__ import annotations

import os
from typing import Any


def create_llm(provider_config: dict[str, Any]) -> Any:
    """Create a chat model instance based on provider configuration.

    Uses browser-use's native LLM wrappers (not raw LangChain's) so
    that `llm.provider` is available for Agent's internal checks.

    Args:
        provider_config: Dict with keys: provider, model, base_url (optional),
                         api_key_env (optional).

    Returns:
        A BaseChatModel instance compatible with browser-use Agent.

    Raises:
        ValueError: If provider is unsupported or API key is missing.
    """
    provider = provider_config["provider"].lower()
    model = provider_config["model"]
    base_url = provider_config.get("base_url")
    api_key_env = provider_config.get("api_key_env")

    if provider == "openrouter":
        from browser_use.llm import ChatOpenRouter

        api_key = _resolve_api_key(api_key_env, "OPENROUTER_API_KEY")
        extra_body = {}
        fallback_models = provider_config.get("fallback_models") or []
        if fallback_models:
            extra_body["models"] = fallback_models
        return ChatOpenRouter(
            model=model,
            api_key=api_key,
            extra_body=extra_body or None,
            max_retries=3,
            **({"base_url": base_url} if base_url else {}),
        )

    elif provider == "groq":
        from browser_use.llm import ChatGroq

        api_key = _resolve_api_key(api_key_env, "GROQ_API_KEY")
        return ChatGroq(model=model, api_key=api_key)

    elif provider == "ollama":
        from src.llm.ollama_wrapper import ChatOllamaFixed

        return ChatOllamaFixed(
            model=model,
            host=base_url or "http://localhost:11434",
            timeout=120.0,
            ollama_options={"temperature": 0, "num_ctx": 16384},
        )

    elif provider == "nvidia":
        from browser_use.llm import ChatOpenAI

        api_key = _resolve_api_key(api_key_env, "NVIDIA_API_KEY")
        return ChatOpenAI(
            model=model,
            base_url=base_url or "https://integrate.api.nvidia.com/v1",
            api_key=api_key,
        )

    elif provider == "openai":
        from browser_use.llm import ChatOpenAI

        api_key = _resolve_api_key(api_key_env, "OPENAI_API_KEY")
        return ChatOpenAI(model=model, api_key=api_key)

    elif provider == "gemini":
        from browser_use.llm import ChatGoogle

        api_key = _resolve_api_key(api_key_env, "GOOGLE_API_KEY")
        return ChatGoogle(
            model=model,
            api_key=api_key,
            temperature=0.0,
            max_retries=5,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: openrouter, groq, ollama, nvidia, openai, gemini"
        )


def _resolve_api_key(explicit_env: str | None, default_env: str) -> str:
    """Resolve API key from environment variable.

    Args:
        explicit_env: Explicitly configured env var name (from config).
        default_env: Default env var to check if explicit not provided.

    Returns:
        The API key string.

    Raises:
        ValueError: If the key is not found in environment.
    """
    env_var = explicit_env or default_env
    key = os.environ.get(env_var, "")
    if not key:
        raise ValueError(
            f"API key not found. Set the '{env_var}' environment variable. "
            f"See .env.example for reference."
        )
    return key
