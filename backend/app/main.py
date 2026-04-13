import os
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.core.llm_service import llm_service
import app.models  # noqa: F401  # Ensure SQLAlchemy models are registered before create_all

from app.api import auth
from app.api import analyze
from app.api import chat
from app.api import documents
from app.api import admin
from app.api import knowledge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
model_init_task: asyncio.Task | None = None

DB_BOOTSTRAP_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'user'",
    "UPDATE users SET role = 'user' WHERE role IS NULL",
    "UPDATE users SET role = 'admin' WHERE is_admin IS TRUE AND role <> 'admin'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS purpose VARCHAR(20) DEFAULT 'check'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS confidentiality_level VARCHAR(20) DEFAULT 'confidential'",
    "UPDATE documents SET confidentiality_level = 'confidential' WHERE confidentiality_level IS NULL",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_hash VARCHAR(64)",
    "ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS policy_hash TEXT",
    "CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_documents_text_hash ON documents(text_hash)",
    "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
    "CREATE INDEX IF NOT EXISTS idx_documents_confidentiality_level ON documents(confidentiality_level)",
    """
    CREATE TABLE IF NOT EXISTS source_references (
        id BIGSERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        section VARCHAR(128),
        reference_code VARCHAR(128),
        url_or_local_path VARCHAR(1024),
        note TEXT,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS glossary_terms (
        id BIGSERIAL PRIMARY KEY,
        term VARCHAR(255) NOT NULL,
        normalized_term VARCHAR(255) NOT NULL,
        canonical_definition TEXT NOT NULL,
        allowed_variants JSONB NOT NULL DEFAULT '[]'::jsonb,
        forbidden_variants JSONB NOT NULL DEFAULT '[]'::jsonb,
        category VARCHAR(64),
        severity_default VARCHAR(16) NOT NULL DEFAULT 'medium',
        source_ref_id BIGINT REFERENCES source_references(id) ON DELETE SET NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rule_patterns (
        id BIGSERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        rule_type VARCHAR(32) NOT NULL DEFAULT 'regex',
        pattern TEXT NOT NULL,
        description TEXT,
        severity VARCHAR(16) NOT NULL DEFAULT 'medium',
        suggestion_template TEXT,
        source_ref_id BIGINT REFERENCES source_references(id) ON DELETE SET NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_references_active ON source_references(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_glossary_terms_term ON glossary_terms(term)",
    "CREATE INDEX IF NOT EXISTS idx_glossary_terms_normalized_term ON glossary_terms(normalized_term)",
    "CREATE INDEX IF NOT EXISTS idx_glossary_terms_active ON glossary_terms(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_glossary_terms_source_ref_id ON glossary_terms(source_ref_id)",
    "CREATE INDEX IF NOT EXISTS idx_rule_patterns_rule_type ON rule_patterns(rule_type)",
    "CREATE INDEX IF NOT EXISTS idx_rule_patterns_active ON rule_patterns(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_rule_patterns_source_ref_id ON rule_patterns(source_ref_id)",
    """
    CREATE TABLE IF NOT EXISTS knowledge_policy_snapshots (
        id BIGSERIAL PRIMARY KEY,
        label VARCHAR(255),
        policy_hash VARCHAR(64) NOT NULL,
        snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_by VARCHAR(64),
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_knowledge_policy_snapshots_hash ON knowledge_policy_snapshots(policy_hash)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_policy_snapshots_created_at ON knowledge_policy_snapshots(created_at DESC)",
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
        # Ensure base tables exist on first start even if init.sql was not applied
        await conn.run_sync(Base.metadata.create_all)
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
app.include_router(knowledge.router, prefix="/api", tags=["Knowledge"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "llm_loaded": llm_service.is_initialized}

@app.get("/")
async def root():
    return {"message": "LLM Document Quality Checker API"}
