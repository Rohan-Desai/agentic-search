"""Application configuration, loaded from environment variables / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    agent_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

    upload_dir: Path = Path("./data/uploads")
    vector_store_dir: Path = Path("./data/chroma")

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
