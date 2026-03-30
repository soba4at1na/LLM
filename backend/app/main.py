from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path   # ← Добавили этот импорт!

from app.config import settings
from app.core.llm_service import llm_service

# Роутеры
from app.api.routers.documents import router as documents_router
from app.api.routers.analysis import router as analysis_router
from app.api.routers.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск LLM Document Quality Checker...")
    await llm_service.initialize()
    print("✅ Модель успешно загружена!")
    print("✅ Приложение готово к работе!")
    yield
    print("🛑 Приложение завершает работу...")


app = FastAPI(
    title="Document Quality Checker",
    description="Локальный инструмент проверки качества технической документации",
    version="0.3.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])


@app.get("/")
async def root():
    return {
        "message": "Document Quality Checker API работает",
        "model": Path(settings.MODEL_PATH).name,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": llm_service._llm is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)