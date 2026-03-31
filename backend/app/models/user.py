import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False
    )
    
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    username = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    
    hashed_password = Column(
        String(255),
        nullable=False
    )
    
    is_active = Column(
        Boolean,
        default=True
    )
    is_verified = Column(
        Boolean,
        default=False
    )
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now()
    )
    
    def to_dict(self, exclude_password: bool = True) -> dict:
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
        return f"<User(id={self.id}, username='{self.username}')>"