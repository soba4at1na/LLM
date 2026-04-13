import json
import re
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm_service import llm_service
from app.models.analysis_record import AnalysisIssueRecord, AnalysisRecommendationRecord, AnalysisRun
from app.models.document_record import DocumentChunk, DocumentRecord
from app.models.user import User
from app.services.audit_service import log_event
from app.services.rule_engine import rule_engine
from app.utils.auth import get_current_active_user
from app.utils.text_processor import build_chunk_rows, count_words, sha256_text

router = APIRouter()
ANALYSIS_PIPELINE_VERSION = "2026-04-13-v2"


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
    model_config = ConfigDict(protected_namespaces=())

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
    rule_findings: int = 0
    policy_hash: Optional[str] = None


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
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Не удалось извлечь текст из документа. Для сканов PDF нужен OCR.",
        )
    short_text_mode = len(text.strip()) < 50
    if not document.text_hash and text:
        document.text_hash = sha256_text(text)
        await db.flush()

    policy_hash = await rule_engine.compute_policy_hash(db)
    cached_payload = await _try_get_cached_analysis_payload(document, current_user, db, policy_hash=policy_hash)
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
                "policy_hash": policy_hash,
            },
            ip_address=http_request.client.host if http_request and http_request.client else None,
        )
        await db.commit()
        return AnalyzeResponse(**cached_payload)

    if llm_service.is_initialized and not short_text_mode:
        result = await _analyze_with_llm(text)
        model_mode = "llm"
    else:
        result = get_mock_analysis(text)
        model_mode = "mock_short" if short_text_mode else "mock"

    rule_outcome = await rule_engine.evaluate_text(
        db,
        text=text,
        max_findings=12,
    )
    builtin_outcome = _run_builtin_quality_checks(text, max_findings=24)
    combined_rule_outcome = _merge_rule_outcomes(rule_outcome, builtin_outcome, max_findings=24)
    result = _merge_analysis_with_rule_findings(result, combined_rule_outcome)
    result = _enforce_consistency_guards(result, text)
    result = _normalize_analysis_for_render(result, text)

    processing_ms = int((time.perf_counter() - start) * 1000)
    run = AnalysisRun(
        document_id=document.id,
        user_id=current_user.id,
        overall_score=result.overall_score,
        readability_score=result.readability_score,
        grammar_score=result.grammar_score,
        structure_score=result.structure_score,
        summary=result.summary,
        raw_response={**result.model_dump(), "analysis_pipeline_version": ANALYSIS_PIPELINE_VERSION},
        model_mode=model_mode,
        policy_hash=policy_hash,
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
            "rule_findings": int(combined_rule_outcome.get("matched_count", 0)),
            "policy_hash": policy_hash,
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
    payload["rule_findings"] = int(combined_rule_outcome.get("matched_count", 0))
    payload["policy_hash"] = policy_hash
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


@router.get("/analysis/{analysis_id}/export")
async def export_analysis_report(
    analysis_id: int,
    format: str = Query(default="json", pattern="^(json|pdf)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            AnalysisRun,
            DocumentRecord.filename,
            DocumentRecord.confidentiality_level,
            User.email,
        )
        .join(DocumentRecord, DocumentRecord.id == AnalysisRun.document_id)
        .join(User, User.id == AnalysisRun.user_id)
        .where(AnalysisRun.id == analysis_id)
        .limit(1)
    )
    if not current_user.is_admin:
        query = query.where(AnalysisRun.user_id == current_user.id)

    row = (await db.execute(query)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Анализ не найден")

    run, filename, confidentiality_level, user_email = row

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
    issue_details = _extract_issue_details(run.raw_response)

    payload = {
        "analysis_id": int(run.id),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "model_mode": str(run.model_mode or "unknown"),
        "processing_ms": run.processing_ms,
        "policy_hash": run.policy_hash,
        "document": {
            "id": int(run.document_id),
            "filename": str(filename),
            "confidentiality_level": str(confidentiality_level or "confidential"),
        },
        "user": {
            "id": str(run.user_id),
            "email": str(user_email),
        },
        "scores": {
            "overall": int(run.overall_score),
            "readability": int(run.readability_score),
            "grammar": int(run.grammar_score),
            "structure": int(run.structure_score),
        },
        "summary": str(run.summary or ""),
        "issues": [str(item) for item in issues],
        "recommendations": [str(item) for item in recommendations],
        "issue_details": issue_details,
        "rule_findings": len(issue_details),
    }

    if format == "json":
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=json_bytes,
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="analysis_{analysis_id}.json"'
            },
        )

    pdf_bytes = _build_analysis_pdf(payload)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="analysis_{analysis_id}.pdf"'
        },
    )


