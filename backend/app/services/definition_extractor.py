import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeImportCandidate, SourceReference
from app.core.llm_service import llm_service
TERM_BANNED_PREFIXES = (
    "это ",
    "вопрос ",
    "задача ",
    "пример ",
    "когда ",
    "если ",
    "чтобы ",
    "почему ",
    "как ",
    "где ",
)
TERM_BANNED_SUBSTRINGS = (
    "grep",
    "select ",
    "insert ",
    "update ",
    "delete ",
    " from ",
    " where ",
    "*.log",
    "postgresql",
)


def _normalize_term(value: str) -> str:
    return " ".join(str(value or "").lower().strip().split())


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()


def _is_good_term(value: str) -> bool:
    term = _clean_text(value)
    if len(term) < 2 or len(term) > 120:
        return False
    if len(term.split()) > 6:
        return False
    if not re.search(r"[A-Za-zА-Яа-яЁё0-9]", term):
        return False
    if re.search(r"[{}[\]<>@#$%^&*_=+|~`\\]", term):
        return False
    lowered = term.lower()
    if any(lowered.startswith(prefix) for prefix in TERM_BANNED_PREFIXES):
        return False
    if any(bad in lowered for bad in TERM_BANNED_SUBSTRINGS):
        return False
    if re.search(r"\b(E|e)\s+[\"'`].+[\"'`]", term):
        return False
    return True


def _is_good_definition(value: str) -> bool:
    definition = _clean_text(value)
    if len(definition) < 20 or len(definition) > 800:
        return False
    if len(definition.split()) < 4:
        return False
    lowered = definition.lower()
    if "вопрос" in lowered and "логик" in lowered:
        return False
    if re.search(r"postgresql-.*\.log", lowered):
        return False
    return True


def extract_definition_candidates(text: str, max_items: int = 60) -> list[dict[str, str]]:
    raw = str(text or "")
    if not raw.strip():
        return []

    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    line_patterns = [
        re.compile(
            r"^\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9()\"'«»\-/\s]{1,100}?)\s*[—–-]\s*(?:это\s+)?(.+?)\s*$",
            flags=re.UNICODE,
        ),
        re.compile(
            r"^\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9()\"'«»\-/\s]{1,100}?)\s+(?:это|означает|понимается\s+как)\s+(.+?)\s*$",
            flags=re.IGNORECASE | re.UNICODE,
        ),
    ]

    for line in raw.split("\n"):
        cleaned_line = line.strip(" \t*•;")
        if not cleaned_line:
            continue
        for pattern in line_patterns:
            match = pattern.match(cleaned_line)
            if not match:
                continue
            term = _clean_text(match.group(1))
            definition = _clean_text(match.group(2)).rstrip(" .;:")
            if len(definition) > 260:
                continue
            if not _is_good_term(term) or not _is_good_definition(definition):
                continue
            key = _normalize_term(term)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"term": term, "canonical_definition": definition})
            if len(candidates) >= max_items:
                return candidates
            break

    inline_pattern = re.compile(
        r"(?<!\w)([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9()\"'«»\-/\s]{1,80}?)\s*(?:—|–|-|:)?\s*(?:это|означает|понимается\s+как)\s+([^.!?\n]{20,320})",
        flags=re.IGNORECASE | re.UNICODE,
    )
    for match in inline_pattern.finditer(raw):
        term = _clean_text(match.group(1))
        definition = _clean_text(match.group(2)).rstrip(" .;:")
        if not _is_good_term(term) or not _is_good_definition(definition):
            continue
        key = _normalize_term(term)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"term": term, "canonical_definition": definition})
        if len(candidates) >= max_items:
            break

    return candidates


