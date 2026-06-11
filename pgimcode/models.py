"""Model registry: available LLM providers and models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(str, Enum):
    DEEPSEEK = "deepseek"
    DEEPINFRA = "deepinfra"
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
    api_model_name: str = ""


AVAILABLE_MODELS: dict[str, ModelInfo] = {
    "deepseek-v4-flash": ModelInfo(
        id="deepseek-v4-flash",
        name="DeepSeek V4 Flash",
        provider=ModelProvider.DEEPSEEK,
        context_window=1_000_000,
        description="Official DeepSeek V4 Flash endpoint. Fast, low-cost, supports tools and thinking mode.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.14/$0.28 per 1M tokens; cache hit $0.0028 in",
    ),
    "deepseek-v4-pro": ModelInfo(
        id="deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        provider=ModelProvider.DEEPSEEK,
        context_window=1_000_000,
        description="Official DeepSeek V4 Pro endpoint. Higher quality V4 tier for coding and reasoning.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.435/$0.87 per 1M tokens; cache hit $0.003625 in",
    ),
    "deepseek-coder-v2": ModelInfo(
        id="deepseek-coder-v2",
        name="DeepSeek Coder V2",
        provider=ModelProvider.DEEPSEEK,
        context_window=128_000,
        description="DeepSeek Coder V2 model ID requested by the user. May require an endpoint that exposes legacy coder IDs.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.14/$0.28 per 1M tokens; unofficial/legacy",
    ),
    "deepseek-v3": ModelInfo(
        id="deepseek-v3",
        name="DeepSeek V3",
        provider=ModelProvider.DEEPSEEK,
        context_window=128_000,
        description="DeepSeek V3 model ID requested by the user. May require an endpoint that still exposes V3.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.27/$1.10 per 1M tokens; legacy estimate",
    ),
    "deepseek-v3.5": ModelInfo(
        id="deepseek-v3.5",
        name="DeepSeek V3.5",
        provider=ModelProvider.DEEPSEEK,
        context_window=128_000,
        description="DeepSeek V3.5 model ID requested by the user. Pricing is not listed in current official DeepSeek docs.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="Not published by official DeepSeek pricing",
    ),
    "deepseek-v4": ModelInfo(
        id="deepseek-v4",
        name="DeepSeek V4",
        provider=ModelProvider.DEEPSEEK,
        context_window=1_000_000,
        description="Generic DeepSeek V4 model ID requested by the user. Current official endpoint lists v4-flash/v4-pro instead.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.50/$1.50 per 1M tokens; third-party estimate",
    ),
    "deepseek-r1": ModelInfo(
        id="deepseek-r1",
        name="DeepSeek R1",
        provider=ModelProvider.DEEPSEEK,
        context_window=128_000,
        description="DeepSeek R1 reasoning model ID requested by the user. May require an endpoint that still exposes R1.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="$0.55/$2.19 per 1M tokens; legacy reasoning",
    ),
    "deepseek-r2": ModelInfo(
        id="deepseek-r2",
        name="DeepSeek R2",
        provider=ModelProvider.DEEPSEEK,
        context_window=128_000,
        description="DeepSeek R2 reasoning model ID requested by the user. Pricing is not listed in current official DeepSeek docs.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="Not published by official DeepSeek pricing",
    ),
    "deepseek-r3": ModelInfo(
        id="deepseek-r3",
        name="DeepSeek R3",
        provider=ModelProvider.DEEPSEEK,
        context_window=128_000,
        description="DeepSeek R3 reasoning model ID requested by the user. Pricing is not listed in current official DeepSeek docs.",
        api_base_url="https://api.deepseek.com/v1",
        pricing_note="Not published by official DeepSeek pricing",
    ),
    # DeepInfra models (OpenAI-compatible inference API)
    "nemotron-3-ultra-550b": ModelInfo(
        id="nemotron-3-ultra-550b",
        name="Nemotron 3 Ultra 550B",
        provider=ModelProvider.DEEPINFRA,
        context_window=128_000,
        description="NVIDIA Nemotron 3 Ultra 550B served via DeepInfra. High-capacity reasoning and chat model.",
        api_base_url="https://api.deepinfra.com/v1/openai",
        pricing_note="DeepInfra pay-per-token; cost varies by plan",
        api_model_name="nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B",
    ),
    # Gemini models (Google AI via native Gemini API)
    "gemini-3.5-flash": ModelInfo(
        id="gemini-3.5-flash",
        name="Gemini 3.5 Flash",
        provider=ModelProvider.GEMINI,
        context_window=1_048_576,
        description="Google Gemini 3.5 Flash. Latest fast agentic/coding model with 1M context.",
        api_base_url="",
        pricing_note="$1.50/$9.00 per 1M tokens",
    ),
    "gemini-3.1-pro-preview": ModelInfo(
        id="gemini-3.1-pro-preview",
        name="Gemini 3.1 Pro",
        provider=ModelProvider.GEMINI,
        context_window=1_048_576,
        description="Google Gemini 3.1 Pro Preview. Premium reasoning & coding model.",
        api_base_url="",
        pricing_note="$2.00/$12.00 per 1M tokens",
    ),
    "gemini-3.1-pro-preview-customtools": ModelInfo(
        id="gemini-3.1-pro-preview-customtools",
        name="Gemini 3.1 Pro Custom Tools",
        provider=ModelProvider.GEMINI,
        context_window=1_048_576,
        description="Gemini 3.1 Pro endpoint optimized for custom coding tools.",
        api_base_url="",
        pricing_note="$2.00/$12.00 per 1M tokens",
    ),
    "gemini-3.1-flash-lite": ModelInfo(
        id="gemini-3.1-flash-lite",
        name="Gemini 3.1 Flash Lite",
        provider=ModelProvider.GEMINI,
        context_window=1_048_576,
        description="Google Gemini 3.1 Flash Lite. Low-cost high-volume model with 1M context.",
        api_base_url="",
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
        ModelProvider.DEEPSEEK: "deepseek-v4-flash",
        ModelProvider.DEEPINFRA: "nemotron-3-ultra-550b",
        ModelProvider.GEMINI: "gemini-3.5-flash",
    }
    return defaults.get(provider, "deepseek-v4-flash")
