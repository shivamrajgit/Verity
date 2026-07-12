"""Direct LLM chat — plain provider calls without browser-use wrappers.

Provides a single ``call_llm_chat`` entry-point that routes to the correct
provider backend.  Used by the summarizer (and any future node that needs
a simple text-in / text-out LLM call).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.llm.retry import retry_async

logger = logging.getLogger(__name__)


async def call_llm_chat(
    system_prompt: str,
    user_prompt: str,
    provider_config: dict[str, Any],
) -> str:
    """Send a system + user message to the configured LLM and return the text.

    Args:
        system_prompt: System-level instruction.
        user_prompt: User-level content / data.
        provider_config: Provider config dict with 'provider', 'model', etc.

    Returns:
        Raw text response from the LLM.

    Raises:
        ValueError: If the provider is not supported.
        RuntimeError: If the API call fails.
    """
    provider = str(provider_config.get("provider", "")).lower()
    if provider == "gemini":
        return await _call_gemini(system_prompt, user_prompt, provider_config)
    if provider == "ollama":
        return await _call_ollama(system_prompt, user_prompt, provider_config)
    if provider == "openrouter":
        return await _call_openrouter(system_prompt, user_prompt, provider_config)
    raise ValueError(
        f"Unsupported direct-chat provider '{provider}'. "
        "Supported: 'ollama', 'gemini', 'openrouter'."
    )


# ── Ollama ────────────────────────────────────────────────────────────────────


async def _call_ollama(
    system_prompt: str,
    user_prompt: str,
    config: dict[str, Any],
) -> str:
    """Call the Ollama /api/chat endpoint directly via httpx.

    Args:
        system_prompt: System message content.
        user_prompt: User message content.
        config: Must contain 'model'; optionally 'base_url'.

    Returns:
        Assistant message text.

    Raises:
        RuntimeError: On HTTP or parsing errors.
    """
    import httpx

    model = config.get("model", "llama3.1:8b")
    base_url = config.get("base_url") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    url = f"{base_url.rstrip('/')}/api/chat"

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.3,
            "num_ctx": 8192,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Ollama chat request failed: {exc}") from exc

    text = data.get("message", {}).get("content", "")
    if not text.strip():
        raise RuntimeError("Ollama returned an empty response")

    logger.debug(f"Ollama response length: {len(text)} chars")
    return text


# ── Gemini ────────────────────────────────────────────────────────────────────


async def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    config: dict[str, Any],
) -> str:
    """Call Gemini via the google-genai SDK (text-only, no screenshot).

    Args:
        system_prompt: System instruction.
        user_prompt: User content.
        config: Must contain 'model'; optionally 'api_key_env'.

    Returns:
        Raw text response.

    Raises:
        RuntimeError: On API or key errors.
    """
    from google import genai
    from google.genai import types

    api_key_env = config.get("api_key_env", "GOOGLE_API_KEY")
    api_key = os.environ.get(api_key_env, "") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            f"Gemini API key not found. Set '{api_key_env}' or "
            "'GOOGLE_API_KEY' environment variable."
        )

    model_name = config.get("model", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)

    try:
        response = await retry_async(
            lambda: client.aio.models.generate_content(
                model=model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=system_prompt),
                            types.Part.from_text(text=user_prompt),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                ),
            ),
            operation_name="Gemini summarizer",
        )

        text = response.text or ""
        if not text.strip():
            raise RuntimeError("Gemini returned an empty response")

        logger.debug(f"Gemini response length: {len(text)} chars")
        return text

    except Exception as exc:
        raise RuntimeError(f"Gemini summarizer call failed: {exc}") from exc


async def _call_openrouter(
    system_prompt: str,
    user_prompt: str,
    config: dict[str, Any],
) -> str:
    """Call OpenRouter through Browser Use's OpenAI-compatible wrapper."""
    from browser_use.llm import ChatOpenRouter, SystemMessage, UserMessage

    api_key_env = config.get("api_key_env", "OPENROUTER_API_KEY")
    api_key = os.environ.get(api_key_env, "") or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            f"OpenRouter API key not found. Set '{api_key_env}' or "
            "'OPENROUTER_API_KEY' environment variable."
        )

    extra_body: dict[str, Any] = {
        "max_tokens": int(config.get("max_output_tokens", 4096)),
    }
    if config.get("fallback_models"):
        extra_body["models"] = config["fallback_models"]

    llm = ChatOpenRouter(
        model=config.get("model", "openrouter/auto"),
        api_key=api_key,
        extra_body=extra_body,
        max_retries=3,
    )
    response = await retry_async(
        lambda: llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                UserMessage(content=user_prompt),
            ]
        ),
        operation_name="OpenRouter chat",
    )
    text = getattr(response, "completion", None) or getattr(response, "content", None)
    text = text or str(response)
    if not str(text).strip():
        raise RuntimeError("OpenRouter returned an empty response")
    return str(text)
