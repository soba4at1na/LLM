import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.knowledge import GlossaryTerm, KnowledgePolicySnapshot, RulePattern, SourceReference
from app.models.user import User
from app.services.audit_service import log_event
from app.services.rule_engine import rule_engine
from app.utils.auth import get_current_admin_user

router = APIRouter()

ALLOWED_RULE_TYPES = {"regex", "lemma", "triplet"}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}

DEFAULT_SOURCES = [
    {
        "title": "ГОСТ Р ИСО/МЭК 27001-2021",
        "section": "Термины и определения",
        "reference_code": "ISO27001-RU",
        "url_or_local_path": None,
        "note": "Базовый словарь терминов ИБ для внутренних документов.",
    },
    {
        "title": "Внутренний глоссарий ИТ и ИБ",
        "section": "Корпоративный стандарт",
        "reference_code": "CORP-IT-SEC-001",
        "url_or_local_path": None,
        "note": "Единая терминология для коммерческой документации.",
    },
]

DEFAULT_GLOSSARY = [
    {
        "term": "IP-адрес",
        "canonical_definition": "IP — это интернет-протокол, а IP-адрес — идентификатор узла в сети.",
        "forbidden_variants": ["ip это интернет", "ip это интернет", "ip - это интернет"],
        "allowed_variants": ["IP-адрес", "адрес IP"],
        "category": "network",
        "severity_default": "high",
        "source_code": "CORP-IT-SEC-001",
    },
    {
        "term": "Персональные данные",
        "canonical_definition": "Используйте формулировку 'персональные данные', избегайте сокращений без расшифровки.",
        "forbidden_variants": ["перс данные", "перс. данные", "пдн"],
        "allowed_variants": ["персональные данные", "ПДн (персональные данные)"],
        "category": "legal",
        "severity_default": "medium",
        "source_code": "CORP-IT-SEC-001",
    },
    {
        "term": "Информационная безопасность",
        "canonical_definition": "Термин 'информационная безопасность' пишется полностью при первом упоминании.",
        "forbidden_variants": ["иб", "инфобез"],
        "allowed_variants": ["информационная безопасность", "ИБ (информационная безопасность)"],
        "category": "security",
        "severity_default": "medium",
        "source_code": "ISO27001-RU",
    },
]

DEFAULT_RULES = [
    {
        "name": "Двойные пробелы",
        "rule_type": "regex",
        "pattern": r" {2,}",
        "description": "Обнаружены множественные пробелы.",
        "severity": "low",
        "suggestion_template": "Замените множественные пробелы на один.",
        "source_code": "CORP-IT-SEC-001",
    },
    {
        "name": "Слишком много восклицательных знаков",
        "rule_type": "regex",
        "pattern": r"!{2,}",
        "description": "Избыточная эмоциональная пунктуация неуместна в техническом документе.",
        "severity": "medium",
        "suggestion_template": "Оставьте один восклицательный знак или замените на точку.",
        "source_code": "CORP-IT-SEC-001",
    },
    {
        "name": "Капслок-фрагменты",
        "rule_type": "regex",
        "pattern": r"\\b[А-ЯЁ]{5,}\\b",
        "description": "Найдены слова в полном верхнем регистре.",
        "severity": "low",
        "suggestion_template": "Используйте стандартный регистр, если это не официальная аббревиатура.",
        "source_code": "CORP-IT-SEC-001",
    },
]


def _normalize_severity(value: str | None) -> str:
    normalized = str(value or "medium").strip().lower()
    if normalized not in ALLOWED_SEVERITIES:
        raise HTTPException(status_code=400, detail="Invalid severity. Allowed: low, medium, high, critical")
    return normalized


def _normalize_rule_type(value: str | None) -> str:
    normalized = str(value or "regex").strip().lower()
    if normalized not in ALLOWED_RULE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid rule_type. Allowed: regex, lemma, triplet")
    return normalized


def _validate_pattern(rule_type: str, pattern: str) -> None:
    if rule_type != "regex":
        return
    import re

    try:
        re.compile(pattern)
    except re.error as exc:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {exc}") from exc


