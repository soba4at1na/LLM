# backend/app/models/user.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    """Модель пользователя"""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False
    )

    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        """Преобразование в словарь для Pydantic"""
        return {
            "id": str(self.id),           # ← Важно: преобразуем UUID в строку
            "email": self.email,
            "username": self.username,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
        }


# ====================== Pydantic Response Model ======================
from pydantic import BaseModel


class UserResponse(BaseModel):
    """Ответ API с данными пользователя"""
    id: str
    email: str
    username: str
    is_active: bool

    class Config:
        from_attributes = True   # Позволяет работать с SQLAlchemy объектами