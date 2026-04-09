import json
import re
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm_service import llm_service
from app.models.analysis_record import AnalysisIssueRecord, AnalysisRecommendationRecord, AnalysisRun
from app.models.document_record import DocumentChunk, DocumentRecord
from app.models.user import User
from app.services.audit_service import log_event
from app.utils.auth import get_current_active_user
from app.utils.text_processor import build_chunk_rows, count_words

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="Текст документа для анализа")
    document_id: Optional[int] = Field(default=None, description="ID ранее загруженного документа")
    filename: Optional[str] = Field(default="inline_text.txt", max_length=255)

    @model_validator(mode="after")
    def validate_payload(self) -> "AnalyzeRequest":
        has_text = bool(self.text and self.text.strip())
        has_document_id = self.document_id is not None
        if not has_text and not has_document_id:
            raise ValueError("Передайте text или document_id")
        return self


class AnalyzeResponse(BaseModel):
    overall_score: int
    readability_score: int
    grammar_score: int
    structure_score: int
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    issue_details: List[dict] = Field(default_factory=list)
    summary: str
    document_id: int
    analysis_id: int


class AnalysisHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    analysis_id: int
    document_id: int
    filename: str
    user_id: str | None = None
    user_email: str | None = None
    overall_score: int
    readability_score: int
    grammar_score: int
    structure_score: int
    summary: str
    issues: List[str]
    recommendations: List[str]
    run_mode: str = Field(alias="model_mode")
    processing_ms: Optional[int] = None
    created_at: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    start = time.perf_counter()

    document = await _resolve_or_create_document(request, current_user, db)
    text = document.extracted_text
    if len(text) < 50:
        raise HTTPException(status_code=400, detail="Текст слишком короткий для анализа")

    if llm_service.is_initialized:
        result = _analyze_with_llm(text)
        model_mode = "llm"
    else:
        result = get_mock_analysis(text)
        model_mode = "mock"

    processing_ms = int((time.perf_counter() - start) * 1000)
    run = AnalysisRun(
        document_id=document.id,
        user_id=current_user.id,
        overall_score=result.overall_score,
        readability_score=result.readability_score,
        grammar_score=result.grammar_score,
        structure_score=result.structure_score,
        summary=result.summary,
        raw_response=result.model_dump(),
        model_mode=model_mode,
        processing_ms=processing_ms,
    )
    db.add(run)
    await db.flush()

    for idx, issue in enumerate(result.issues):
        db.add(AnalysisIssueRecord(run_id=run.id, issue_index=idx, text=issue))
    for idx, rec in enumerate(result.recommendations):
        db.add(AnalysisRecommendationRecord(run_id=run.id, recommendation_index=idx, text=rec))

    await log_event(
        db,
        action="analysis_run",
        user_id=current_user.id,
        resource_type="analysis_run",
        resource_id=str(run.id),
        metadata={
            "document_id": document.id,
            "scores": {
                "overall": result.overall_score,
                "readability": result.readability_score,
                "grammar": result.grammar_score,
                "structure": result.structure_score,
            },
            "mode": model_mode,
        },
        ip_address=http_request.client.host if http_request and http_request.client else None,
    )
    await db.commit()

    payload = result.model_dump()
    payload["document_id"] = document.id
    payload["analysis_id"] = run.id
    return AnalyzeResponse(**payload)


@router.get("/analysis/history", response_model=List[AnalysisHistoryItem])
async def get_analysis_history(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    document_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(AnalysisRun, DocumentRecord.filename, User.email)
        .join(DocumentRecord, DocumentRecord.id == AnalysisRun.document_id)
        .join(User, User.id == AnalysisRun.user_id)
        .order_by(desc(AnalysisRun.id))
        .limit(limit)
        .offset(offset)
    )
    if not current_user.is_admin:
        query = query.where(AnalysisRun.user_id == current_user.id)
    if document_id is not None:
        query = query.where(AnalysisRun.document_id == document_id)

    rows = (await db.execute(query)).all()
    if not rows:
        return []

    run_ids = [run.id for run, _, _ in rows]
    issues_rows = (
        await db.execute(
            select(AnalysisIssueRecord.run_id, AnalysisIssueRecord.text)
            .where(AnalysisIssueRecord.run_id.in_(run_ids))
            .order_by(AnalysisIssueRecord.run_id, AnalysisIssueRecord.issue_index)
        )
    ).all()
    rec_rows = (
        await db.execute(
            select(AnalysisRecommendationRecord.run_id, AnalysisRecommendationRecord.text)
            .where(AnalysisRecommendationRecord.run_id.in_(run_ids))
            .order_by(
                AnalysisRecommendationRecord.run_id,
                AnalysisRecommendationRecord.recommendation_index,
            )
        )
    ).all()

    issues_map: dict[int, List[str]] = {}
    for run_id, issue_text in issues_rows:
        issues_map.setdefault(int(run_id), []).append(str(issue_text))

    rec_map: dict[int, List[str]] = {}
    for run_id, rec_text in rec_rows:
        rec_map.setdefault(int(run_id), []).append(str(rec_text))

    return [
        AnalysisHistoryItem(
            analysis_id=run.id,
            document_id=run.document_id,
            filename=str(filename),
            user_id=str(run.user_id) if current_user.is_admin else None,
            user_email=str(user_email) if current_user.is_admin else None,
            overall_score=run.overall_score,
            readability_score=run.readability_score,
            grammar_score=run.grammar_score,
            structure_score=run.structure_score,
            summary=run.summary,
            issues=issues_map.get(int(run.id), []),
            recommendations=rec_map.get(int(run.id), []),
            run_mode=run.model_mode,
            processing_ms=run.processing_ms,
            created_at=run.created_at.isoformat(),
        )
        for run, filename, user_email in rows
    ]


