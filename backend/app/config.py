from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Digital Inspector API"
    api_prefix: str = "/api"
    storage_dir: Path = Path("storage")
    database_url: str = "sqlite:///./app.db"
    log_level: str = "INFO"
    model_path: Path = Path("models/best.pt")
    model_confidence: float = 0.35
    pdf_dpi: int = 200

    model_config = SettingsConfigDict(
        env_prefix="DI_",
        env_file=".env",
        protected_namespaces=("settings_",),
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    model_path = settings.model_path
    if not model_path.is_absolute():
        # Resolve relative to the backend package root (/app in Docker, backend/ locally)
        candidate = (Path(__file__).resolve().parents[1] / model_path).resolve()
        if candidate.exists():
            model_path = candidate
        else:
            repo_root_candidate = (Path(__file__).resolve().parents[2] / model_path).resolve()
            if repo_root_candidate.exists():
                model_path = repo_root_candidate
    if model_path.exists():
        settings.model_path = model_path
    return settings
