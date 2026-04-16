import os
import json
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Document Quality Checker"
    VERSION: str = "0.1.0"
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    DATABASE_URL: str
    
    MODEL_PATH: str = ""
    MODEL_DIR: str = "/app/models"
    MODEL_AUTO_SELECT: bool = True
    MODEL_N_CTX: int = 8192
    MODEL_TEMPERATURE: float = 0.1
    MODEL_MAX_TOKENS: int = 700
    MODEL_N_THREADS: int = 14
    MODEL_N_THREADS_BATCH: int = 14
    MODEL_N_BATCH: int = 512
    MODEL_USE_MLOCK: bool = False
    MODEL_USE_MMAP: bool = True
    LLM_REQUEST_TIMEOUT_SECONDS: int = 180
    
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    DISABLE_LLM: bool = False
    MAX_UPLOAD_SIZE_MB: int = 10
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    @property
    def cors_origins_parsed(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            try:
                return json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                return [self.CORS_ORIGINS]
        return self.CORS_ORIGINS

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
