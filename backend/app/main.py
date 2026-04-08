# backend/app/main.py

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.llm_service import llm_service

# Импорты роутеров
from app.api import auth
from app.api import analyze
from app.api import chat        # ← Эта строка должна быть

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Запуск LLM Document Quality Checker...")

    async with engine.begin() as conn:
        logger.info("✅ База данных подключена")

    if os.getenv("DISABLE_LLM", "false").lower() != "true":
        try:
            logger.info(f"🚀 Загрузка модели...")
            await llm_service.initialize()
            logger.info("✅ Модель успешно загружена!")
        except FileNotFoundError as e:
            logger.warning(f"⚠️ Модель не найдена: {e}")
    else:
        logger.warning("⚠️ LLM отключён — mock режим")

    logger.info("✅ Приложение готово!")
    yield
    logger.info("🛑 Приложение завершает работу...")
    await llm_service.shutdown()


app = FastAPI(
    title="LLM Document Quality Checker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])   # ← Должна быть эта строка

@app.get("/health")
async def health_check():
    return {"status": "ok", "llm_loaded": llm_service.is_initialized}

@app.get("/")
async def root():
    return {"message": "LLM Document Quality Checker API"}