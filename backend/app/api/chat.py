import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm_service import llm_service
from app.models.chat_record import ChatMessageRecord, ChatThreadRecord
from app.models.user import User
from app.services.audit_service import log_event
from app.services.retrieval_service import retrieval_service
from app.utils.auth import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    chat_id: Optional[int] = Field(default=None, ge=1)
    temperature: Optional[float] = Field(default=0.35, ge=0.0, le=1.5)
    max_tokens: Optional[int] = Field(default=768, ge=64, le=4096)


class ChatResponse(BaseModel):
    chat_id: int
    response: str
    usage: Optional[dict] = None
    context_used: bool = False


class ChatHistoryItem(BaseModel):
    id: int
    role: str
    content: str
    context_used: bool = False
    created_at: str


class ChatThreadItem(BaseModel):
    id: int
    title: str
    message_count: int
    created_at: str
    updated_at: str
    last_message_at: Optional[str] = None


class CreateChatRequest(BaseModel):
    title: str = Field(default="Новый чат", min_length=1, max_length=120)


class RenameChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


def _looks_like_smalltalk(message: str) -> bool:
    text = (message or "").strip().lower()
    if len(text) <= 6:
        return True
    markers = [
        "привет",
        "здравств",
        "как дела",
        "добрый день",
        "добрый вечер",
        "пока",
        "спасибо",
        "ку",
    ]
    return any(marker in text for marker in markers)


