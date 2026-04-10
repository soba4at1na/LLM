import os
import logging
import asyncio
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
model_init_task: asyncio.Task | None = None

DB_BOOTSTRAP_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS purpose VARCHAR(20) DEFAULT 'check'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_hash VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_documents_text_hash ON documents(text_hash)",
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGSERIAL PRIMARY KEY,
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(64) NOT NULL,
        resource_type VARCHAR(64),
        resource_id VARCHAR(128),
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ip_address VARCHAR(64),
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_threads (
        id BIGSERIAL PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL DEFAULT 'Новый чат',
        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id BIGSERIAL PRIMARY KEY,
        thread_id BIGINT REFERENCES chat_threads(id) ON DELETE SET NULL,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL DEFAULT '',
        context_used BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS thread_id BIGINT REFERENCES chat_threads(id) ON DELETE SET NULL",
    "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS context_used BOOLEAN NOT NULL DEFAULT FALSE",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_init_task
    logger.info("Starting LLM Document Quality Checker")

    async with engine.begin() as conn:
        for statement in DB_BOOTSTRAP_STATEMENTS:
            await conn.exec_driver_sql(statement)
        logger.info("Database connection is ready and schema bootstrap is applied")

    if os.getenv("DISABLE_LLM", "false").lower() != "true":
        async def _init_model_background():
            try:
                logger.info("Initializing model in background")
                await llm_service.initialize()
                logger.info("Model initialized")
            except FileNotFoundError as e:
                logger.warning("Model file is missing: %s", e)
            except Exception as e:
                logger.error("Model initialization failed: %s", e)

        model_init_task = asyncio.create_task(_init_model_background())
    else:
        logger.warning("LLM is disabled, running in mock mode")

    logger.info("Application is ready")
    yield
    logger.info("Shutting down application")
    if model_init_task and not model_init_task.done():
        model_init_task.cancel()
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
