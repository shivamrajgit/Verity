"""Application configuration — loads config.yaml + env vars."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

SUPPORTED_LLM_PROVIDERS = frozenset({"openrouter", "groq", "ollama", "nvidia", "openai", "gemini"})


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    provider: str = Field(
        description="Provider name: openrouter, groq, ollama, nvidia, openai, gemini"
    )
    model: str = Field(description="Model identifier")
    base_url: str | None = Field(default=None, description="Custom endpoint URL")
    api_key_env: str | None = Field(default=None, description="Env var name for API key")
    fallback_models: list[str] = Field(
        default_factory=list,
        description="OpenRouter model IDs to try after the primary model fails",
    )
    max_output_tokens: int = Field(
        default=4096,
        ge=256,
        le=16384,
        description="Maximum completion tokens per provider request",
    )

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        """Normalize and validate provider names at config load time."""
        provider = value.strip().lower()
        if provider not in SUPPORTED_LLM_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
            raise ValueError(f"Unsupported LLM provider '{value}'. Choose one of: {supported}")
        return provider

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject blank model names before the graph starts."""
        model = value.strip()
        if not model:
            raise ValueError("LLM model must not be empty")
        return model

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class LLMConfig(BaseModel):
    """LLM configuration for all agent roles."""

    planner: LLMProviderConfig
    executor: LLMProviderConfig
    summarizer: LLMProviderConfig
    fallback: LLMProviderConfig | None = None


class ConcurrencyConfig(BaseModel):
    """Concurrency settings for parallel executor runs."""

    max_executors: int = Field(default=4, ge=1, le=20)
    stagger_delay_seconds: float = Field(default=2.0, ge=0.0)
    step_timeout: int | None = Field(
        default=None,
        ge=30,
        description="Maximum seconds per executor, or null for no timeout",
    )
    max_steps: int = Field(default=15, ge=1, le=100)


class DepthConfig(BaseModel):
    """Recursion depth settings."""

    max_depth: int = Field(default=2, ge=0, le=10)


class ApprovalConfig(BaseModel):
    """Human-in-the-loop approval settings."""

    mode: Literal["interrupt", "auto_approve", "auto_decline"] = "interrupt"
    timeout_seconds: int = Field(default=120, ge=10)


class ReportConfig(BaseModel):
    """Report output settings."""

    output_path: str = "report.md"


class BrowserConfig(BaseModel):
    """Browser settings for browser-use sessions."""

    headless: bool = True
    proxy: str | None = None
    use_cloud: bool = False
    allowed_domains_extra: list[str] = Field(
        default_factory=list,
        description=("Additional allowed domains for browser navigation (e.g., auth providers)."),
    )


class SecurityConfig(BaseModel):
    """Target and server safety controls."""

    allow_private_targets: bool = Field(
        default=False,
        description="Allow localhost/private-IP targets; keep disabled for public deployments.",
    )
    allowed_target_domains: list[str] = Field(
        default_factory=list,
        description="Optional exact hostnames or *.example.com patterns permitted as targets.",
    )


class CostConfig(BaseModel):
    """Cost tracking and budget settings."""

    max_total_cost: float | None = None
    calculate_cost: bool = True


class AppConfig(BaseModel):
    """Root application configuration."""

    target_url: str = Field(description="Root URL to test")
    extra_urls: list[str] = Field(
        default_factory=list,
        description="Additional URL paths or full URLs to seed into the planner queue",
    )
    llm: LLMConfig
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    depth: DepthConfig = Field(default_factory=DepthConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    cost: CostConfig = Field(default_factory=CostConfig)

    @model_validator(mode="after")
    def validate_config(self) -> AppConfig:
        """Validate that the configuration is coherent."""
        parsed = urlsplit(self.target_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(
                "target_url must be a valid absolute http(s) URL with a hostname, "
                f"got: {self.target_url}"
            )
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("target_url must not contain embedded credentials")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"target_url contains an invalid port: {self.target_url}") from exc
        if port == 0:
            raise ValueError("target_url port must be greater than zero")
        return self


def load_config(config_path: str | Path) -> AppConfig:
    """Load and validate configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid config file format: expected a YAML mapping, got {type(raw)}")

    return AppConfig.model_validate(raw)