def _normalize_term(term: str) -> str:
    return " ".join(term.lower().strip().split())


def _normalize_reference_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    if not code:
        return None
    import re

    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{1,63}", code):
        raise HTTPException(
            status_code=400,
            detail="Invalid reference_code format. Allowed: A-Z, 0-9, dot, underscore, hyphen (2-64 chars)",
        )
    return code


class KnowledgeOverview(BaseModel):
    sources_count: int
    glossary_terms_count: int
    rule_patterns_count: int
    active_glossary_terms_count: int
    active_rule_patterns_count: int


class SeedResponse(BaseModel):
    sources_created: int
    glossary_created: int
    rules_created: int


class KnowledgeSnapshotCreateRequest(BaseModel):
    label: Optional[str] = Field(default=None, max_length=255)


class KnowledgeSnapshotOut(BaseModel):
    id: int
    label: Optional[str] = None
    policy_hash: str
    created_by: Optional[str] = None
    created_by_email: Optional[str] = None
    created_at: str


class SourceReferenceCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    section: Optional[str] = Field(default=None, max_length=128)
    reference_code: Optional[str] = Field(default=None, max_length=128)
    url_or_local_path: Optional[str] = Field(default=None, max_length=1024)
    note: Optional[str] = None
    is_active: bool = True


class SourceReferenceUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=255)
    section: Optional[str] = Field(default=None, max_length=128)
    reference_code: Optional[str] = Field(default=None, max_length=128)
    url_or_local_path: Optional[str] = Field(default=None, max_length=1024)
    note: Optional[str] = None
    is_active: Optional[bool] = None


class SourceReferenceOut(BaseModel):
    id: int
    title: str
    section: Optional[str] = None
    reference_code: Optional[str] = None
    url_or_local_path: Optional[str] = None
    note: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: Optional[str] = None


class GlossaryTermCreate(BaseModel):
    term: str = Field(..., min_length=1, max_length=255)
    canonical_definition: str = Field(..., min_length=1)
    allowed_variants: List[str] = Field(default_factory=list)
    forbidden_variants: List[str] = Field(default_factory=list)
    category: Optional[str] = Field(default=None, max_length=64)
    severity_default: str = "medium"
    source_ref_id: Optional[int] = None
    is_active: bool = True


class GlossaryTermUpdate(BaseModel):
    term: Optional[str] = Field(default=None, min_length=1, max_length=255)
    canonical_definition: Optional[str] = Field(default=None, min_length=1)
    allowed_variants: Optional[List[str]] = None
    forbidden_variants: Optional[List[str]] = None
    category: Optional[str] = Field(default=None, max_length=64)
    severity_default: Optional[str] = None
    source_ref_id: Optional[int] = None
    is_active: Optional[bool] = None


class GlossaryTermOut(BaseModel):
    id: int
    term: str
    normalized_term: str
    canonical_definition: str
    allowed_variants: List[str]
    forbidden_variants: List[str]
    category: Optional[str] = None
    severity_default: str
    source_ref_id: Optional[int] = None
    source_ref_title: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: Optional[str] = None


class RulePatternCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    rule_type: str = "regex"
    pattern: str = Field(..., min_length=1)
    description: Optional[str] = None
    severity: str = "medium"
    suggestion_template: Optional[str] = None
    source_ref_id: Optional[int] = None
    is_active: bool = True


class RulePatternUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    rule_type: Optional[str] = None
    pattern: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    severity: Optional[str] = None
    suggestion_template: Optional[str] = None
    source_ref_id: Optional[int] = None
    is_active: Optional[bool] = None


class RulePatternOut(BaseModel):
    id: int
    name: str
    rule_type: str
    pattern: str
    description: Optional[str] = None
    severity: str
    suggestion_template: Optional[str] = None
    source_ref_id: Optional[int] = None
    source_ref_title: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: Optional[str] = None


