# backend/app/api/auth.py
from datetime import timedelta
from typing import Annotated, Optional  # ✅ Исправлено: добавлен Optional
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_active_user,
)

router = APIRouter()


# === Pydantic Schemas ===
from pydantic import BaseModel, Field, field_validator


class UserRegister(BaseModel):
    """Схема для регистрации"""
    email: str = Field(..., max_length=255)  # ✅ str вместо EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Валидация email через regex"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError('Неверный формат email')
        return v.lower()


class UserResponse(BaseModel):
    """Ответ с данными пользователя"""
    id: str
    email: str
    username: str
    is_active: bool
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT Token ответ"""
    access_token: str
    token_type: str = "bearer"


# === Endpoints ===

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """Регистрация нового пользователя"""
    # 🔍 Проверка на дубликаты
    email_query = select(User).where(User.email == user_data.email)
    username_query = select(User).where(User.username == user_data.username)
    
    existing_email = await db.scalar(email_query)
    existing_username = await db.scalar(username_query)
    
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Такое имя пользователя уже занято"
        )
    
    # 🔐 Создание пользователя
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        is_active=True,
        is_verified=False,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
):
    """Вход в систему — возвращает JWT access token"""
    # 🔍 Поиск пользователя по email или username
    query = select(User).where(
        (User.email == form_data.username) | (User.username == form_data.username)
    )
    user = await db.scalar(query)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email/username или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Аккаунт деактивирован"
        )
    
    # 🎫 Создание токена
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Получение данных текущего пользователя"""
    return current_user


@router.post("/logout")
async def logout():
    """Выход из системы (клиент должен удалить токен)"""
    return {"message": "Успешный выход"}