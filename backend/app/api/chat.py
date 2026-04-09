from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm_service import llm_service
from app.models.user import User
from app.services.audit_service import log_event
from app.services.retrieval_service import retrieval_service
from app.utils.auth import get_current_active_user

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
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    chunks = await retrieval_service.find_relevant_chunks(
        db,
        owner_id=current_user.id,
        query=request.message,
        top_k=3,
    )
    context_block = retrieval_service.build_context(chunks)

    if not llm_service.is_initialized:
        context_hint = ""
        if context_block:
            context_hint = "\n\nНашел релевантный контекст из ваших документов:\n" + context_block[:1500]
        await log_event(
            db,
            action="chat_request",
            user_id=current_user.id,
            resource_type="chat",
            metadata={
                "llm_loaded": False,
                "message_length": len(request.message),
                "retrieved_chunks": len(chunks),
            },
            ip_address=http_request.client.host if http_request and http_request.client else None,
        )
        return ChatResponse(
            response=(
                f"Получил сообщение: «{request.message}»\n\n"
                f"(Модель сейчас не загружена — это тестовый ответ){context_hint}"
            ),
            usage={"prompt_tokens": len(request.message), "completion_tokens": 60}
        )

    try:
        prompt = f"""<|im_start|>system
Ты полезный ассистент для анализа технической документации. Отвечай кратко и по делу.
Если в контексте есть релевантные фрагменты, опирайся на них и ссылайся на document_id/file.
Если контекста недостаточно, честно это скажи.<|im_end|>
<|im_start|>user
Вопрос пользователя:
{request.message}

Контекст из базы документов:
{context_block if context_block else "Контекст не найден"}<|im_end|>
<|im_start|>assistant
"""

        result = llm_service.generate(
            prompt=prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        await log_event(
            db,
            action="chat_request",
            user_id=current_user.id,
            resource_type="chat",
            metadata={
                "llm_loaded": True,
                "message_length": len(request.message),
                "retrieved_chunks": len(chunks),
            },
            ip_address=http_request.client.host if http_request and http_request.client else None,
        )
        return ChatResponse(
            response=result.get("content", "Нет ответа"),
            usage=result.get("usage")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
