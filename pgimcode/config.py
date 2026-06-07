"""Application settings."""

from pathlib import Path

from platformdirs import user_config_dir
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """pgimcode settings, sourced from env + config file."""

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
    openai_api_key: str | None = None
    model_name: str = "gpt-4o"
    llm_max_turns: int = 50
    llm_temperature: float = 0.2
    api_provider: str = "openai"
    api_base_url: str | None = None
    deepseek_api_key: str | None = None

    def get_active_api_key(self) -> str | None:
        """Return any available API key, preferring the active provider."""
        if self.api_provider == "deepseek" and self.deepseek_api_key:
            return self.deepseek_api_key
        if self.api_provider == "openai" and self.openai_api_key:
            return self.openai_api_key
        return self.deepseek_api_key or self.openai_api_key

    def resolve_provider(self) -> str:
        """Auto-detect the best provider based on available (non-placeholder) keys."""
        def _is_real(key: str | None) -> bool:
            if not key:
                return False
            return not key.endswith("-here") and len(key) > 20

        has_openai = _is_real(self.openai_api_key)
        has_deepseek = _is_real(self.deepseek_api_key)

        if self.api_provider == "deepseek" and has_deepseek:
            return "deepseek"
        if self.api_provider == "openai" and has_openai:
            return "openai"
        if has_deepseek:
            return "deepseek"
        if has_openai:
            return "openai"
        return self.api_provider