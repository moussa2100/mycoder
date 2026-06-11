from langchain_openai import ChatOpenAI

from pgimcode.agents.orchestrator import _build_model
from pgimcode.config import Settings
from pgimcode.models import AVAILABLE_MODELS, ModelProvider, get_default_model_for_provider


def test_deepinfra_registry_includes_nemotron():
    deepinfra_ids = [
        model.id
        for model in AVAILABLE_MODELS.values()
        if model.provider == ModelProvider.DEEPINFRA
    ]

    assert "nemotron-3-ultra-550b" in deepinfra_ids
    assert get_default_model_for_provider(ModelProvider.DEEPINFRA) == "nemotron-3-ultra-550b"


def test_deepinfra_model_builder_uses_api_model_name():
    settings = Settings(
        model_name="nemotron-3-ultra-550b",
        api_provider="deepinfra",
        deepinfra_api_key="fake-key-for-construction-only",
    )

    model = _build_model(settings, "nemotron-3-ultra-550b")

    assert type(model).__name__ == "ChatOpenAI"
    assert model.model_name == "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B"
    assert str(model.openai_api_base) == "https://api.deepinfra.com/v1/openai"
