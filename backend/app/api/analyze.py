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
from app.utils.text_processor import build_chunk_rows, count_words, sha256_text

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: Optional[str] = Field(default=None, max_length=200000, description="Текст документа для анализа")
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
    model_mode: str = "mock"
    processing_ms: Optional[int] = None
    analyzed_at: Optional[str] = None
    cached: bool = False
    cached_from_analysis_id: Optional[int] = None


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
    issue_details: List[dict] = Field(default_factory=list)
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
    if not document.text_hash and text:
        document.text_hash = sha256_text(text)
        await db.flush()

    cached_payload = await _try_get_cached_analysis_payload(document, current_user, db)
    if cached_payload is not None:
        await log_event(
            db,
            action="analysis_cache_hit",
            user_id=current_user.id,
            resource_type="analysis_run",
            resource_id=str(cached_payload["analysis_id"]),
            metadata={
                "document_id": document.id,
                "text_hash": document.text_hash,
                "source_analysis_id": cached_payload["analysis_id"],
            },
            ip_address=http_request.client.host if http_request and http_request.client else None,
        )
        await db.commit()
        return AnalyzeResponse(**cached_payload)

    if llm_service.is_initialized:
        result = await _analyze_with_llm(text)
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
    payload["model_mode"] = model_mode
    payload["processing_ms"] = processing_ms
    payload["analyzed_at"] = run.created_at.isoformat() if run.created_at else None
    payload["cached"] = False
    payload["cached_from_analysis_id"] = None
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
            issue_details=_extract_issue_details(run.raw_response),
            run_mode=run.model_mode,
            processing_ms=run.processing_ms,
            created_at=run.created_at.isoformat(),
        )
        for run, filename, user_email in rows
    ]