def _parse_llm_verdict(raw: str) -> str:
    value = str(raw or "").strip().upper()
    if not value:
        return "UNKNOWN"
    if "REJECT" in value or "ОТКЛОН" in value:
        return "REJECT"
    if "ACCEPT" in value or "ПРИНЯТ" in value:
        return "ACCEPT"
    first_line = value.splitlines()[0] if value.splitlines() else value
    if first_line.startswith("A"):
        return "ACCEPT"
    if first_line.startswith("R"):
        return "REJECT"
    return "UNKNOWN"


async def _llm_validate_candidate(term: str, definition: str) -> tuple[bool, str]:
    if not llm_service.is_initialized:
        return True, "medium"

    prompt = (
        "Ты валидируешь кандидат-термин для корпоративной базы знаний.\n"
        "Ответь строго одним словом: ACCEPT или REJECT.\n"
        "Критерии REJECT:\n"
        "- обрывок фразы, мусор OCR, служебные символы, фрагмент формулы;\n"
        "- термин не является самостоятельным понятием;\n"
        "- термин начинается/заканчивается союзами, предлогами, скобочными хвостами.\n"
        "Критерии ACCEPT:\n"
        "- самостоятельный термин/понятие;\n"
        "- определение завершено и предметно.\n\n"
        f"TERM: {term}\n"
        f"DEFINITION: {definition}\n"
    )
    response = await llm_service.generate_async(
        prompt,
        max_tokens=8,
        temperature=0.0,
        top_p=0.1,
    )
    verdict = _parse_llm_verdict(response.get("content", ""))
    if verdict == "REJECT":
        return False, "low"
    if verdict == "ACCEPT":
        return True, "high"
    return True, "medium"


async def stage_definitions_from_training_document(
    db: AsyncSession,
    *,
    document_id: int,
    filename: str,
    text: str,
    max_terms: int = 60,
) -> dict[str, Any]:
    candidates = extract_definition_candidates(text, max_items=max_terms)
    if not candidates:
        return {"source_id": None, "detected": 0, "staged": 0}

    source_key = f"document:{int(document_id)}"
    source = await db.scalar(
        select(SourceReference).where(SourceReference.url_or_local_path == source_key)
    )
    if not source:
        source = SourceReference(
            title=str(filename or f"training_document_{document_id}").strip()[:255],
            section="Автоимпорт определений",
            reference_code=f"DOC-{int(document_id)}",
            url_or_local_path=source_key,
            note="Источник создан автоматически из training-документа.",
            is_active=True,
        )
        db.add(source)
        await db.flush()

    # Rebuild draft candidates for the source on each document re-upload.
    existing_candidates = (
        await db.execute(
            select(KnowledgeImportCandidate).where(KnowledgeImportCandidate.source_ref_id == source.id)
        )
    ).scalars().all()
    for row in existing_candidates:
        await db.delete(row)

    staged = 0
    llm_rejected = 0
    for candidate in candidates:
        term = str(candidate["term"]).strip()
        canonical_definition = str(candidate["canonical_definition"]).strip()
        normalized_term = _normalize_term(term)
        accept_candidate, confidence = await _llm_validate_candidate(term, canonical_definition)
        if not accept_candidate:
            llm_rejected += 1
            continue
        db.add(
            KnowledgeImportCandidate(
                source_ref_id=source.id,
                document_id=int(document_id),
                term=term,
                normalized_term=normalized_term,
                canonical_definition=canonical_definition,
                confidence=confidence,
                status="pending",
            )
        )
        staged += 1

    return {
        "source_id": int(source.id),
        "detected": len(candidates),
        "staged": staged,
        "llm_rejected": llm_rejected,
    }


async def upsert_definitions_from_training_document(
    db: AsyncSession,
    *,
    document_id: int,
    filename: str,
    text: str,
    max_terms: int = 60,
) -> dict[str, Any]:
    # Backward-compat wrapper. Training flow now stages candidates first.
    return await stage_definitions_from_training_document(
        db,
        document_id=document_id,
        filename=filename,
        text=text,
        max_terms=max_terms,
    )