async def _try_get_cached_analysis_payload(
    document: DocumentRecord,
    user: User,
    db: AsyncSession,
    policy_hash: str | None,
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
                AnalysisRun.policy_hash == policy_hash,
            )
            .order_by(desc(AnalysisRun.id))
            .limit(1)
        )
    ).first()
    if not cached_row:
        return None

    (run,) = cached_row
    run_raw = run.raw_response if isinstance(run.raw_response, dict) else {}
    if str(run_raw.get("analysis_pipeline_version", "")) != ANALYSIS_PIPELINE_VERSION:
        return None
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
        "rule_findings": len(_extract_issue_details(run.raw_response)),
        "policy_hash": run.policy_hash,
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
        confidentiality_level="confidential",
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
    prompt = f"""Ты проверяешь технический документ на русском языке.
Верни ТОЛЬКО валидный JSON, без markdown и без комментариев.

Жесткие требования:
1) Не используй шаблонные фразы типа "конкретная проблема", "еще одна проблема", "конкретная правка".
2) В issue_details[].fragment указывай ФРАГМЕНТ ИЗ ИСХОДНОГО ТЕКСТА (буквально).
3) Если проблем мало, верни 1-3 реальных пункта. Не выдумывай.
4) Для каждой проблемы дай предметную рекомендацию.

Формат:
{{
  "overall_score": 0,
  "readability_score": 0,
  "grammar_score": 0,
  "structure_score": 0,
  "issues": ["..."],
  "recommendations": ["..."],
  "issue_details": [
    {{"fragment":"...","suggestion":"...","reason":"...","confidence":"low|medium|high"}}
  ],
  "summary": "..."
}}

Текст:
---
{text[:6000]}
---
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
        candidate = AnalyzeResponse(
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
        if _looks_placeholder_analysis(candidate):
            return _heuristic_analysis(text)
        return candidate
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


def _heuristic_analysis(text: str) -> AnalyzeResponse:
    """Fallback with concrete, text-grounded findings when LLM returns template/generic output."""
    base = get_mock_analysis(text)
    details = list(base.issue_details)

    if "!!!" in text:
        details.append(
            {
                "fragment": "!!!",
                "suggestion": ".",
                "reason": "Избыточные восклицательные знаки нарушают деловой стиль.",
                "confidence": "high",
                "severity": "medium",
                "source_ref": None,
                "rule_origin": "heuristic-style",
            }
        )

    long_sent = max((s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()), key=len, default="")
    if len(long_sent.split()) > 35:
        details.append(
            {
                "fragment": long_sent[:220],
                "suggestion": "Разделите предложение на 2-3 более коротких и оставьте по одной мысли на предложение.",
                "reason": "Слишком длинное предложение снижает читаемость и точность интерпретации.",
                "confidence": "medium",
                "severity": "medium",
                "source_ref": None,
                "rule_origin": "heuristic-readability",
            }
        )

    if details:
        issues = list(base.issues)
        recs = list(base.recommendations)
        if not any("пунктуац" in i.lower() for i in issues) and "!!!" in text:
            issues.append("Нарушен нейтральный тон: обнаружены эмоционально окрашенные знаки препинания.")
            recs.append("Уберите повторные восклицательные знаки и оставьте нейтральную пунктуацию.")
        return AnalyzeResponse(
            overall_score=base.overall_score,
            readability_score=base.readability_score,
            grammar_score=base.grammar_score,
            structure_score=base.structure_score,
            issues=issues[:40],
            recommendations=recs[:40],
            issue_details=details[:40],
            summary=base.summary,
            document_id=0,
            analysis_id=0,
        )

    return base


def _looks_placeholder_analysis(result: AnalyzeResponse) -> bool:
    bad_markers = (
        "конкретная проблема",
        "еще одна конкретная проблема",
        "конкретная правка",
        "вторая конкретная правка",
        "краткое резюме анализа",
    )
    issues_blob = " ".join(result.issues).lower()
    rec_blob = " ".join(result.recommendations).lower()
    summary = str(result.summary or "").lower()
    if any(marker in issues_blob for marker in bad_markers):
        return True
    if any(marker in rec_blob for marker in bad_markers):
        return True
    if any(marker in summary for marker in bad_markers):
        return True
    return False


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
        severity_raw = str(item.get("severity", "medium")).strip().lower()
        severity = severity_raw if severity_raw in {"low", "medium", "high", "critical"} else "medium"
        source_ref = item.get("source_ref")
        rule_origin = str(item.get("rule_origin", "")).strip() or None
        replacement = str(item.get("replacement", "")).strip() or None
        if fragment and suggestion:
            out.append(
                {
                    "fragment": fragment,
                    "suggestion": suggestion,
                    "reason": reason,
                    "confidence": confidence,
                    "severity": severity,
                    "source_ref": source_ref if isinstance(source_ref, dict) else None,
                    "rule_origin": rule_origin,
                    "replacement": replacement,
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
            severity_raw = str(item.get("severity", "medium")).strip().lower()
            severity = severity_raw if severity_raw in {"low", "medium", "high", "critical"} else "medium"
            source_ref = item.get("source_ref")
            rule_origin = str(item.get("rule_origin", "")).strip() or None
            replacement = str(item.get("replacement", "")).strip() or None
            if fragment and suggestion:
                aligned_fragment = _align_fragment_to_text(text, fragment)
                details.append(
                    {
                        "fragment": aligned_fragment,
                        "suggestion": suggestion,
                        "reason": reason,
                        "confidence": confidence,
                        "severity": severity,
                        "source_ref": source_ref if isinstance(source_ref, dict) else None,
                        "rule_origin": rule_origin,
                        "replacement": replacement,
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
                        "replacement": recommendation,
                        "reason": reason,
                        "confidence": "low",
                    "severity": "medium",
                    "source_ref": None,
                    "rule_origin": "llm-fallback",
                }
            )

    if not details and text.strip():
        fallback_fragment = text.strip()[:220]
        details.append(
            {
                "fragment": fallback_fragment,
                "suggestion": recommendations[0] if recommendations else "Уточните формулировки и добавьте конкретику.",
                "replacement": recommendations[0] if recommendations else "Уточните формулировки и добавьте конкретику.",
                "reason": issues[0] if issues else "Найдены потенциальные улучшения.",
                "confidence": "low",
                "severity": "medium",
                "source_ref": None,
                "rule_origin": "llm-fallback",
            }
        )

    return details[:10]


def _align_fragment_to_text(text: str, fragment: str) -> str:
    source = str(text or "")
    candidate = str(fragment or "").strip()
    if not candidate:
        return candidate
    if candidate in source:
        return candidate

    tokens = [tok for tok in re.findall(r"\w+", candidate.lower()) if len(tok) >= 3][:8]
    if not tokens:
        return candidate

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", source) if s.strip()]
    best_sentence = ""
    best_score = 0
    for sentence in sentences:
        sentence_l = sentence.lower()
        score = sum(1 for tok in tokens if tok in sentence_l)
        if score > best_score:
            best_score = score
            best_sentence = sentence
    if best_sentence and best_score >= 2:
        return best_sentence[:220]

    return candidate


def _merge_analysis_with_rule_findings(
    base_result: AnalyzeResponse,
    rule_outcome: dict,
) -> AnalyzeResponse:
    rule_issues = [str(x) for x in (rule_outcome.get("issues") or []) if str(x).strip()]
    rule_recommendations = [str(x) for x in (rule_outcome.get("recommendations") or []) if str(x).strip()]
    rule_details_raw = rule_outcome.get("issue_details") or []
    rule_details = [item for item in rule_details_raw if isinstance(item, dict)]

    if not rule_issues and not rule_details:
        return base_result

    merged_issues = list(base_result.issues)
    merged_recommendations = list(base_result.recommendations)
    merged_details = list(base_result.issue_details)

    if rule_issues:
        merged_issues = [item for item in merged_issues if item.strip().lower() != "явных проблем не найдено"]
        merged_recommendations = [
            item
            for item in merged_recommendations
            if item.strip().lower() != "текст соответствует базовым требованиям качества"
        ]

    existing_issue_keys = {value.strip().lower() for value in merged_issues}
    for issue in rule_issues:
        key = issue.strip().lower()
        if key and key not in existing_issue_keys:
            merged_issues.append(issue)
            existing_issue_keys.add(key)

    existing_rec_keys = {value.strip().lower() for value in merged_recommendations}
    for recommendation in rule_recommendations:
        key = recommendation.strip().lower()
        if key and key not in existing_rec_keys:
            merged_recommendations.append(recommendation)
            existing_rec_keys.add(key)

    existing_detail_keys = {
        (
            str(item.get("fragment", "")).strip().lower(),
            str(item.get("suggestion", "")).strip().lower(),
        )
        for item in merged_details
        if isinstance(item, dict)
    }
    for detail in rule_details:
        detail_key = (
            str(detail.get("fragment", "")).strip().lower(),
            str(detail.get("suggestion", "")).strip().lower(),
        )
        if detail_key[0] and detail_key[1] and detail_key not in existing_detail_keys:
            merged_details.append(detail)
            existing_detail_keys.add(detail_key)

    penalty = min(30, int(rule_outcome.get("matched_count", 0)) * 4)
    grammar_score = max(0, base_result.grammar_score - penalty)
    overall_score = int((base_result.readability_score + grammar_score + base_result.structure_score) / 3)
    quality_label = "хорошее" if overall_score > 70 else "требует улучшений"
    summary_base = (base_result.summary or "").strip()
    rule_count = int(rule_outcome.get("matched_count", 0))
    if summary_base:
        summary = f"{summary_base} Детектор правил: найдено {rule_count} срабатываний. Итоговое качество: {quality_label}."
    else:
        summary = f"Детектор правил: найдено {rule_count} срабатываний. Итоговое качество: {quality_label}."

    return AnalyzeResponse(
        overall_score=overall_score,
        readability_score=base_result.readability_score,
        grammar_score=grammar_score,
        structure_score=base_result.structure_score,
        issues=merged_issues[:40],
        recommendations=merged_recommendations[:40],
        issue_details=merged_details[:40],
        summary=summary,
        document_id=base_result.document_id,
        analysis_id=base_result.analysis_id,
    )


def _enforce_consistency_guards(result: AnalyzeResponse, text: str) -> AnalyzeResponse:
    issues = list(result.issues or [])
    recommendations = list(result.recommendations or [])
    details = [d for d in (result.issue_details or []) if isinstance(d, dict)]

    only_ok_issue = len(issues) == 1 and issues[0].strip().lower() == "явных проблем не найдено"
    if only_ok_issue and (
        int(result.readability_score) < 70 or int(result.grammar_score) < 75 or int(result.structure_score) < 75
    ):
        issues = []
        recommendations = []

    if int(result.readability_score) < 70 and not any("читаем" in i.lower() for i in issues):
        sentence = max((s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()), key=len, default="")
        issues.append("Сниженная читаемость: есть перегруженные или длинные формулировки.")
        recommendations.append("Сократите длину предложений и разделите сложные фразы на более короткие.")
        if sentence:
            details.append(
                {
                    "fragment": sentence[:220],
                    "suggestion": "Разделите этот фрагмент на 2-3 коротких предложения.",
                    "replacement": None,
                    "reason": "Длинные фразы ухудшают читаемость текста.",
                    "confidence": "medium",
                    "severity": "medium",
                    "source_ref": None,
                    "rule_origin": "builtin:consistency",
                }
            )

    if int(result.grammar_score) < 75 and not any("грам" in i.lower() or "орфограф" in i.lower() for i in issues):
        issues.append("Обнаружены языковые неточности, влияющие на грамматическое качество.")
        recommendations.append("Проведите орфографическую и пунктуационную вычитку документа.")

    if issues and not details:
        details = _prepare_issue_details(
            text=text,
            issues=issues,
            recommendations=recommendations,
            raw_details=[],
        )

    return AnalyzeResponse(
        overall_score=result.overall_score,
        readability_score=result.readability_score,
        grammar_score=result.grammar_score,
        structure_score=result.structure_score,
        issues=issues[:40] if issues else ["Явных проблем не найдено"],
        recommendations=recommendations[:40] if recommendations else ["Текст соответствует базовым требованиям качества"],
        issue_details=details[:40],
        summary=result.summary,
        document_id=result.document_id,
        analysis_id=result.analysis_id,
    )


def _normalize_analysis_for_render(result: AnalyzeResponse, text: str) -> AnalyzeResponse:
    normalized_details: list[dict] = []
    for item in (result.issue_details or []):
        if not isinstance(item, dict):
            continue
        fragment = _compact_fragment_for_highlight(text, str(item.get("fragment", "")))
        suggestion = str(item.get("suggestion", "")).strip()
        if not fragment or not suggestion:
            continue
        normalized = dict(item)
        normalized["fragment"] = fragment
        normalized_details.append(normalized)

    return AnalyzeResponse(
        overall_score=result.overall_score,
        readability_score=result.readability_score,
        grammar_score=result.grammar_score,
        structure_score=result.structure_score,
        issues=list(result.issues or [])[:40],
        recommendations=list(result.recommendations or [])[:40],
        issue_details=normalized_details[:40],
        summary=result.summary,
        document_id=result.document_id,
        analysis_id=result.analysis_id,
    )


def _compact_fragment_for_highlight(text: str, fragment: str, max_len: int = 72) -> str:
    src = str(text or "")
    frag = str(fragment or "").strip()
    if not frag:
        return ""
    if len(frag) <= max_len:
        return frag

    line = frag.splitlines()[0].strip()
    if line and len(line) <= max_len and line in src:
        return line
    if line and len(line) > max_len:
        candidate = line[:max_len].rstrip()
        if candidate in src:
            return candidate

    compact = re.sub(r"\s+", " ", frag).strip()
    if compact and len(compact) > max_len:
        for start in range(0, len(compact) - max_len + 1, max(1, max_len // 2)):
            candidate = compact[start:start + max_len].strip()
            if candidate and candidate in src:
                return candidate

    fallback = frag[:max_len].strip()
    return fallback


def _build_analysis_pdf(payload: dict) -> bytes:
    return _build_basic_pdf(payload)


def _merge_rule_outcomes(primary: dict, secondary: dict, max_findings: int = 24) -> dict:
    issues = [str(x) for x in (primary.get("issues") or []) if str(x).strip()]
    recommendations = [str(x) for x in (primary.get("recommendations") or []) if str(x).strip()]
    details = [x for x in (primary.get("issue_details") or []) if isinstance(x, dict)]

    for item in (secondary.get("issues") or []):
        text = str(item).strip()
        if text and text not in issues:
            issues.append(text)
    for item in (secondary.get("recommendations") or []):
        text = str(item).strip()
        if text and text not in recommendations:
            recommendations.append(text)

    existing = {
        (
            str(x.get("fragment", "")).strip().lower(),
            str(x.get("suggestion", "")).strip().lower(),
        )
        for x in details
    }
    for item in (secondary.get("issue_details") or []):
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("fragment", "")).strip().lower(),
            str(item.get("suggestion", "")).strip().lower(),
        )
        if key[0] and key[1] and key not in existing:
            details.append(item)
            existing.add(key)

    details = details[:max_findings]
    return {
        "issues": issues[:max_findings],
        "recommendations": recommendations[:max_findings],
        "issue_details": details,
        "matched_count": len(details),
    }


def _run_builtin_quality_checks(text: str, max_findings: int = 24) -> dict:
    src = str(text or "")
    src_l = src.lower()
    issues: list[str] = []
    recommendations: list[str] = []
    details: list[dict] = []

    typo_map = {
        "безопастност": "безопасност",
        "правельно": "правильно",
        "обородован": "оборудован",
        "постояное": "постоянное",
        "ненадо": "не надо",
        "предстовля": "представля",
        "попость": "попасть",
        "респератор": "респиратор",
        "раслаб": "расслаб",
        "всовременом": "в современном",
        "исскуствен": "искусствен",
        "обязятель": "обязатель",
        "не щаст": "несчаст",
        "инжинер": "инженер",
        "лезиш": "лезешь",
    }
    for bad, good in typo_map.items():
        idx = src_l.find(bad)
        if idx >= 0:
            fragment = src[idx:idx + len(bad)]
            issues.append(f"Орфографическая ошибка: «{bad}».")
            recommendations.append(f"Проверьте правописание и используйте форму, близкую к «{good}...».")
            details.append(
                {
                    "fragment": fragment,
                    "suggestion": good,
                    "replacement": good,
                    "reason": "Обнаружено слово с высокой вероятностью орфографической ошибки.",
                    "confidence": "high",
                    "severity": "medium",
                    "source_ref": None,
                    "rule_origin": "builtin:typo",
                }
            )
        if len(details) >= max_findings:
            break

    invalid_date = re.search(r"\b31\s+феврал[ья]\s+\d{4}\b", src_l)
    if invalid_date:
        fragment = src[invalid_date.start():invalid_date.end()]
        issues.append("Некорректная календарная дата в документе.")
        recommendations.append("Укажите реальную дату (например, 28 февраля или 1 марта соответствующего года).")
        details.append(
            {
                "fragment": fragment,
                "suggestion": fragment.replace("31 февраля", "28 февраля"),
                "replacement": fragment.replace("31 февраля", "28 февраля"),
                "reason": "31 февраля не существует в календаре.",
                "confidence": "high",
                "severity": "high",
                "source_ref": None,
                "rule_origin": "builtin:date",
            }
        )

    informal_markers = [
        "не тупите",
        "дядя",
        "мышки",
        "волосы стали дыбом",
        "можно не читать",
        "не знаю кто",
        "фамилия неразборчиво",
    ]
    for marker in informal_markers:
        idx = src_l.find(marker)
        if idx >= 0:
            fragment = src[idx: idx + len(marker)]
            issues.append("Разговорный/неформальный стиль для официального документа.")
            recommendations.append("Замените разговорные формулировки на нейтральный деловой стиль.")
            details.append(
                {
                    "fragment": fragment,
                    "suggestion": "Переформулируйте фрагмент в нейтральном официально-деловом стиле.",
                    "replacement": None,
                    "reason": "Фрагмент снижает формальность и пригодность документа для регламентного использования.",
                    "confidence": "medium",
                    "severity": "medium",
                    "source_ref": None,
                    "rule_origin": "builtin:style",
                }
            )
        if len(details) >= max_findings:
            break

    exclamation = re.search(r"!{2,}", src)
    if exclamation and len(details) < max_findings:
        frag = src[exclamation.start(): exclamation.end()]
        issues.append("Избыточные знаки восклицания в техническом тексте.")
        recommendations.append("Используйте нейтральную пунктуацию: один знак или точку.")
        details.append(
            {
                "fragment": frag,
                "suggestion": ".",
                "replacement": ".",
                "reason": "Эмоциональная пунктуация ухудшает официальный стиль документа.",
                "confidence": "high",
                "severity": "low",
                "source_ref": None,
                "rule_origin": "builtin:punct",
            }
        )

    # Deduplicate
    uniq_issues: list[str] = []
    for item in issues:
        if item not in uniq_issues:
            uniq_issues.append(item)
    uniq_recs: list[str] = []
    for item in recommendations:
        if item not in uniq_recs:
            uniq_recs.append(item)

    return {
        "issues": uniq_issues[:max_findings],
        "recommendations": uniq_recs[:max_findings],
        "issue_details": details[:max_findings],
        "matched_count": min(len(details), max_findings),
    }


def _build_basic_pdf(payload: dict) -> bytes:
    def sanitize(value: str) -> str:
        return str(value).encode("latin-1", "replace").decode("latin-1")

    def escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    doc = payload.get("document", {})
    scores = payload.get("scores", {})
    issues = payload.get("issues", []) or []
    recommendations = payload.get("recommendations", []) or []

    lines: list[str] = [
        "Analysis report",
        f"Analysis ID: {payload.get('analysis_id')}",
        f"Date: {payload.get('created_at')}",
        f"Mode: {payload.get('model_mode')}",
        f"Processing: {payload.get('processing_ms')} ms",
        f"Policy hash: {payload.get('policy_hash') or '-'}",
        "",
        f"Document ID: {doc.get('id')}",
        f"Filename: {doc.get('filename')}",
        f"Confidentiality: {doc.get('confidentiality_level')}",
        "",
        f"Overall score: {scores.get('overall')}/100",
        f"Readability: {scores.get('readability')}/100",
        f"Grammar: {scores.get('grammar')}/100",
        f"Structure: {scores.get('structure')}/100",
        "",
        "Summary:",
        str(payload.get("summary") or ""),
        "",
        "Issues:",
    ]
    lines.extend([f"- {x}" for x in issues[:40]] or ["- none"])
    lines.append("")
    lines.append("Recommendations:")
    lines.extend([f"- {x}" for x in recommendations[:40]] or ["- none"])

    def wrap_line(value: str, max_len: int = 96) -> list[str]:
        text = sanitize(value)
        if len(text) <= max_len:
            return [text]
        parts: list[str] = []
        current = ""
        for word in text.split(" "):
            if len(word) > max_len:
                if current:
                    parts.append(current.rstrip())
                    current = ""
                for i in range(0, len(word), max_len):
                    parts.append(word[i:i + max_len])
                continue
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    parts.append(current)
                current = word
        if current:
            parts.append(current)
        return parts or [text[:max_len]]

    wrapped_lines: list[str] = []
    for row in lines[:130]:
        wrapped_lines.extend(wrap_line(str(row), max_len=96))
    safe_lines = wrapped_lines[:260]

    content_lines = [
        "BT",
        "/F1 10 Tf",
        "13 TL",
        "40 800 Td",
    ]
    for idx, line in enumerate(safe_lines):
        prefix = "" if idx == 0 else "T* "
        content_lines.append(f"{prefix}({escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", "replace")

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)
