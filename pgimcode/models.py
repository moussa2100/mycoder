"""Model registry: available LLM providers and models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


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
    "gpt-4o": ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        provider=ModelProvider.OPENAI,
        context_window=128000,
        description="Best overall for coding tasks. Fast, multimodal.",
        api_base_url="https://api.openai.com/v1",
        pricing_note="$2.50/$10 per 1M tokens",
    ),
    "gpt-4o-mini": ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=ModelProvider.OPENAI,
        context_window=128000,
        description="Cheaper, faster version of GPT-4o. Good for simple tasks.",
        api_base_url="https://api.openai.com/v1",
        pricing_note="$0.15/$0.60 per 1M tokens",
    ),
    "gpt-4-turbo": ModelInfo(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        provider=ModelProvider.OPENAI,
        context_window=128000,
        description="Previous generation flagship. Still solid for coding.",
        api_base_url="https://api.openai.com/v1",
        pricing_note="$10/$30 per 1M tokens",
    ),
    "o3-mini": ModelInfo(
        id="o3-mini",
        name="o3-mini",
        provider=ModelProvider.OPENAI,
        context_window=200000,
        description="Reasoning model. Great for complex multi-step problems.",
        api_base_url="https://api.openai.com/v1",
        pricing_note="$1.10/$4.40 per 1M tokens",
    ),
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
        ModelProvider.OPENAI: "gpt-4o",
        ModelProvider.DEEPSEEK: "deepseek-chat",
    }
    return defaults.get(provider, "gpt-4o")