async def _try_get_cached_analysis_payload(
    document: DocumentRecord,
    user: User,
    db: AsyncSession,
) -> Optional[dict]:
    if not document.text_hash:
        return None

    cached_row = (
        await db.execute(
            select(AnalysisRun)
            .join(DocumentRecord, DocumentRecord.id == AnalysisRun.document_id)
            .where(
                AnalysisRun.user_id == user.id,
                DocumentRecord.owner_id == user.id,
                DocumentRecord.text_hash == document.text_hash,
            )
            .order_by(desc(AnalysisRun.id))
            .limit(1)
        )
    ).first()
    if not cached_row:
        return None

    (run,) = cached_row
    issues = (
        await db.execute(
            select(AnalysisIssueRecord.text)
            .where(AnalysisIssueRecord.run_id == run.id)
            .order_by(AnalysisIssueRecord.issue_index)
        )
    ).scalars().all()
    recommendations = (
        await db.execute(
            select(AnalysisRecommendationRecord.text)
            .where(AnalysisRecommendationRecord.run_id == run.id)
            .order_by(AnalysisRecommendationRecord.recommendation_index)
        )
    ).scalars().all()

    return {
        "overall_score": run.overall_score,
        "readability_score": run.readability_score,
        "grammar_score": run.grammar_score,
        "structure_score": run.structure_score,
        "issues": [str(x) for x in issues],
        "recommendations": [str(x) for x in recommendations],
        "issue_details": _extract_issue_details(run.raw_response),
        "summary": run.summary,
        "document_id": document.id,
        "analysis_id": run.id,
        "model_mode": run.model_mode,
        "processing_ms": 0,
        "analyzed_at": run.created_at.isoformat() if run.created_at else None,
        "cached": True,
        "cached_from_analysis_id": run.id,
    }


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
    text_hash = sha256_text(text)
    existing_by_hash = await db.scalar(
        select(DocumentRecord).where(
            DocumentRecord.owner_id == user.id,
            DocumentRecord.purpose == "check",
            DocumentRecord.source_type == "text",
            DocumentRecord.text_hash == text_hash,
        ).order_by(desc(DocumentRecord.id))
    )
    if existing_by_hash:
        return existing_by_hash

    document = DocumentRecord(
        owner_id=user.id,
        filename=filename,
        mime_type="text/plain",
        extension=".txt",
        source_type="text",
        purpose="check",
        file_size=len(text.encode("utf-8")),
        file_hash=None,
        file_content=text.encode("utf-8"),
        extracted_text=text,
        text_hash=text_hash,
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


async def _analyze_with_llm(text: str) -> AnalyzeResponse:
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
    "issues": ["Конкретная проблема в тексте с пояснением", "Еще одна конкретная проблема"],
    "recommendations": ["Конкретная правка, что именно поменять", "Вторая конкретная правка"],
    "issue_details": [
      {{"fragment":"точный фрагмент из текста","suggestion":"как переписать","reason":"почему это лучше","confidence":"high"}},
      {{"fragment":"еще один точный фрагмент","suggestion":"вариант правки","reason":"обоснование","confidence":"medium"}}
    ],
    "summary": "Краткое резюме анализа"
}}
"""
    result = await llm_service.generate_async(prompt, max_tokens=700, temperature=0.3)
    if result.get("error"):
        return get_mock_analysis(text)

    content = result.get("content", "")
    json_start = content.find("{")
    json_end = content.rfind("}")
    if json_start == -1 or json_end == -1 or json_end <= json_start:
        return get_mock_analysis(text)

    try:
        parsed = json.loads(content[json_start:json_end + 1])
        issue_details = _prepare_issue_details(
            text=text,
            issues=[str(i) for i in parsed.get("issues", [])],
            recommendations=[str(r) for r in parsed.get("recommendations", [])],
            raw_details=parsed.get("issue_details", []),
        )
        return AnalyzeResponse(
            overall_score=int(parsed.get("overall_score", 0)),
            readability_score=int(parsed.get("readability_score", 0)),
            grammar_score=int(parsed.get("grammar_score", 0)),
            structure_score=int(parsed.get("structure_score", 0)),
            issues=[str(i) for i in parsed.get("issues", [])],
            recommendations=[str(r) for r in parsed.get("recommendations", [])],
            issue_details=issue_details,
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
                    "confidence": "medium",
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
                "confidence": "high",
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
                "confidence": "medium",
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


def _extract_issue_details(raw_response: dict | None) -> List[dict]:
    if not isinstance(raw_response, dict):
        return []
    raw_details = raw_response.get("issue_details", [])
    if not isinstance(raw_details, list):
        return []
    out: List[dict] = []
    for item in raw_details:
        if not isinstance(item, dict):
            continue
        fragment = str(item.get("fragment", "")).strip()
        suggestion = str(item.get("suggestion", "")).strip()
        reason = str(item.get("reason", "")).strip()
        confidence_raw = str(item.get("confidence", "medium")).strip().lower()
        confidence = confidence_raw if confidence_raw in {"low", "medium", "high"} else "medium"
        if fragment and suggestion:
            out.append(
                {
                    "fragment": fragment,
                    "suggestion": suggestion,
                    "reason": reason,
                    "confidence": confidence,
                }
            )
    return out


def _prepare_issue_details(
    text: str,
    issues: List[str],
    recommendations: List[str],
    raw_details: list | None,
) -> List[dict]:
    details: List[dict] = []
    if isinstance(raw_details, list):
        for item in raw_details:
            if not isinstance(item, dict):
                continue
            fragment = str(item.get("fragment", "")).strip()
            suggestion = str(item.get("suggestion", "")).strip()
            reason = str(item.get("reason", "")).strip()
            confidence_raw = str(item.get("confidence", "medium")).strip().lower()
            confidence = confidence_raw if confidence_raw in {"low", "medium", "high"} else "medium"
            if fragment and suggestion:
                details.append(
                    {
                        "fragment": fragment,
                        "suggestion": suggestion,
                        "reason": reason,
                        "confidence": confidence,
                    }
                )

    if details:
        return details

    sentence_candidates = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
    for idx, issue_text in enumerate(issues):
        issue_l = issue_text.lower()
        recommendation = recommendations[idx] if idx < len(recommendations) else "Переформулируйте фрагмент понятнее."
        fragment = ""
        reason = issue_text

        if "двойн" in issue_l and "  " in text:
            fragment = "  "
        elif "длин" in issue_l and sentence_candidates:
            fragment = max(sentence_candidates, key=len)[:220]
        elif sentence_candidates:
            fragment = sentence_candidates[min(idx, len(sentence_candidates) - 1)][:220]

        if fragment:
            details.append(
                {
                    "fragment": fragment,
                    "suggestion": recommendation,
                    "reason": reason,
                    "confidence": "low",
                }
            )

    if not details and text.strip():
        fallback_fragment = text.strip()[:220]
        details.append(
            {
                "fragment": fallback_fragment,
                "suggestion": recommendations[0] if recommendations else "Уточните формулировки и добавьте конкретику.",
                "reason": issues[0] if issues else "Найдены потенциальные улучшения.",
                "confidence": "low",
            }
        )

    return details[:10]
