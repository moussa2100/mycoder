"""Application settings."""

from pathlib import Path

from platformdirs import user_config_dir
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """pgimcode settings, sourced from env + config file."""

    # Config source: env vars (PGIMCODE_XXX) or optional .env
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

    # LLM settings
    openai_api_key: str | None = None
    model_name: str = "gpt-4o"
    llm_max_turns: int = 50
    llm_temperature: float = 0.2