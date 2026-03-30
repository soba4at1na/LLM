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
    
    # 🔑 Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False
    )
    
    # 📧 Уникальные идентификаторы
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Email пользователя"
    )
    username = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Уникальное имя пользователя"
    )
    
    # 🔐 Безопасность
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Хэш пароля (bcrypt)"
    )
    
    # 📊 Статусы
    is_active = Column(
        Boolean,
        default=True,
        comment="Активен ли аккаунт"
    )
    is_verified = Column(
        Boolean,
        default=False,
        comment="Подтверждён ли email"
    )
    
    # ⏰ Временные метки
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Дата создания"
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        comment="Дата последнего обновления"
    )
    
    # 🎯 Pydantic-like методы для сериализации
    def to_dict(self, exclude_password: bool = True) -> dict:
        """Конвертация в словарь"""
        data = {
            "id": str(self.id),
            "email": self.email,
            "username": self.username,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if not exclude_password:
            data["hashed_password"] = self.hashed_password
        return data
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"