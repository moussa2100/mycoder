"""Application settings."""

import json
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _prefs_path() -> Path:
    """Path to the persisted user preferences file (last chosen model, etc.)."""
    return Path(user_config_dir("pgimcode")) / "prefs.json"


class Settings(BaseSettings):
    """pgimcode settings, sourced from env + config file + saved prefs."""

    model_config = SettingsConfigDict(
        env_prefix="PGIMCODE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "pgimcode"
    version: str = "0.1.0"

    session_dir: Path = Field(
        default_factory=lambda: Path(user_config_dir("pgimcode")) / "sessions"
    )
    max_turns: int = 100
    mock_delay_seconds: float = 1.5
    color_enabled: bool = True

    # Agents
    default_mode: str = "build"
    intelligence_mode: str = "graph"
    research_depth: str = "standard"
    task_board_enabled: bool = True
    self_review_enabled: bool = True

    # LLM settings
    model_name: str = "gemini-3.5-flash"
    llm_max_turns: int = 50
    llm_temperature: float = 0.2
    api_provider: str = "gemini"
    api_base_url: str | None = None
    deepseek_api_key: str | None = None
    gemini_api_key: str | None = None

    @model_validator(mode="after")
    def _apply_saved_prefs(self) -> "Settings":
        """Restore the last chosen model unless explicitly set via env/.env."""
        if "model_name" in self.model_fields_set:
            self._normalize_model_choice()
            return self
        try:
            prefs = json.loads(_prefs_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._normalize_model_choice()
            return self
        if isinstance(prefs, dict) and prefs.get("model_name"):
            self.model_name = prefs["model_name"]
            if prefs.get("api_provider") and "api_provider" not in self.model_fields_set:
                self.api_provider = prefs["api_provider"]
            if "api_base_url" not in self.model_fields_set:
                self.api_base_url = prefs.get("api_base_url")
        self._normalize_model_choice()
        return self

    def _normalize_model_choice(self) -> None:
        """Migrate stale saved model IDs to a currently supported default."""
        from pgimcode.models import (
            AVAILABLE_MODELS,
            ModelProvider,
            get_default_model_for_provider,
        )

        info = AVAILABLE_MODELS.get(self.model_name)
        if info is not None:
            self.api_provider = info.provider.value
            if not info.api_base_url:
                self.api_base_url = None
            return

        try:
            provider = ModelProvider(self.api_provider)
        except ValueError:
            provider = ModelProvider.GEMINI

        self.model_name = get_default_model_for_provider(provider)
        self.api_provider = provider.value
        fallback = AVAILABLE_MODELS.get(self.model_name)
        self.api_base_url = fallback.api_base_url or None if fallback else None

    def save_model_choice(self) -> None:
        """Persist the current model selection so future sessions reuse it."""
        path = _prefs_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "model_name": self.model_name,
                        "api_provider": self.api_provider,
                        "api_base_url": self.api_base_url,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def get_active_api_key(self) -> str | None:
        """Return any available API key, preferring the active provider."""
        if self.api_provider == "deepseek" and self.deepseek_api_key:
            return self.deepseek_api_key
        if self.api_provider == "gemini" and self.gemini_api_key:
            return self.gemini_api_key
        return self.deepseek_api_key or self.gemini_api_key

    def resolve_provider(self) -> str:
        """Auto-detect the best provider based on available (non-placeholder) keys."""
        def _is_real(key: str | None) -> bool:
            if not key:
                return False
            return not key.endswith("-here") and len(key) > 20

        has_deepseek = _is_real(self.deepseek_api_key)
        has_gemini = _is_real(self.gemini_api_key)

        if self.api_provider == "deepseek" and has_deepseek:
            return "deepseek"
        if self.api_provider == "gemini" and has_gemini:
            return "gemini"
        if has_deepseek:
            return "deepseek"
        if has_gemini:
            return "gemini"
        return self.api_provider