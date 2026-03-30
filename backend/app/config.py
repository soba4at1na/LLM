from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # === Основные пути ===
    BASE_DIR: Path = Path(__file__).parent.parent
    
    # ←←← УКАЖИ СВОЙ РЕАЛЬНЫЙ ПУТЬ К МОДЕЛИ ←←←
    MODEL_PATH: str = "Model/default.gguf"
    # Папки проекта
    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    DATASETS_DIR: Path = BASE_DIR / "datasets"

    # === Настройки LLM ===
    CONTEXT_SIZE: int = 8192
    MAX_TOKENS: int = 1024
    TEMPERATURE: float = 0.1
    N_THREADS: int = 16                    # Для Ryzen 7 5700X
    N_BATCH: int = 512

    # === Приложение ===
    APP_NAME: str = "LLM Document Quality Checker"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-in-production-2026"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()