async def _get_or_create_chat_thread(db: AsyncSession, user_id, chat_id: Optional[int], first_message: str) -> ChatThreadRecord:
    if chat_id is not None:
        thread = await db.scalar(
            select(ChatThreadRecord).where(
                ChatThreadRecord.id == chat_id,
                ChatThreadRecord.user_id == user_id,
                ChatThreadRecord.is_deleted.is_(False),
            )
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Чат не найден")
        return thread

    title = first_message.strip().splitlines()[0][:60] or "Новый чат"
    thread = ChatThreadRecord(
        user_id=user_id,
        title=title,
        is_deleted=False,
        updated_at=datetime.utcnow(),
    )
    db.add(thread)
    await db.flush()
    return thread


async def _load_recent_history_block(
    db: AsyncSession,
    *,
    user_id,
    thread_id: int,
    limit_messages: int = 8,
    max_chars: int = 1800,
) -> str:
    rows = (
        await db.execute(
            select(ChatMessageRecord.role, ChatMessageRecord.content)
            .where(
                ChatMessageRecord.user_id == user_id,
                ChatMessageRecord.thread_id == thread_id,
            )
            .order_by(desc(ChatMessageRecord.id))
            .limit(limit_messages)
        )
    ).all()
    if not rows:
        return ""

    ordered = list(reversed(rows))
    lines: List[str] = []
    chars_used = 0
    for role, content in ordered:
        role_label = "Пользователь" if str(role) == "user" else "Ассистент"
        chunk = f"{role_label}: {str(content).strip()}"
        if not chunk.strip():
            continue
        if chars_used + len(chunk) > max_chars:
            break
        lines.append(chunk)
        chars_used += len(chunk)
    return "\n".join(lines)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    thread = await _get_or_create_chat_thread(db, current_user.id, request.chat_id, request.message)

    db.add(
        ChatMessageRecord(
            thread_id=thread.id,
            user_id=current_user.id,
            role="user",
            content=request.message,
            context_used=False,
        )
    )
    await db.flush()

    use_document_context = not _looks_like_smalltalk(request.message) and len(request.message.strip()) >= 12
    chunks = []
    context_block = ""
    if use_document_context:
        chunks = await retrieval_service.find_relevant_chunks(
            db,
            owner_id=current_user.id,
            query=request.message,
            top_k=3,
            min_score=0.25,
        )
        context_block = retrieval_service.build_context(chunks, max_chars=2200)
    has_context = bool(context_block.strip())
    history_block = await _load_recent_history_block(
        db,
        user_id=current_user.id,
        thread_id=thread.id,
    )

    context_section = ""
    if has_context:
        context_section = f"\nРелевантный контекст из документов пользователя:\n{context_block}\n"

    if not llm_service.is_initialized:
        context_hint = ""
        if has_context:
            context_hint = "\n\nНашел релевантный контекст из ваших документов:\n" + context_block[:1500]
        mock_response = (
            f"Получил сообщение: «{request.message}»\n\n"
            f"(Модель сейчас не загружена — это тестовый ответ){context_hint}"
        )
        db.add(
            ChatMessageRecord(
                thread_id=thread.id,
                user_id=current_user.id,
                role="assistant",
                content=mock_response,
                context_used=has_context,
            )
        )
        thread.updated_at = datetime.utcnow()
        await log_event(
            db,
            action="chat_request",
            user_id=current_user.id,
            resource_type="chat",
            resource_id=str(thread.id),
            metadata={
                "llm_loaded": False,
                "message_length": len(request.message),
                "retrieved_chunks": len(chunks),
            },
            ip_address=http_request.client.host if http_request and http_request.client else None,
        )
        await db.commit()
        return ChatResponse(
            chat_id=thread.id,
            response=mock_response,
            context_used=has_context,
            usage={"prompt_tokens": len(request.message), "completion_tokens": 60},
        )

    try:
        history_section = ""
        if history_block:
            history_section = f"\nКраткая история текущего чата:\n{history_block}\n"

        prompt = f"""<|im_start|>system
Ты универсальный русскоязычный AI-ассистент.
Отвечай строго на русском языке.
Отвечай полезно, по делу и последовательно с учетом истории диалога.
Не упоминай документы, если их релевантный контекст не был передан.
Не говори про отсутствие контекста, если пользователь спрашивает обычный бытовой вопрос.
Будь точным и не выдумывай факты.<|im_end|>
<|im_start|>user
Вопрос пользователя:
{request.message}
{history_section}{context_section}<|im_end|>
<|im_start|>assistant
"""

        result = await llm_service.generate_async(
            prompt=prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        assistant_response = result.get("content", "Нет ответа")
        db.add(
            ChatMessageRecord(
                thread_id=thread.id,
                user_id=current_user.id,
                role="assistant",
                content=assistant_response,
                context_used=has_context,
            )
        )
        thread.updated_at = datetime.utcnow()

        await log_event(
            db,
            action="chat_request",
            user_id=current_user.id,
            resource_type="chat",
            resource_id=str(thread.id),
            metadata={
                "llm_loaded": True,
                "message_length": len(request.message),
                "retrieved_chunks": len(chunks),
            },
            ip_address=http_request.client.host if http_request and http_request.client else None,
        )
        await db.commit()
        return ChatResponse(
            chat_id=thread.id,
            response=assistant_response,
            context_used=has_context,
            usage=result.get("usage"),
        )

    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during chat request")
        raise HTTPException(status_code=500, detail="Ошибка сервиса чата")


@router.get("/chat/history", response_model=List[ChatHistoryItem])
async def get_chat_history(
    chat_id: int = Query(..., ge=1),
    limit: int = Query(default=120, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await db.scalar(
        select(ChatThreadRecord).where(
            ChatThreadRecord.id == chat_id,
            ChatThreadRecord.user_id == current_user.id,
            ChatThreadRecord.is_deleted.is_(False),
        )
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Чат не найден")

    rows = (
        await db.execute(
            select(ChatMessageRecord)
            .where(
                ChatMessageRecord.user_id == current_user.id,
                ChatMessageRecord.thread_id == chat_id,
            )
            .order_by(desc(ChatMessageRecord.id))
            .limit(limit)
        )
    ).scalars().all()
    rows = list(reversed(rows))

    return [
        ChatHistoryItem(
            id=item.id,
            role=item.role,
            content=item.content,
            context_used=bool(getattr(item, "context_used", False)),
            created_at=item.created_at.isoformat(),
        )
        for item in rows
    ]


@router.get("/chats", response_model=List[ChatThreadItem])
async def list_chats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(
                ChatThreadRecord.id,
                ChatThreadRecord.title,
                ChatThreadRecord.created_at,
                ChatThreadRecord.updated_at,
                func.count(ChatMessageRecord.id).label("message_count"),
                func.max(ChatMessageRecord.created_at).label("last_message_at"),
            )
            .outerjoin(ChatMessageRecord, ChatMessageRecord.thread_id == ChatThreadRecord.id)
            .where(
                ChatThreadRecord.user_id == current_user.id,
                ChatThreadRecord.is_deleted.is_(False),
            )
            .group_by(
                ChatThreadRecord.id,
                ChatThreadRecord.title,
                ChatThreadRecord.created_at,
                ChatThreadRecord.updated_at,
            )
            .order_by(desc(ChatThreadRecord.updated_at), desc(ChatThreadRecord.id))
        )
    ).all()
    return [
        ChatThreadItem(
            id=chat_id,
            title=title,
            message_count=int(message_count or 0),
            created_at=created_at.isoformat(),
            updated_at=updated_at.isoformat(),
            last_message_at=last_message_at.isoformat() if last_message_at else None,
        )
        for chat_id, title, created_at, updated_at, message_count, last_message_at in rows
    ]


@router.post("/chats", response_model=ChatThreadItem)
async def create_chat(
    payload: CreateChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    title = payload.title.strip() or "Новый чат"
    thread = ChatThreadRecord(
        user_id=current_user.id,
        title=title[:120],
        is_deleted=False,
        updated_at=datetime.utcnow(),
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return ChatThreadItem(
        id=thread.id,
        title=thread.title,
        message_count=0,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
        last_message_at=None,
    )


@router.patch("/chats/{chat_id}")
async def rename_chat(
    chat_id: int,
    payload: RenameChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await db.scalar(
        select(ChatThreadRecord).where(
            ChatThreadRecord.id == chat_id,
            ChatThreadRecord.user_id == current_user.id,
            ChatThreadRecord.is_deleted.is_(False),
        )
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Чат не найден")

    thread.title = payload.title.strip()[:120] or "Новый чат"
    thread.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "chat_id": thread.id, "title": thread.title}


@router.delete("/chats/{chat_id}")
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await db.scalar(
        select(ChatThreadRecord).where(
            ChatThreadRecord.id == chat_id,
            ChatThreadRecord.user_id == current_user.id,
            ChatThreadRecord.is_deleted.is_(False),
        )
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Чат не найден")

    thread.is_deleted = True
    thread.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True}
