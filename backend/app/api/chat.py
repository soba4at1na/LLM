# backend/app/api/chat.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.llm_service import llm_service
from app.api.auth import get_current_active_user
from app.models.user import User

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024


class ChatResponse(BaseModel):
    response: str
    usage: Optional[dict] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user)
):
    if not llm_service.is_initialized:
        # Mock ответ, если модель не загружена
        return ChatResponse(
            response=f"Получил сообщение: «{request.message}»\n\n(Модель сейчас не загружена — это тестовый ответ)",
            usage={"prompt_tokens": len(request.message), "completion_tokens": 60}
        )

    try:
        prompt = f"""<|im_start|>system
Ты полезный ассистент для анализа технической документации. Отвечай кратко и по делу.<|im_end|>
<|im_start|>user
{request.message}<|im_end|>
<|im_start|>assistant
"""

        result = await llm_service.generate(
            prompt=prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        return ChatResponse(
            response=result.get("content", "Нет ответа"),
            usage=result.get("usage")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))