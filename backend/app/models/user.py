import uuid

from sqlalchemy import Boolean, Column, String, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


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
    is_admin = Column(
        Boolean,
        default=False
    )
    role = Column(
        String(32),
        nullable=False,
        default="user",
        server_default=text("'user'")
    )
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True
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
            "is_admin": self.is_admin,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if not exclude_password:
            data["hashed_password"] = self.hashed_password
        return data
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
