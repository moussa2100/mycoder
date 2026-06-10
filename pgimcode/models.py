"""Model registry: available LLM providers and models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(str, Enum):
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


@dataclass
class ModelInfo:
    id: str
    name: str
    provider: ModelProvider
    context_window: int
    description: str
    api_base_url: str
    pricing_note: str = ""


AVAILABLE_MODELS: dict[str, ModelInfo] = {
    "deepseek-chat": ModelInfo(
        id="deepseek-chat",
        name="DeepSeek Chat (v3)",
        provider=ModelProvider.DEEPSEEK,
        context_window=128000,
        description="DeepSeek flagship chat model. Strong coding performance.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.27/$1.10 per 1M tokens",
    ),
    "deepseek-reasoner": ModelInfo(
        id="deepseek-reasoner",
        name="DeepSeek Reasoner (r1)",
        provider=ModelProvider.DEEPSEEK,
        context_window=64000,
        description="DeepSeek reasoning model. Chain-of-thought for complex tasks.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.55/$2.19 per 1M tokens",
    ),
    # Gemini models (Google AI via OpenAI-compatible endpoint)
    "gemini-3.5-pro-preview": ModelInfo(
        id="gemini-3.5-pro-preview",
        name="Gemini 3.5 Pro",
        provider=ModelProvider.GEMINI,
        context_window=2_000_000,
        description="Google Gemini 3.5 Pro Preview. Premium reasoning & coding with 2M context.",
        api_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        pricing_note="~$2.50/$15.00 per 1M tokens",
    ),
    "gemini-3.5-flash": ModelInfo(
        id="gemini-3.5-flash",
        name="Gemini 3.5 Flash",
        provider=ModelProvider.GEMINI,
        context_window=1_000_000,
        description="Google Gemini 3.5 Flash. Fast, cost-effective with 1M context.",
        api_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        pricing_note="$1.50/$9.00 per 1M tokens",
    ),
    "gemini-3.1-pro": ModelInfo(
        id="gemini-3.1-pro",
        name="Gemini 3.1 Pro",
        provider=ModelProvider.GEMINI,
        context_window=2_000_000,
        description="Google Gemini 3.1 Pro. Strong reasoning & coding with 2M context.",
        api_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        pricing_note="$2.00/$12.00 per 1M tokens",
    ),
    "gemini-3.1-flash-lite": ModelInfo(
        id="gemini-3.1-flash-lite",
        name="Gemini 3.1 Flash Lite",
        provider=ModelProvider.GEMINI,
        context_window=1_000_000,
        description="Google Gemini 3.1 Flash Lite. Cheapest Gemini option with 1M context.",
        api_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        pricing_note="$0.25/$1.50 per 1M tokens",
    ),
}


def get_models_by_provider(provider: ModelProvider) -> list[ModelInfo]:
    """Return all models for a given provider."""
    return [m for m in AVAILABLE_MODELS.values() if m.provider == provider]


def get_model(model_id: str) -> ModelInfo | None:
    """Look up a model by its ID."""
    return AVAILABLE_MODELS.get(model_id)


def resolve_model_info(model_id: str) -> ModelInfo:
    """Resolve model info, raising ValueError if not found."""
    info = AVAILABLE_MODELS.get(model_id)
    if info is None:
        raise ValueError(
            f"Unknown model: '{model_id}'. "
            f"Available: {', '.join(AVAILABLE_MODELS.keys())}"
        )
    return info


def get_default_model_for_provider(provider: ModelProvider) -> str:
    """Return the default model ID for a given provider."""
    defaults = {
        ModelProvider.DEEPSEEK: "deepseek-chat",
        ModelProvider.GEMINI: "gemini-3.5-flash",
    }
    return defaults.get(provider, "deepseek-chat")
