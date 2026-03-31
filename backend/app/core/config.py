import json
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    # Проект
    PROJECT_NAME: str = "LLM Document Quality Checker"
    VERSION: str = "0.2.0"

    # Безопасность
    SECRET_KEY: str = "super-secret-key-change-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # База данных
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"   # по умолчанию SQLite для разработки

    # LLM
    MODEL_PATH: str = r"C:\Models\qwen2.5-14b-instruct-uncensored-q5_k_m.gguf"
    MODEL_N_CTX: int = 8192
    MODEL_TEMPERATURE: float = 0.1
    MODEL_TOP_P: float = 0.9
    N_GPU_LAYERS: int = 0          # 0 = CPU only, -1 = все GPU слои
    N_THREADS: Optional[int] = None

    # CORS
    CORS_ORIGINS: str = '["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8080"]'

    # Режим разработки
    DISABLE_LLM: bool = False
    DEBUG: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception:
            return ["http://localhost:3000"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()