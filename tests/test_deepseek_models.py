from pgimcode.agents.orchestrator import _build_model, _resolve_agent_model_names
from pgimcode.config import Settings
from pgimcode.input_handler import ModelSelector
from pgimcode.models import AVAILABLE_MODELS, ModelProvider, get_default_model_for_provider


REQUESTED_DEEPSEEK_IDS = {
    "deepseek-coder-v2",
    "deepseek-v3",
    "deepseek-v3.5",
    "deepseek-v4",
    "deepseek-r1",
    "deepseek-r2",
    "deepseek-r3",
}


OLD_DEEPSEEK_IDS = {
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-coder",
}


def test_deepseek_registry_includes_requested_models_and_removes_old_aliases():
    deepseek_ids = {
        model.id
        for model in AVAILABLE_MODELS.values()
        if model.provider == ModelProvider.DEEPSEEK
    }

    assert REQUESTED_DEEPSEEK_IDS.issubset(deepseek_ids)
    assert "deepseek-v4-flash" in deepseek_ids
    assert "deepseek-v4-pro" in deepseek_ids
    assert deepseek_ids.isdisjoint(OLD_DEEPSEEK_IDS)
    assert get_default_model_for_provider(ModelProvider.DEEPSEEK) == "deepseek-v4-flash"

    for model_id in REQUESTED_DEEPSEEK_IDS:
        assert AVAILABLE_MODELS[model_id].pricing_note


def test_deepseek_selection_updates_provider_and_base_url(monkeypatch):
    monkeypatch.setattr(Settings, "save_model_choice", lambda self: None)
    settings = Settings(model_name="gemini-3.5-flash")

    ModelSelector.apply_model_selection(settings, "deepseek-v3.5")

    assert settings.model_name == "deepseek-v3.5"
    assert settings.api_provider == "deepseek"
    assert settings.api_base_url == "https://api.deepseek.com/v1"


def test_agent_model_selection_allows_different_models(monkeypatch):
    monkeypatch.setattr(Settings, "save_model_choice", lambda self: None)
    settings = Settings(model_name="gemini-3.5-flash")

    ModelSelector.apply_agent_model_selection(settings, "reader", "deepseek-v4-pro")
    ModelSelector.apply_agent_model_selection(settings, "executor", "deepseek-r1")

    resolved = _resolve_agent_model_names(settings)
    assert resolved["reader"] == "deepseek-v4-pro"
    assert resolved["executor"] == "deepseek-r1"
    assert resolved["editor"] == "gemini-3.5-flash"
    assert resolved["planner"] == "gemini-3.5-flash"
    assert resolved["verifier"] == "gemini-3.5-flash"

    ModelSelector.apply_agent_model_selection(settings, "reader", None)
    assert _resolve_agent_model_names(settings)["reader"] == "gemini-3.5-flash"


def test_stale_deepseek_main_and_agent_models_are_migrated():
    settings = Settings(
        model_name="deepseek-chat",
        api_provider="deepseek",
        reader_model_name="deepseek-reasoner",
    )

    assert settings.model_name == "deepseek-v4-flash"
    assert settings.api_provider == "deepseek"
    assert settings.reader_model_name is None


def test_deepseek_model_builder_uses_openai_compatible_endpoint():
    settings = Settings(
        model_name="deepseek-v4-flash",
        api_provider="deepseek",
        deepseek_api_key="fake-key-for-construction-only",
    )

    model = _build_model(settings, "deepseek-v4-flash")

    assert type(model).__name__ == "ChatOpenAI"
    assert model.model_name == "deepseek-v4-flash"
    assert str(model.openai_api_base) == "https://api.deepseek.com/v1"
