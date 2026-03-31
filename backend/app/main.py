# backend/app/main.py
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.llm_service import llm_service
from app.api import auth

# 🔧 Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для приложения"""
    # 🚀 Startup
    logger.info("🚀 Запуск LLM Document Quality Checker...")
    
    # Инициализация БД
    async with engine.begin() as conn:
        # Здесь можно добавить создание таблиц, если не используете Alembic
        logger.info("✅ База данных подключена")
    
    # Инициализация LLM (можно отключить для быстрой разработки)
    if os.getenv("DISABLE_LLM", "false").lower() != "true":
        try:
            logger.info(f"🚀 Загрузка модели: {Path(settings.MODEL_PATH).name} ...")
            await llm_service.initialize()
            logger.info("✅ Модель успешно загружена!")
        except FileNotFoundError as e:
            logger.warning(f"⚠️ {e}")
            logger.warning("💡 Приложение запустится без LLM. Проверьте путь к модели.")
    else:
        logger.warning("⚠️ LLM отключена — режим быстрой разработки")
    
    logger.info("✅ Приложение готово к работе!")
    yield
    # 🛑 Shutdown
    logger.info("🛑 Приложение завершает работу...")
    await llm_service.shutdown()


# 🎯 Создание приложения
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="...",
    version="0.1.0",
    lifespan=lifespan,
    debug=True,                    # ← Добавь эту строку
    docs_url="/docs",
    redoc_url="/redoc"
)

# 🌐 CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📦 Подключение роутеров
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])


# 🔍 Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Проверка работоспособности приложения"""
    return {
        "status": "ok",
        "database": "connected",
        "llm_loaded": llm_service.is_initialized
    }


# 🏠 Root endpoint
@app.get("/")
async def root():
    """Информация об API"""
    return {
        "message": "LLM Document Quality Checker API",
        "docs": "/docs",
        "health": "/health"
    }


# ❌ Обработчик 404 для несуществующих эндпоинтов
@app.exception_handler(404)
async def custom_404_handler(request, exc):
    """Кастомный ответ для 404"""
    return JSONResponse(
        status_code=404,
        content={"detail": f"Endpoint '{request.url.path}' not found"}
    )