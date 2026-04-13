from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.exc import UnknownHashError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, field_validator

from app.core.database import get_db
from app.models.user import User
from app.services.audit_service import log_event
from app.utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_active_user,
)

router = APIRouter()


class UserRegister(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Неверный формат email')
        return v.lower()


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_active: bool
    is_admin: bool
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    try:
        if await db.scalar(select(User).where(User.email == user_data.email)):
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

        if await db.scalar(select(User).where(User.username == user_data.username)):
            raise HTTPException(status_code=400, detail="Такое имя пользователя уже занято")

        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_verified=False,
            is_admin=False,
            role="user",
        )

        db.add(new_user)
        await db.flush()
        await log_event(
            db,
            action="user_register",
            user_id=new_user.id,
            resource_type="user",
            resource_id=str(new_user.id),
            metadata={"email": new_user.email, "username": new_user.username},
            ip_address=request.client.host if request and request.client else None,
        )
        await db.commit()
        await db.refresh(new_user)

        # Явно преобразуем UUID в строку
        return {
            "id": str(new_user.id),
            "email": new_user.email,
            "username": new_user.username,
            "is_active": new_user.is_active,
            "is_admin": new_user.is_admin,
            "role": new_user.role or "user",
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка регистрации: {str(e)}")


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    user = await db.scalar(
        select(User).where(
            (User.email == form_data.username) | (User.username == form_data.username)
        )
    )

    is_password_ok = False
    if user:
        try:
            is_password_ok = verify_password(form_data.password, user.hashed_password)
        except UnknownHashError:
            is_password_ok = False

    if not user or not user.is_active or not is_password_ok:
        await log_event(
            db,
            action="user_login_failed",
            resource_type="user",
            resource_id=form_data.username,
            metadata={"username_or_email": form_data.username},
            ip_address=request.client.host if request and request.client else None,
        )
        await db.commit()
        raise HTTPException(
            status_code=401,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = func.now()
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": (user.role or "user")}
    )
    await log_event(
        db,
        action="user_login_success",
        user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        metadata={"username": user.username},
        ip_address=request.client.host if request and request.client else None,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Получение данных текущего пользователя"""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "role": current_user.role or "user",
    }


@router.post("/logout")
async def logout():
    return {"message": "Успешный выход из системы"}
