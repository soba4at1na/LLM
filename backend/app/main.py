import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.llm_service import llm_service

from app.api import auth
from app.api import analyze
from app.api import chat
from app.api import documents
from app.api import admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting LLM Document Quality Checker")

    async with engine.begin() as conn:
        logger.info("Database connection is ready")

    if os.getenv("DISABLE_LLM", "false").lower() != "true":
        try:
            logger.info("Initializing model")
            await llm_service.initialize()
            logger.info("Model initialized")
        except FileNotFoundError as e:
            logger.warning("Model file is missing: %s", e)
    else:
        logger.warning("LLM is disabled, running in mock mode")

    logger.info("Application is ready")
    yield
    logger.info("Shutting down application")
    await llm_service.shutdown()


app = FastAPI(
    title="LLM Document Quality Checker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_parsed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "llm_loaded": llm_service.is_initialized}

@app.get("/")
async def root():
    return {"message": "LLM Document Quality Checker API"}
