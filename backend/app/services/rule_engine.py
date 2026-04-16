import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import GlossaryTerm, SourceReference

ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}

BUILTIN_REGEX_RULES: list[dict[str, str]] = [
    {
        "id": "double-spaces",
        "name": "Двойные пробелы",
        "rule_type": "regex",
        "pattern": r" {2,}",
        "description": "Обнаружены множественные пробелы.",
        "severity": "low",
        "suggestion_template": "Замените множественные пробелы на один.",
        "source_code": "CORP-IT-SEC-001",
        "is_active": True,
    },
    {
        "id": "many-exclamation",
        "name": "Слишком много восклицательных знаков",
        "rule_type": "regex",
        "pattern": r"!{2,}",
        "description": "Избыточная эмоциональная пунктуация неуместна в техническом документе.",
        "severity": "medium",
        "suggestion_template": "Оставьте один восклицательный знак или замените на точку.",
        "source_code": "CORP-IT-SEC-001",
        "is_active": True,
    },
    {
        "id": "capslock-fragments",
        "name": "Капслок-фрагменты",
        "rule_type": "regex",
        "pattern": r"\b[А-ЯЁ]{5,}\b",
        "description": "Найдены слова в полном верхнем регистре.",
        "severity": "low",
        "suggestion_template": "Используйте стандартный регистр, если это не официальная аббревиатура.",
        "source_code": "CORP-IT-SEC-001",
        "is_active": True,
    },
]

_DEFINITION_STOPWORDS = {
    "это",
    "как",
    "для",
    "при",
    "или",
    "также",
    "так",
    "что",
    "чтобы",
    "который",
    "которая",
    "которые",
    "над",
    "под",
    "без",
    "между",
    "через",
    "а",
    "и",
    "но",
    "по",
    "в",
    "во",
    "на",
    "с",
    "со",
    "к",
    "у",
    "о",
    "об",
}


def _normalize_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            value = str(item).strip()
            if value:
                out.append(value)
        return out
    if isinstance(raw, str):
        chunks = [chunk.strip() for chunk in raw.split(",")]
        return [chunk for chunk in chunks if chunk]
    return []


def _normalize_severity(raw: Any) -> str:
    value = str(raw or "medium").strip().lower()
    return value if value in ALLOWED_SEVERITIES else "medium"


def _source_payload(source_ref: SourceReference | None) -> dict | None:
    if source_ref is None:
        return None
    return {
        "id": int(source_ref.id),
        "title": source_ref.title,
        "section": source_ref.section,
        "reference_code": source_ref.reference_code,
        "url_or_local_path": source_ref.url_or_local_path,
    }


def _build_replacement_candidate(matched_text: str, suggestion: str) -> str | None:
    match_clean = str(matched_text or "").strip()
    sugg_clean = str(suggestion or "").strip()
    if not match_clean or not sugg_clean:
        return None

    lower = sugg_clean.lower()
    generic_prefixes = (
        "уточн",
        "проверь",
        "провести",
        "добав",
        "удал",
        "исправ",
        "использ",
        "сократ",
        "переформ",
    )
    if any(lower.startswith(prefix) for prefix in generic_prefixes):
        return None
    if len(sugg_clean) > max(220, int(len(match_clean) * 2.2)):
        return None
    return sugg_clean


def _compile_glossary_variant_pattern(phrase: str) -> str:
    tokens = [t for t in re.split(r"\s+", phrase.strip()) if t]
    if not tokens:
        return ""
    parts: list[str] = []
    for token in tokens:
        escaped = re.escape(token)
        if len(token) >= 5:
            parts.append(rf"{escaped}\w{{0,3}}")
        else:
            parts.append(escaped)
    inner = r"\s+".join(parts)
    return rf"(?<!\w){inner}(?!\w)"


