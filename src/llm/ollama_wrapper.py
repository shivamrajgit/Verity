"""ChatOllama wrapper that fixes malformed action JSON output.

Some Ollama models (e.g. gpt-oss:120b-cloud) generate browser-use actions
with incorrect key names — typically wrapping inner fields in ``"type"``
instead of the correct action name (``"input"``, ``"click"``, etc.).

This wrapper intercepts the raw JSON response when ``output_format`` is
provided, detects and fixes the malformed action keys, then validates
against the expected Pydantic schema.
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar, overload

import httpx
from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

# ── Action inference rules ──
# Maps inner field combinations → correct browser-use action key.
# Order matters: more specific patterns first.
_ACTION_INFERENCE_RULES: list[tuple[set[str], set[str], str]] = [
    # (required_fields, forbidden_fields, action_name)
    ({"index", "text"}, set(), "input"),
    ({"url"}, set(), "navigate"),
    ({"keys"}, set(), "send_keys"),
    ({"seconds"}, set(), "wait"),
    ({"tab_id"}, set(), "switch"),
    ({"text", "success"}, {"index"}, "done"),
    ({"text"}, {"index", "url", "keys"}, "done"),
    ({"direction"}, set(), "scroll"),
    ({"down"}, set(), "scroll"),
    ({"query"}, set(), "extract"),
    ({"index"}, {"text", "url", "keys"}, "click"),
]

# All valid browser-use action key names (used to detect already-correct output)
_VALID_ACTION_KEYS: set[str] = {
    "done",
    "search",
    "navigate",
    "go_back",
    "wait",
    "click",
    "input",
    "upload_file",
    "switch",
    "close",
    "extract",
    "search_page",
    "find_elements",
    "scroll",
    "send_keys",
    "find_text",
    "save_as_pdf",
    "dropdown_options",
    "select_dropdown",
    "write_file",
    "replace_file",
    "read_file",
    "read_long_content",
    "evaluate",
    "screenshot",
}


def _infer_action_name(inner: dict[str, Any]) -> str | None:
    """Infer the correct action key from the inner dict's field names.

    Args:
        inner: The value dict that the model placed under the wrong key.

    Returns:
        Correct action key name, or None if unrecognizable.
    """
    fields = set(inner.keys())
    for required, forbidden, action in _ACTION_INFERENCE_RULES:
        if required <= fields and not (forbidden & fields):
            return action
    return None


def _fix_actions(data: dict[str, Any]) -> dict[str, Any]:
    """Fix malformed action entries in the parsed AgentOutput dict.

    Detects actions wrapped in ``"type"`` or other wrong keys and
    replaces them with the correct action key inferred from inner fields.

    Args:
        data: Parsed JSON dict (expected to have ``"action"`` list).

    Returns:
        Fixed dict (mutated in-place and returned).
    """
    actions = data.get("action")
    if not isinstance(actions, list):
        return data

    fixed_actions = []
    for action in actions:
        if not isinstance(action, dict):
            fixed_actions.append(action)
            continue

        keys = set(action.keys())

        # Already has a valid action key — check if inner fields need fixing
        matched_valid = keys & _VALID_ACTION_KEYS
        if matched_valid:
            action = _fix_done_inner(action)
            fixed_actions.append(action)
            continue

        # Model used wrong key (e.g. "type") — try to fix
        # Iterate all keys that aren't valid action names
        fixed = False
        for bad_key in list(keys):
            inner = action.get(bad_key)
            if not isinstance(inner, dict):
                continue
            inferred = _infer_action_name(inner)
            if inferred:
                logger.debug(
                    f"Fixing action key: '{bad_key}' → '{inferred}' "
                    f"(inner fields: {set(inner.keys())})"
                )
                fixed_actions.append({inferred: inner})
                fixed = True
                break

        if not fixed:
            # Can't fix — pass through and let Pydantic report the error
            fixed_actions.append(action)

    data["action"] = fixed_actions
    return data


def _fix_done_inner(action: dict[str, Any]) -> dict[str, Any]:
    """Fix malformed inner fields of a ``done`` action.

    Some models output ``{"done": {"success": true, "evidence": "..."}}``
    instead of the expected ``{"done": {"text": "..."}}``.
    This converts ``success``/``evidence`` fields to the required ``text`` field.

    Args:
        action: A single action dict that already has a valid action key.

    Returns:
        The (possibly mutated) action dict.
    """
    inner = action.get("done")
    if not isinstance(inner, dict):
        return action

    # If 'text' field already present, nothing to fix
    if "text" in inner:
        return action

    # Build text from success/evidence fields
    parts: list[str] = []
    if "evidence" in inner:
        parts.append(str(inner["evidence"]))
    if "success" in inner:
        verdict = "PASS" if inner["success"] else "FAIL"
        if parts:
            parts.insert(0, verdict + ":")
        else:
            parts.append(verdict)

    if parts:
        logger.debug(
            f"Fixing done inner fields: {set(inner.keys())} → text"
        )
        action["done"] = {"text": " ".join(parts)}

    return action


class ChatOllamaFixed(BaseChatModel):
    """ChatOllama wrapper that auto-fixes malformed action JSON output.

    Delegates to the real ChatOllama but intercepts structured output
    responses to fix action key names before Pydantic validation.
    """

    def __init__(
        self,
        model: str,
        host: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        ollama_options: dict[str, Any] | None = None,
        client_params: dict[str, Any] | None = None,
    ) -> None:
        """Initialize wrapper around ChatOllama.

        Args:
            model: Ollama model name.
            host: Ollama server URL.
            timeout: Request timeout.
            ollama_options: Ollama-specific model options (temperature, etc.).
            client_params: Additional client kwargs.
        """
        from browser_use.llm import ChatOllama

        self._inner = ChatOllama(
            model=model,
            host=host,
            timeout=timeout,
            ollama_options=ollama_options,
            client_params=client_params,
        )

    @property
    def provider(self) -> str:
        """Return provider name for browser-use Agent checks."""
        return self._inner.provider

    @property
    def model(self) -> str:
        """Return model name for browser-use Agent internals."""
        return self._inner.model

    def __getattr__(self, item: str) -> Any:
        """Forward any unresolved attribute access to the inner ChatOllama.

        Args:
            item: Attribute name.

        Returns:
            Attribute from the inner ChatOllama instance.
        """
        return getattr(self._inner, item)

    @property
    def name(self) -> str:
        """Return model name."""
        return self._inner.name

    @overload
    async def ainvoke(
        self, messages: list[BaseMessage], output_format: None = None, **kwargs: Any
    ) -> ChatInvokeCompletion[str]: ...

    @overload
    async def ainvoke(
        self, messages: list[BaseMessage], output_format: type[T], **kwargs: Any
    ) -> ChatInvokeCompletion[T]: ...

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        output_format: type[T] | None = None,
        **kwargs: Any,
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """Invoke the LLM with optional output fixing for structured output.

        When ``output_format`` is provided, intercepts the raw JSON,
        fixes action keys, and re-validates against the schema.

        Args:
            messages: Chat messages.
            output_format: Optional Pydantic model class for structured output.
            **kwargs: Additional arguments.

        Returns:
            ChatInvokeCompletion with correct completion type.

        Raises:
            ModelProviderError: If LLM call or parsing fails.
        """
        if output_format is None:
            # Plain text mode — no fixing needed
            return await self._inner.ainvoke(messages, output_format=None, **kwargs)

        # Structured output mode — intercept and fix
        try:
            from browser_use.llm.ollama.serializer import OllamaMessageSerializer

            ollama_messages = OllamaMessageSerializer.serialize_messages(messages)
            schema = output_format.model_json_schema()

            response = await self._inner.get_client().chat(
                model=self._inner.model,
                messages=ollama_messages,
                format=schema,
                options=self._inner.ollama_options,
            )

            raw_text = response.message.content or ""

            if not raw_text.strip():
                raise ModelProviderError(message="Empty response from Ollama", model=self.name)

            # Try to parse and fix the JSON
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as e:
                raise ModelProviderError(
                    message=f"Invalid JSON from Ollama: {e}", model=self.name
                ) from e

            # Fix action keys if this looks like an AgentOutput
            if "action" in data and isinstance(data["action"], list):
                data = _fix_actions(data)

            # Validate against the expected schema
            try:
                completion = output_format.model_validate(data)
            except Exception:
                # If fix didn't help, try the original raw text as last resort
                logger.debug("Fixed JSON still failed validation, trying original")
                completion = output_format.model_validate_json(raw_text)

            return ChatInvokeCompletion(completion=completion, usage=None)

        except ModelProviderError:
            raise
        except Exception as e:
            raise ModelProviderError(message=str(e), model=self.name) from e
