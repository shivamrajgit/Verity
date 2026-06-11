"""Application configuration — loads config.yaml + env vars."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    provider: str = Field(
        description="Provider name: openrouter, groq, ollama, nvidia, openai, gemini"
    )
    model: str = Field(description="Model identifier")
    base_url: str | None = Field(default=None, description="Custom endpoint URL")
    api_key_env: str | None = Field(default=None, description="Env var name for API key")

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
    step_timeout: int = Field(default=180, ge=30)


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
        description=(
            "Additional allowed domains for browser navigation (e.g., auth providers)."
        ),
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
    concurrency: ConcurrencyConfig = ConcurrencyConfig()
    depth: DepthConfig = DepthConfig()
    approval: ApprovalConfig = ApprovalConfig()
    report: ReportConfig = ReportConfig()
    browser: BrowserConfig = BrowserConfig()
    cost: CostConfig = CostConfig()

    @model_validator(mode="after")
    def validate_config(self) -> AppConfig:
        """Validate that the configuration is coherent."""
        if not self.target_url.startswith(("http://", "https://")):
            raise ValueError(
                f"target_url must start with http:// or https://, got: {self.target_url}"
            )
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
