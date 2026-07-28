"""Configure the OpenAI Agents SDK from application settings."""
from __future__ import annotations

from agents import set_default_openai_key

from app.core.config import Settings, get_settings


def configure_agents_sdk(settings: Settings | None = None) -> None:
    """Give the Agents SDK the API key loaded by pydantic-settings."""

    configured = settings or get_settings()
    if configured.openai_api_key:
        set_default_openai_key(
            configured.openai_api_key,
            use_for_tracing=False,
        )
