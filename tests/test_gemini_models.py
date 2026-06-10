from langchain_google_genai import ChatGoogleGenerativeAI

from pgimcode.config import Settings
from pgimcode.input_handler import ModelSelector
from pgimcode.models import AVAILABLE_MODELS, ModelProvider, get_default_model_for_provider


def test_gemini_registry_uses_native_valid_model_ids():
    gemini_ids = [
        model.id
        for model in AVAILABLE_MODELS.values()
        if model.provider == ModelProvider.GEMINI
    ]

    assert "gemini-3.5-pro-preview" not in gemini_ids
    assert "gemini-3.1-pro" not in gemini_ids
    assert "gemini-3.5-flash" in gemini_ids
    assert "gemini-3.1-pro-preview" in gemini_ids
    assert "gemini-3.1-pro-preview-customtools" in gemini_ids
    assert "gemini-3.1-flash-lite" in gemini_ids
    assert get_default_model_for_provider(ModelProvider.GEMINI) == "gemini-3.5-flash"


def test_gemini_selection_clears_openai_compat_base_url(monkeypatch):
    monkeypatch.setattr(Settings, "save_model_choice", lambda self: None)
    settings = Settings()
    ModelSelector.apply_model_selection(settings, "gemini-3.5-flash")

    assert settings.model_name == "gemini-3.5-flash"
    assert settings.api_provider == "gemini"
    assert settings.api_base_url is None


def test_settings_migrates_removed_gemini_model_ids():
    settings = Settings(model_name="gemini-3.5-pro-preview", api_provider="gemini")

    assert settings.model_name == "gemini-3.5-flash"
    assert settings.api_provider == "gemini"
    assert settings.api_base_url is None


def test_native_gemini_model_constructs_with_tool_safe_settings():
    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        api_key="fake-key-for-construction-only",
        thinking_level="low",
        temperature=0.2,
    )

    assert model.model == "gemini-3.5-flash"
