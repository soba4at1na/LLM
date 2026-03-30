# backend/app/utils/auth.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# 🔐 Контекст для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# === Пароли ===

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хэширование пароля"""
    return pwd_context.hash(password)


# === JWT Tokens ===

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Создание JWT access token
    
    Args:
        data: Данные для кодирования (обычно {"sub": user_id})
        expires_delta: Время жизни токена
    """
    to_encode = data.copy()
    
    # ⏰ Срок действия
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    # 🔐 Подпись
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Декодирование JWT token
    
    Returns:
        dict с данными или None если токен невалиден
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def get_token_subject(token: str) -> Optional[str]:
    """Получение user_id из токена"""
    payload = decode_token(token)
    if payload:
        return payload.get("sub")
    return None


# === Dependencies для FastAPI ===

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency для получения текущего пользователя из JWT
    
    Raises:
        HTTPException 401: Если токен невалиден или пользователь не найден
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 🔍 Декодируем токен
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    # 📋 Извлекаем user_id
    user_id: Optional[str] = payload.get("sub")
    token_type: Optional[str] = payload.get("type")
    
    if user_id is None or token_type != "access":
        raise credentials_exception
    
    # 🗄️ Ищем пользователя в БД
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency для проверки, что пользователь активен"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Аккаунт деактивирован"
        )
    return current_user