def _source_to_out(item: SourceReference) -> SourceReferenceOut:
    return SourceReferenceOut(
        id=int(item.id),
        title=item.title,
        section=item.section,
        reference_code=item.reference_code,
        url_or_local_path=item.url_or_local_path,
        note=item.note,
        is_active=bool(item.is_active),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


def _glossary_to_out(item: GlossaryTerm, source_title: str | None = None) -> GlossaryTermOut:
    return GlossaryTermOut(
        id=int(item.id),
        term=item.term,
        normalized_term=item.normalized_term,
        canonical_definition=item.canonical_definition,
        allowed_variants=list(item.allowed_variants or []),
        forbidden_variants=list(item.forbidden_variants or []),
        category=item.category,
        severity_default=item.severity_default,
        source_ref_id=int(item.source_ref_id) if item.source_ref_id else None,
        source_ref_title=source_title,
        is_active=bool(item.is_active),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


def _rule_to_out(item: RulePattern, source_title: str | None = None) -> RulePatternOut:
    return RulePatternOut(
        id=int(item.id),
        name=item.name,
        rule_type=item.rule_type,
        pattern=item.pattern,
        description=item.description,
        severity=item.severity,
        suggestion_template=item.suggestion_template,
        source_ref_id=int(item.source_ref_id) if item.source_ref_id else None,
        source_ref_title=source_title,
        is_active=bool(item.is_active),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


async def _ensure_source_exists(db: AsyncSession, source_ref_id: int | None) -> None:
    if source_ref_id is None:
        return
    source = await db.scalar(select(SourceReference).where(SourceReference.id == source_ref_id))
    if not source:
        raise HTTPException(status_code=400, detail="source_ref_id not found")


async def _source_id_by_code(db: AsyncSession, reference_code: str | None) -> int | None:
    if not reference_code:
        return None
    source = await db.scalar(
        select(SourceReference).where(
            SourceReference.reference_code == reference_code,
        )
    )
    return int(source.id) if source else None


async def _serialize_policy(db: AsyncSession) -> dict:
    sources = (
        await db.execute(
            select(SourceReference).order_by(SourceReference.id)
        )
    ).scalars().all()
    glossary = (
        await db.execute(
            select(GlossaryTerm).order_by(GlossaryTerm.id)
        )
    ).scalars().all()
    rules = (
        await db.execute(
            select(RulePattern).order_by(RulePattern.id)
        )
    ).scalars().all()

    return {
        "sources": [
            {
                "id": int(item.id),
                "title": item.title,
                "section": item.section,
                "reference_code": item.reference_code,
                "url_or_local_path": item.url_or_local_path,
                "note": item.note,
                "is_active": bool(item.is_active),
            }
            for item in sources
        ],
        "glossary": [
            {
                "id": int(item.id),
                "term": item.term,
                "normalized_term": item.normalized_term,
                "canonical_definition": item.canonical_definition,
                "allowed_variants": list(item.allowed_variants or []),
                "forbidden_variants": list(item.forbidden_variants or []),
                "category": item.category,
                "severity_default": item.severity_default,
                "source_ref_id": int(item.source_ref_id) if item.source_ref_id else None,
                "is_active": bool(item.is_active),
            }
            for item in glossary
        ],
        "rules": [
            {
                "id": int(item.id),
                "name": item.name,
                "rule_type": item.rule_type,
                "pattern": item.pattern,
                "description": item.description,
                "severity": item.severity,
                "suggestion_template": item.suggestion_template,
                "source_ref_id": int(item.source_ref_id) if item.source_ref_id else None,
                "is_active": bool(item.is_active),
            }
            for item in rules
        ],
    }


@router.get("/admin/knowledge/overview", response_model=KnowledgeOverview)
async def knowledge_overview(
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    sources_count = await db.scalar(select(func.count(SourceReference.id)))
    glossary_terms_count = await db.scalar(select(func.count(GlossaryTerm.id)))
    rule_patterns_count = await db.scalar(select(func.count(RulePattern.id)))
    active_glossary_terms_count = await db.scalar(
        select(func.count(GlossaryTerm.id)).where(GlossaryTerm.is_active.is_(True))
    )
    active_rule_patterns_count = await db.scalar(
        select(func.count(RulePattern.id)).where(RulePattern.is_active.is_(True))
    )

    return KnowledgeOverview(
        sources_count=int(sources_count or 0),
        glossary_terms_count=int(glossary_terms_count or 0),
        rule_patterns_count=int(rule_patterns_count or 0),
        active_glossary_terms_count=int(active_glossary_terms_count or 0),
        active_rule_patterns_count=int(active_rule_patterns_count or 0),
    )


@router.get("/admin/knowledge/snapshots", response_model=List[KnowledgeSnapshotOut])
async def list_snapshots(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    snapshots = (
        await db.execute(
            select(KnowledgePolicySnapshot)
            .order_by(desc(KnowledgePolicySnapshot.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    out: list[KnowledgeSnapshotOut] = []
    for item in snapshots:
        email: str | None = None
        if item.created_by:
            try:
                created_by_uuid = uuid.UUID(str(item.created_by))
                email_row = await db.scalar(select(User.email).where(User.id == created_by_uuid))
                email = str(email_row) if email_row else None
            except ValueError:
                email = None
        out.append(
            KnowledgeSnapshotOut(
                id=int(item.id),
                label=item.label,
                policy_hash=item.policy_hash,
                created_by=item.created_by,
                created_by_email=email,
                created_at=item.created_at.isoformat(),
            )
        )
    return out


@router.post("/admin/knowledge/snapshots", response_model=KnowledgeSnapshotOut, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    payload: KnowledgeSnapshotCreateRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    snapshot_json = await _serialize_policy(db)
    policy_hash = await rule_engine.compute_policy_hash(db)
    item = KnowledgePolicySnapshot(
        label=payload.label.strip() if payload.label else None,
        policy_hash=policy_hash,
        snapshot_json=snapshot_json,
        created_by=str(admin_user.id),
    )
    db.add(item)
    await db.flush()
    await log_event(
        db,
        action="knowledge_snapshot_create",
        user_id=admin_user.id,
        resource_type="knowledge_snapshot",
        resource_id=str(item.id),
        metadata={"label": item.label, "policy_hash": item.policy_hash},
    )
    await db.commit()
    await db.refresh(item)
    return KnowledgeSnapshotOut(
        id=int(item.id),
        label=item.label,
        policy_hash=item.policy_hash,
        created_by=item.created_by,
        created_by_email=admin_user.email,
        created_at=item.created_at.isoformat(),
    )


@router.post("/admin/knowledge/snapshots/{snapshot_id}/restore")
async def restore_snapshot(
    snapshot_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    snapshot = await db.scalar(
        select(KnowledgePolicySnapshot).where(KnowledgePolicySnapshot.id == snapshot_id)
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if not isinstance(snapshot.snapshot_json, dict):
        raise HTTPException(status_code=400, detail="Snapshot is corrupted")

    payload = snapshot.snapshot_json
    sources = payload.get("sources", []) if isinstance(payload.get("sources", []), list) else []
    glossary = payload.get("glossary", []) if isinstance(payload.get("glossary", []), list) else []
    rules = payload.get("rules", []) if isinstance(payload.get("rules", []), list) else []

    await db.execute(delete(RulePattern))
    await db.execute(delete(GlossaryTerm))
    await db.execute(delete(SourceReference))
    await db.flush()

    for item in sources:
        if not isinstance(item, dict):
            continue
        db.add(
            SourceReference(
                id=int(item.get("id", 0)) or None,
                title=str(item.get("title", "")).strip() or "Без названия",
                section=str(item.get("section", "")).strip() or None,
                reference_code=_normalize_reference_code(item.get("reference_code")),
                url_or_local_path=str(item.get("url_or_local_path", "")).strip() or None,
                note=str(item.get("note", "")).strip() or None,
                is_active=bool(item.get("is_active", True)),
            )
        )
    await db.flush()

    for item in glossary:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        if not term:
            continue
        db.add(
            GlossaryTerm(
                id=int(item.get("id", 0)) or None,
                term=term,
                normalized_term=_normalize_term(term),
                canonical_definition=str(item.get("canonical_definition", "")).strip() or "—",
                allowed_variants=[str(x).strip() for x in (item.get("allowed_variants") or []) if str(x).strip()],
                forbidden_variants=[str(x).strip() for x in (item.get("forbidden_variants") or []) if str(x).strip()],
                category=str(item.get("category", "")).strip() or None,
                severity_default=_normalize_severity(item.get("severity_default")),
                source_ref_id=int(item.get("source_ref_id")) if item.get("source_ref_id") is not None else None,
                is_active=bool(item.get("is_active", True)),
            )
        )
    await db.flush()

    for item in rules:
        if not isinstance(item, dict):
            continue
        rule_name = str(item.get("name", "")).strip()
        pattern = str(item.get("pattern", ""))
        if not rule_name or not pattern:
            continue
        rule_type = _normalize_rule_type(item.get("rule_type"))
        _validate_pattern(rule_type, pattern)
        db.add(
            RulePattern(
                id=int(item.get("id", 0)) or None,
                name=rule_name,
                rule_type=rule_type,
                pattern=pattern,
                description=str(item.get("description", "")).strip() or None,
                severity=_normalize_severity(item.get("severity")),
                suggestion_template=str(item.get("suggestion_template", "")).strip() or None,
                source_ref_id=int(item.get("source_ref_id")) if item.get("source_ref_id") is not None else None,
                is_active=bool(item.get("is_active", True)),
            )
        )
    await db.flush()

    await db.execute(
        select(func.setval("source_references_id_seq", func.coalesce(func.max(SourceReference.id), 1), True))
    )
    await db.execute(
        select(func.setval("glossary_terms_id_seq", func.coalesce(func.max(GlossaryTerm.id), 1), True))
    )
    await db.execute(
        select(func.setval("rule_patterns_id_seq", func.coalesce(func.max(RulePattern.id), 1), True))
    )

    new_hash = await rule_engine.compute_policy_hash(db)
    await log_event(
        db,
        action="knowledge_snapshot_restore",
        user_id=admin_user.id,
        resource_type="knowledge_snapshot",
        resource_id=str(snapshot.id),
        metadata={
            "restored_snapshot_id": snapshot.id,
            "restored_policy_hash": new_hash,
        },
    )
    await db.commit()
    return {"ok": True, "snapshot_id": snapshot.id, "policy_hash": new_hash}


@router.post("/admin/knowledge/seed-defaults", response_model=SeedResponse)
async def seed_defaults(
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    created_sources = 0
    created_glossary = 0
    created_rules = 0

    for source_payload in DEFAULT_SOURCES:
        existing = await db.scalar(
            select(SourceReference).where(
                SourceReference.title == source_payload["title"],
                SourceReference.reference_code == source_payload["reference_code"],
            )
        )
        if existing:
            continue
        source = SourceReference(
            title=source_payload["title"],
            section=source_payload["section"],
            reference_code=source_payload["reference_code"],
            url_or_local_path=source_payload["url_or_local_path"],
            note=source_payload["note"],
            is_active=True,
        )
        db.add(source)
        created_sources += 1

    await db.flush()

    for term_payload in DEFAULT_GLOSSARY:
        normalized_term = _normalize_term(term_payload["term"])
        existing = await db.scalar(
            select(GlossaryTerm).where(
                GlossaryTerm.normalized_term == normalized_term,
                GlossaryTerm.canonical_definition == term_payload["canonical_definition"],
            )
        )
        if existing:
            continue
        source_ref_id = await _source_id_by_code(db, term_payload.get("source_code"))
        term = GlossaryTerm(
            term=term_payload["term"],
            normalized_term=normalized_term,
            canonical_definition=term_payload["canonical_definition"],
            allowed_variants=term_payload["allowed_variants"],
            forbidden_variants=term_payload["forbidden_variants"],
            category=term_payload["category"],
            severity_default=_normalize_severity(term_payload["severity_default"]),
            source_ref_id=source_ref_id,
            is_active=True,
        )
        db.add(term)
        created_glossary += 1

    for rule_payload in DEFAULT_RULES:
        existing = await db.scalar(
            select(RulePattern).where(
                RulePattern.name == rule_payload["name"],
                RulePattern.pattern == rule_payload["pattern"],
            )
        )
        if existing:
            continue
        source_ref_id = await _source_id_by_code(db, rule_payload.get("source_code"))
        rule_type = _normalize_rule_type(rule_payload["rule_type"])
        _validate_pattern(rule_type, rule_payload["pattern"])
        rule = RulePattern(
            name=rule_payload["name"],
            rule_type=rule_type,
            pattern=rule_payload["pattern"],
            description=rule_payload["description"],
            severity=_normalize_severity(rule_payload["severity"]),
            suggestion_template=rule_payload["suggestion_template"],
            source_ref_id=source_ref_id,
            is_active=True,
        )
        db.add(rule)
        created_rules += 1

    await log_event(
        db,
        action="knowledge_seed_defaults",
        user_id=admin_user.id,
        resource_type="knowledge",
        resource_id="defaults",
        metadata={
            "sources_created": created_sources,
            "glossary_created": created_glossary,
            "rules_created": created_rules,
        },
    )
    await db.commit()
    return SeedResponse(
        sources_created=created_sources,
        glossary_created=created_glossary,
        rules_created=created_rules,
    )


@router.get("/admin/knowledge/sources", response_model=List[SourceReferenceOut])
async def list_sources(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=False),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SourceReference).order_by(desc(SourceReference.id)).limit(limit).offset(offset)
    if active_only:
        query = query.where(SourceReference.is_active.is_(True))
    rows = (await db.execute(query)).scalars().all()
    return [_source_to_out(item) for item in rows]


@router.post("/admin/knowledge/sources", response_model=SourceReferenceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceReferenceCreate,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = SourceReference(
        title=payload.title.strip(),
        section=payload.section.strip() if payload.section else None,
        reference_code=_normalize_reference_code(payload.reference_code),
        url_or_local_path=payload.url_or_local_path.strip() if payload.url_or_local_path else None,
        note=payload.note.strip() if payload.note else None,
        is_active=payload.is_active,
    )
    db.add(item)
    await db.flush()
    await log_event(
        db,
        action="knowledge_source_create",
        user_id=admin_user.id,
        resource_type="source_reference",
        resource_id=str(item.id),
        metadata={"title": item.title},
    )
    await db.commit()
    await db.refresh(item)
    return _source_to_out(item)


@router.patch("/admin/knowledge/sources/{source_id}", response_model=SourceReferenceOut)
async def update_source(
    source_id: int,
    payload: SourceReferenceUpdate,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(select(SourceReference).where(SourceReference.id == source_id))
    if not item:
        raise HTTPException(status_code=404, detail="Source reference not found")

    if payload.title is not None:
        item.title = payload.title.strip()
    if payload.section is not None:
        item.section = payload.section.strip() or None
    if payload.reference_code is not None:
        item.reference_code = _normalize_reference_code(payload.reference_code)
    if payload.url_or_local_path is not None:
        item.url_or_local_path = payload.url_or_local_path.strip() or None
    if payload.note is not None:
        item.note = payload.note.strip() or None
    if payload.is_active is not None:
        item.is_active = payload.is_active

    await log_event(
        db,
        action="knowledge_source_update",
        user_id=admin_user.id,
        resource_type="source_reference",
        resource_id=str(item.id),
        metadata={"title": item.title, "is_active": item.is_active},
    )
    await db.commit()
    await db.refresh(item)
    return _source_to_out(item)


@router.delete("/admin/knowledge/sources/{source_id}")
async def delete_source(
    source_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(select(SourceReference).where(SourceReference.id == source_id))
    if not item:
        raise HTTPException(status_code=404, detail="Source reference not found")
    item.is_active = False
    await log_event(
        db,
        action="knowledge_source_deactivate",
        user_id=admin_user.id,
        resource_type="source_reference",
        resource_id=str(item.id),
        metadata={"title": item.title},
    )
    await db.commit()
    return {"ok": True}


@router.get("/admin/knowledge/glossary", response_model=List[GlossaryTermOut])
async def list_glossary(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=False),
    search: Optional[str] = Query(default=None),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(GlossaryTerm, SourceReference.title)
        .outerjoin(SourceReference, SourceReference.id == GlossaryTerm.source_ref_id)
        .order_by(desc(GlossaryTerm.id))
        .limit(limit)
        .offset(offset)
    )
    if active_only:
        query = query.where(GlossaryTerm.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        query = query.where((GlossaryTerm.term.ilike(like)) | (GlossaryTerm.canonical_definition.ilike(like)))

    rows = (await db.execute(query)).all()
    return [_glossary_to_out(item, str(title) if title else None) for item, title in rows]


@router.post("/admin/knowledge/glossary", response_model=GlossaryTermOut, status_code=status.HTTP_201_CREATED)
async def create_glossary_term(
    payload: GlossaryTermCreate,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_source_exists(db, payload.source_ref_id)
    item = GlossaryTerm(
        term=payload.term.strip(),
        normalized_term=_normalize_term(payload.term),
        canonical_definition=payload.canonical_definition.strip(),
        allowed_variants=[v.strip() for v in payload.allowed_variants if v.strip()],
        forbidden_variants=[v.strip() for v in payload.forbidden_variants if v.strip()],
        category=payload.category.strip() if payload.category else None,
        severity_default=_normalize_severity(payload.severity_default),
        source_ref_id=payload.source_ref_id,
        is_active=payload.is_active,
    )
    db.add(item)
    await db.flush()
    await log_event(
        db,
        action="knowledge_glossary_create",
        user_id=admin_user.id,
        resource_type="glossary_term",
        resource_id=str(item.id),
        metadata={"term": item.term},
    )
    await db.commit()
    await db.refresh(item)
    source_title = await db.scalar(select(SourceReference.title).where(SourceReference.id == item.source_ref_id))
    return _glossary_to_out(item, str(source_title) if source_title else None)


@router.patch("/admin/knowledge/glossary/{term_id}", response_model=GlossaryTermOut)
async def update_glossary_term(
    term_id: int,
    payload: GlossaryTermUpdate,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(select(GlossaryTerm).where(GlossaryTerm.id == term_id))
    if not item:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    if payload.source_ref_id is not None:
        await _ensure_source_exists(db, payload.source_ref_id)

    if payload.term is not None:
        item.term = payload.term.strip()
        item.normalized_term = _normalize_term(payload.term)
    if payload.canonical_definition is not None:
        item.canonical_definition = payload.canonical_definition.strip()
    if payload.allowed_variants is not None:
        item.allowed_variants = [v.strip() for v in payload.allowed_variants if v.strip()]
    if payload.forbidden_variants is not None:
        item.forbidden_variants = [v.strip() for v in payload.forbidden_variants if v.strip()]
    if payload.category is not None:
        item.category = payload.category.strip() or None
    if payload.severity_default is not None:
        item.severity_default = _normalize_severity(payload.severity_default)
    if payload.source_ref_id is not None:
        item.source_ref_id = payload.source_ref_id
    if payload.is_active is not None:
        item.is_active = payload.is_active

    await log_event(
        db,
        action="knowledge_glossary_update",
        user_id=admin_user.id,
        resource_type="glossary_term",
        resource_id=str(item.id),
        metadata={"term": item.term, "is_active": item.is_active},
    )
    await db.commit()
    await db.refresh(item)
    source_title = await db.scalar(select(SourceReference.title).where(SourceReference.id == item.source_ref_id))
    return _glossary_to_out(item, str(source_title) if source_title else None)


@router.delete("/admin/knowledge/glossary/{term_id}")
async def delete_glossary_term(
    term_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(select(GlossaryTerm).where(GlossaryTerm.id == term_id))
    if not item:
        raise HTTPException(status_code=404, detail="Glossary term not found")
    item.is_active = False
    await log_event(
        db,
        action="knowledge_glossary_deactivate",
        user_id=admin_user.id,
        resource_type="glossary_term",
        resource_id=str(item.id),
        metadata={"term": item.term},
    )
    await db.commit()
    return {"ok": True}


@router.get("/admin/knowledge/rules", response_model=List[RulePatternOut])
async def list_rules(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=False),
    rule_type: Optional[str] = Query(default=None),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(RulePattern, SourceReference.title)
        .outerjoin(SourceReference, SourceReference.id == RulePattern.source_ref_id)
        .order_by(desc(RulePattern.id))
        .limit(limit)
        .offset(offset)
    )
    if active_only:
        query = query.where(RulePattern.is_active.is_(True))
    if rule_type:
        query = query.where(RulePattern.rule_type == _normalize_rule_type(rule_type))

    rows = (await db.execute(query)).all()
    return [_rule_to_out(item, str(title) if title else None) for item, title in rows]


@router.post("/admin/knowledge/rules", response_model=RulePatternOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: RulePatternCreate,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_source_exists(db, payload.source_ref_id)
    item = RulePattern(
        name=payload.name.strip(),
        rule_type=_normalize_rule_type(payload.rule_type),
        pattern=payload.pattern,
        description=payload.description.strip() if payload.description else None,
        severity=_normalize_severity(payload.severity),
        suggestion_template=payload.suggestion_template.strip() if payload.suggestion_template else None,
        source_ref_id=payload.source_ref_id,
        is_active=payload.is_active,
    )
    _validate_pattern(item.rule_type, item.pattern)
    db.add(item)
    await db.flush()
    await log_event(
        db,
        action="knowledge_rule_create",
        user_id=admin_user.id,
        resource_type="rule_pattern",
        resource_id=str(item.id),
        metadata={"name": item.name, "rule_type": item.rule_type},
    )
    await db.commit()
    await db.refresh(item)
    source_title = await db.scalar(select(SourceReference.title).where(SourceReference.id == item.source_ref_id))
    return _rule_to_out(item, str(source_title) if source_title else None)


@router.patch("/admin/knowledge/rules/{rule_id}", response_model=RulePatternOut)
async def update_rule(
    rule_id: int,
    payload: RulePatternUpdate,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(select(RulePattern).where(RulePattern.id == rule_id))
    if not item:
        raise HTTPException(status_code=404, detail="Rule pattern not found")

    if payload.source_ref_id is not None:
        await _ensure_source_exists(db, payload.source_ref_id)
    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.rule_type is not None:
        item.rule_type = _normalize_rule_type(payload.rule_type)
    if payload.pattern is not None:
        item.pattern = payload.pattern
    _validate_pattern(item.rule_type, item.pattern)
    if payload.description is not None:
        item.description = payload.description.strip() or None
    if payload.severity is not None:
        item.severity = _normalize_severity(payload.severity)
    if payload.suggestion_template is not None:
        item.suggestion_template = payload.suggestion_template.strip() or None
    if payload.source_ref_id is not None:
        item.source_ref_id = payload.source_ref_id
    if payload.is_active is not None:
        item.is_active = payload.is_active

    await log_event(
        db,
        action="knowledge_rule_update",
        user_id=admin_user.id,
        resource_type="rule_pattern",
        resource_id=str(item.id),
        metadata={"name": item.name, "is_active": item.is_active},
    )
    await db.commit()
    await db.refresh(item)
    source_title = await db.scalar(select(SourceReference.title).where(SourceReference.id == item.source_ref_id))
    return _rule_to_out(item, str(source_title) if source_title else None)


@router.delete("/admin/knowledge/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(select(RulePattern).where(RulePattern.id == rule_id))
    if not item:
        raise HTTPException(status_code=404, detail="Rule pattern not found")
    item.is_active = False
    await log_event(
        db,
        action="knowledge_rule_deactivate",
        user_id=admin_user.id,
        resource_type="rule_pattern",
        resource_id=str(item.id),
        metadata={"name": item.name},
    )
    await db.commit()
    return {"ok": True}