async def _resolve_or_create_document(request: AnalyzeRequest, user: User, db: AsyncSession) -> DocumentRecord:
    if request.document_id is not None:
        existing = await db.scalar(
            select(DocumentRecord).where(
                DocumentRecord.id == request.document_id,
                DocumentRecord.owner_id == user.id,
            )
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Документ не найден")
        return existing

    text = (request.text or "").strip()
    filename = (request.filename or "inline_text.txt").strip() or "inline_text.txt"

    document = DocumentRecord(
        owner_id=user.id,
        filename=filename,
        mime_type="text/plain",
        extension=".txt",
        source_type="text",
        purpose="check",
        file_size=len(text.encode("utf-8")),
        file_content=text.encode("utf-8"),
        extracted_text=text,
        word_count=count_words(text),
        status="processed",
    )
    db.add(document)
    await db.flush()

    for row in build_chunk_rows(text):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=int(row["chunk_index"]),
                content=str(row["content"]),
                char_count=int(row["char_count"]),
                word_count=int(row["word_count"]),
                sentence_count=int(row["sentence_count"]),
            )
        )
    return document


def _analyze_with_llm(text: str) -> AnalyzeResponse:
    prompt = f"""Проанализируй следующий документ и оцени его качество по шкале от 0 до 100.

Текст документа:
---
{text[:3000]}
---

Верни ответ ТОЛЬКО в формате JSON:
{{
    "overall_score": 85,
    "readability_score": 80,
    "grammar_score": 90,
    "structure_score": 85,
    "issues": ["Проблема 1", "Проблема 2"],
    "recommendations": ["Рекомендация 1", "Рекомендация 2"],
    "summary": "Краткое резюме анализа"
}}
"""
    result = llm_service.generate(prompt, max_tokens=700, temperature=0.3)
    if result.get("error"):
        return get_mock_analysis(text)

    content = result.get("content", "")
    json_start = content.find("{")
    json_end = content.rfind("}")
    if json_start == -1 or json_end == -1 or json_end <= json_start:
        return get_mock_analysis(text)

    try:
        parsed = json.loads(content[json_start:json_end + 1])
        return AnalyzeResponse(
            overall_score=int(parsed.get("overall_score", 0)),
            readability_score=int(parsed.get("readability_score", 0)),
            grammar_score=int(parsed.get("grammar_score", 0)),
            structure_score=int(parsed.get("structure_score", 0)),
            issues=[str(i) for i in parsed.get("issues", [])],
            recommendations=[str(r) for r in parsed.get("recommendations", [])],
            issue_details=[
                {
                    "fragment": str(x.get("fragment", "")),
                    "suggestion": str(x.get("suggestion", "")),
                    "reason": str(x.get("reason", "")),
                }
                for x in parsed.get("issue_details", [])
                if isinstance(x, dict)
            ],
            summary=str(parsed.get("summary", "")),
            document_id=0,
            analysis_id=0,
        )
    except Exception:
        return get_mock_analysis(text)


def get_mock_analysis(text: str) -> AnalyzeResponse:
    word_count = len(text.split())
    sentence_count = len(re.findall(r"[.!?]", text))
    avg_sentence_length = word_count / max(sentence_count, 1)

    readability = min(100, max(0, 100 - abs(avg_sentence_length - 20) * 3))
    grammar = min(100, max(0, 95 - text.count("  ") * 5))
    structure = min(100, max(0, 80 + (text.count("\n") > 5) * 20))
    overall = int((readability + grammar + structure) / 3)

    issues: List[str] = []
    recommendations: List[str] = []
    issue_details: List[dict] = []

    if avg_sentence_length > 25:
        issues.append(f"Предложения слишком длинные (в среднем {avg_sentence_length:.0f} слов)")
        recommendations.append("Разбейте длинные предложения на более короткие")
        longest_sentence = max(re.split(r"(?<=[.!?])\s+", text), key=len, default="")
        if longest_sentence:
            issue_details.append(
                {
                    "fragment": longest_sentence[:180],
                    "suggestion": "Разделите это предложение на 2-3 более коротких.",
                    "reason": "Слишком длинное предложение ухудшает читаемость.",
                }
            )

    if text.count("  ") > 0:
        issues.append("Найдены двойные пробелы")
        recommendations.append("Удалите лишние пробелы")
        issue_details.append(
            {
                "fragment": "  ",
                "suggestion": "Замените двойные пробелы на один.",
                "reason": "Лишние пробелы считаются ошибкой форматирования.",
            }
        )

    if word_count < 100:
        issues.append("Текст слишком короткий для полноценного анализа")
        recommendations.append("Добавьте больше содержания")
        issue_details.append(
            {
                "fragment": text[:120],
                "suggestion": "Добавьте больше фактов, примеров и пояснений.",
                "reason": "Короткий текст не позволяет выполнить полноценную проверку качества.",
            }
        )

    if not issues:
        issues.append("Явных проблем не найдено")
    if not recommendations:
        recommendations.append("Текст соответствует базовым требованиям качества")

    return AnalyzeResponse(
        overall_score=overall,
        readability_score=int(readability),
        grammar_score=int(grammar),
        structure_score=int(structure),
        issues=issues,
        recommendations=recommendations,
        issue_details=issue_details,
        summary=f"Проанализировано {word_count} слов. Общее качество: {'хорошее' if overall > 70 else 'требует улучшений'}.",
        document_id=0,
        analysis_id=0,
    )
