# backend/app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# 🎯 Base для моделей
Base = declarative_base()

# 🔗 Создание асинхронного движка
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # True для отладки SQL-запросов
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600
)

# 🔄 Фабрика сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncSession:
    """
    Dependency для получения сессии БД в эндпоинтах.
    
    Usage:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Инициализация БД: создание таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)