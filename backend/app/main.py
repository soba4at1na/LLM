import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.core.llm_service import llm_service
from app.api import auth
from app.api import auth, analyze  # ← добавь analyze


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting LLM Document Quality Checker...")
    
    async with engine.begin() as conn:
        logger.info("Database connected")
    
    if os.getenv("DISABLE_LLM", "false").lower() != "true":
        try:
            logger.info(f"Loading model: {Path(settings.MODEL_PATH).name} ...")
            await llm_service.initialize()
            logger.info("Model loaded successfully!")
        except FileNotFoundError as e:
            logger.warning(f"Model not found: {e}")
    else:
        logger.warning("LLM disabled - fast development mode")
    
    logger.info("Application ready!")
    yield
    logger.info("Shutting down...")
    await llm_service.shutdown()


app = FastAPI(
    title="LLM Document Quality Checker",
    description="Corporate tool for technical documentation analysis",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])  # ← добавь эту строку

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "ok",
        "database": "connected",
        "llm_loaded": llm_service.is_initialized
    }


@app.get("/")
async def root():
    return {
        "message": "LLM Document Quality Checker API",
        "docs": "/docs",
        "health": "/health"
    }