def _tokenize_definition(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", str(text or "").lower(), flags=re.UNICODE)
    return {token for token in tokens if token not in _DEFINITION_STOPWORDS}


def _definition_similarity(a: str, b: str) -> float:
    ta = _tokenize_definition(a)
    tb = _tokenize_definition(b)
    if not ta or not tb:
        return 0.0
    intersection = len(ta.intersection(tb))
    denominator = len(ta.union(tb))
    if denominator <= 0:
        return 0.0
    return intersection / denominator


def _find_term_definition_matches(text: str, term: str) -> list[tuple[str, str]]:
    escaped_term = re.escape(str(term or "").strip())
    if not escaped_term:
        return []
    pattern = re.compile(
        rf"(?<!\w)({escaped_term}\s*(?:—|–|-|:)?\s*(?:это|означает|понимается\s+как)\s+([^.!?\n]{{8,320}}))",
        flags=re.IGNORECASE | re.UNICODE,
    )
    matches: list[tuple[str, str]] = []
    for match in pattern.finditer(text):
        full = str(match.group(1) or "").strip()
        definition_part = str(match.group(2) or "").strip()
        if full and definition_part:
            matches.append((full, definition_part))
    return matches


class RuleEngine:
    async def compute_policy_hash(self, db: AsyncSession) -> str:
        source_rows = (
            await db.execute(
                select(
                    SourceReference.id,
                    SourceReference.title,
                    SourceReference.section,
                    SourceReference.reference_code,
                    SourceReference.url_or_local_path,
                    SourceReference.updated_at,
                )
                .where(SourceReference.is_active.is_(True))
                .order_by(SourceReference.id)
            )
        ).all()
        glossary_rows = (
            await db.execute(
                select(
                    GlossaryTerm.id,
                    GlossaryTerm.term,
                    GlossaryTerm.normalized_term,
                    GlossaryTerm.canonical_definition,
                    GlossaryTerm.allowed_variants,
                    GlossaryTerm.forbidden_variants,
                    GlossaryTerm.category,
                    GlossaryTerm.severity_default,
                    GlossaryTerm.source_ref_id,
                    GlossaryTerm.updated_at,
                )
                .where(GlossaryTerm.is_active.is_(True))
                .order_by(GlossaryTerm.id)
            )
        ).all()

        payload = {
            "version": 2,
            "sources": [
                {
                    "id": int(row.id),
                    "title": str(row.title),
                    "section": row.section,
                    "reference_code": row.reference_code,
                    "url_or_local_path": row.url_or_local_path,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in source_rows
            ],
            "glossary": [
                {
                    "id": int(row.id),
                    "term": str(row.term),
                    "normalized_term": str(row.normalized_term),
                    "canonical_definition": str(row.canonical_definition),
                    "allowed_variants": _normalize_list(row.allowed_variants),
                    "forbidden_variants": _normalize_list(row.forbidden_variants),
                    "category": row.category,
                    "severity_default": _normalize_severity(row.severity_default),
                    "source_ref_id": int(row.source_ref_id) if row.source_ref_id else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in glossary_rows
            ],
            "patterns": BUILTIN_REGEX_RULES,
        }

        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def evaluate_text(
        self,
        db: AsyncSession,
        *,
        text: str,
        max_findings: int = 12,
    ) -> dict:
        text = text or ""
        findings: list[dict] = []
        issues: list[str] = []
        recommendations: list[str] = []
        issue_keys: set[str] = set()
        recommendation_keys: set[str] = set()

        source_rows = (
            await db.execute(
                select(SourceReference)
                .where(SourceReference.is_active.is_(True))
                .order_by(SourceReference.id)
            )
        ).scalars().all()
        source_by_code = {
            str(source.reference_code): source
            for source in source_rows
            if str(source.reference_code or "").strip()
        }

        glossary_rows = (
            await db.execute(
                select(GlossaryTerm, SourceReference)
                .outerjoin(SourceReference, SourceReference.id == GlossaryTerm.source_ref_id)
                .where(GlossaryTerm.is_active.is_(True))
                .order_by(GlossaryTerm.id)
            )
        ).all()

        for glossary, source in glossary_rows:
            term = str(glossary.term).strip()
            if not term:
                continue
            severity = _normalize_severity(glossary.severity_default)

            forbidden_variants = _normalize_list(glossary.forbidden_variants)
            for variant in forbidden_variants:
                token = variant.strip()
                if not token:
                    continue
                pattern = _compile_glossary_variant_pattern(token)
                if not pattern:
                    continue
                for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.UNICODE):
                    exact_match = match.group(0)
                    suggestion = f"Используйте термин «{term}»."
                    if glossary.canonical_definition:
                        suggestion = f"{suggestion} {str(glossary.canonical_definition).strip()}"
                    issue_text = f"Обнаружен нежелательный термин: «{exact_match}»."
                    reason = f"Термин не соответствует корпоративному глоссарию: {term}."
                    findings.append(
                        {
                            "fragment": exact_match,
                            "suggestion": suggestion,
                            "reason": reason,
                            "confidence": "high",
                            "severity": severity,
                            "source_ref": _source_payload(source),
                            "rule_origin": f"glossary:{int(glossary.id)}",
                            "replacement": term,
                        }
                    )
                    issue_key = issue_text.strip().lower()
                    rec_key = suggestion.strip().lower()
                    if issue_key not in issue_keys:
                        issues.append(issue_text)
                        issue_keys.add(issue_key)
                    if rec_key not in recommendation_keys:
                        recommendations.append(suggestion)
                        recommendation_keys.add(rec_key)
                    if len(findings) >= max_findings:
                        return {
                            "issues": issues,
                            "recommendations": recommendations,
                            "issue_details": findings,
                            "matched_count": len(findings),
                        }

            canonical_definition = str(glossary.canonical_definition or "").strip()
            if canonical_definition:
                def_matches = _find_term_definition_matches(text, term)
                for full_fragment, candidate_definition in def_matches:
                    similarity = _definition_similarity(candidate_definition, canonical_definition)
                    if similarity >= 0.20:
                        continue
                    suggestion = f"Используйте каноничное определение: {canonical_definition}"
                    issue_text = f"Неточное определение термина «{term}»."
                    reason = f"Определение расходится с эталоном из базы знаний (совпадение {int(similarity * 100)}%)."
                    findings.append(
                        {
                            "fragment": full_fragment,
                            "suggestion": suggestion,
                            "reason": reason,
                            "confidence": "medium",
                            "severity": severity,
                            "source_ref": _source_payload(source),
                            "rule_origin": f"definition:{int(glossary.id)}",
                            "replacement": f"{term} — это {canonical_definition}",
                        }
                    )
                    issue_key = issue_text.strip().lower()
                    rec_key = suggestion.strip().lower()
                    if issue_key not in issue_keys:
                        issues.append(issue_text)
                        issue_keys.add(issue_key)
                    if rec_key not in recommendation_keys:
                        recommendations.append(suggestion)
                        recommendation_keys.add(rec_key)
                    if len(findings) >= max_findings:
                        return {
                            "issues": issues,
                            "recommendations": recommendations,
                            "issue_details": findings,
                            "matched_count": len(findings),
                        }

        for idx, rule in enumerate(BUILTIN_REGEX_RULES, start=1):
            if not bool(rule.get("is_active", True)):
                continue
            try:
                compiled = re.compile(
                    str(rule.get("pattern", "")),
                    flags=re.IGNORECASE | re.MULTILINE | re.UNICODE,
                )
            except re.error:
                continue

            source = source_by_code.get(str(rule.get("source_code", "")))
            severity = _normalize_severity(rule.get("severity"))
            rule_name = str(rule.get("name") or f"builtin_rule_{idx}")
            description = str(rule.get("description") or "").strip()
            suggestion_template = str(rule.get("suggestion_template") or "").strip()

            for match in compiled.finditer(text):
                exact_match = match.group(0)
                issue_text = description or f"Сработало правило «{rule_name}»."
                suggestion = suggestion_template or "Проверьте этот фрагмент по корпоративным правилам."
                reason = f"Нарушение шаблонного правила: {rule_name}."
                findings.append(
                    {
                        "fragment": exact_match,
                        "suggestion": suggestion,
                        "reason": reason,
                        "confidence": "medium",
                        "severity": severity,
                        "source_ref": _source_payload(source),
                        "rule_origin": f"pattern:builtin:{rule.get('id', idx)}",
                        "replacement": _build_replacement_candidate(exact_match, suggestion),
                    }
                )
                issue_key = issue_text.strip().lower()
                rec_key = suggestion.strip().lower()
                if issue_key not in issue_keys:
                    issues.append(issue_text)
                    issue_keys.add(issue_key)
                if rec_key not in recommendation_keys:
                    recommendations.append(suggestion)
                    recommendation_keys.add(rec_key)
                if len(findings) >= max_findings:
                    return {
                        "issues": issues,
                        "recommendations": recommendations,
                        "issue_details": findings,
                        "matched_count": len(findings),
                    }

        return {
            "issues": issues,
            "recommendations": recommendations,
            "issue_details": findings,
            "matched_count": len(findings),
        }


rule_engine = RuleEngine()
