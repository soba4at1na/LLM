import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import GlossaryTerm, RulePattern, SourceReference

ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}


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


def _build_fragment(text: str, start: int, end: int, pad: int = 50) -> str:
    left = max(0, start - pad)
    right = min(len(text), end + pad)
    fragment = text[left:right].strip()
    if left > 0:
        fragment = "..." + fragment
    if right < len(text):
        fragment = fragment + "..."
    return fragment or text[max(0, start):min(len(text), end)]


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
    # More tolerant match for phrase variants:
    # - keep short tokens strict (e.g., "ip")
    # - allow small suffix drift for longer tokens (e.g., "интернет" -> "интернетю")
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
        pattern_rows = (
            await db.execute(
                select(
                    RulePattern.id,
                    RulePattern.name,
                    RulePattern.rule_type,
                    RulePattern.pattern,
                    RulePattern.description,
                    RulePattern.severity,
                    RulePattern.suggestion_template,
                    RulePattern.source_ref_id,
                    RulePattern.updated_at,
                )
                .where(RulePattern.is_active.is_(True))
                .order_by(RulePattern.id)
            )
        ).all()

        payload = {
            "version": 1,
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
            "patterns": [
                {
                    "id": int(row.id),
                    "name": str(row.name),
                    "rule_type": str(row.rule_type),
                    "pattern": str(row.pattern),
                    "description": str(row.description or ""),
                    "severity": _normalize_severity(row.severity),
                    "suggestion_template": str(row.suggestion_template or ""),
                    "source_ref_id": int(row.source_ref_id) if row.source_ref_id else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in pattern_rows
            ],
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
            if not forbidden_variants:
                continue

            for variant in forbidden_variants:
                token = variant.strip()
                if not token:
                    continue
                pattern = _compile_glossary_variant_pattern(token)
                if not pattern:
                    continue
                for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.UNICODE):
                    exact_match = match.group(0)
                    fragment = exact_match
                    suggestion = f"Используйте термин «{term}»."
                    if glossary.canonical_definition:
                        suggestion = f"{suggestion} {str(glossary.canonical_definition).strip()[:220]}"
                    issue_text = f"Обнаружен нежелательный термин: «{match.group(0)}»."
                    reason = f"Термин не соответствует корпоративному глоссарию: {term}."
                    finding = {
                        "fragment": fragment,
                        "suggestion": suggestion,
                        "reason": reason,
                        "confidence": "high",
                        "severity": severity,
                        "source_ref": _source_payload(source),
                        "rule_origin": f"glossary:{int(glossary.id)}",
                        "replacement": term,
                    }
                    findings.append(finding)
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

        pattern_rows = (
            await db.execute(
                select(RulePattern, SourceReference)
                .outerjoin(SourceReference, SourceReference.id == RulePattern.source_ref_id)
                .where(RulePattern.is_active.is_(True))
                .order_by(RulePattern.id)
            )
        ).all()

        for rule, source in pattern_rows:
            if str(rule.rule_type).lower() != "regex":
                continue
            try:
                compiled = re.compile(str(rule.pattern), flags=re.IGNORECASE | re.MULTILINE | re.UNICODE)
            except re.error:
                continue

            severity = _normalize_severity(rule.severity)
            for match in compiled.finditer(text):
                exact_match = match.group(0)
                fragment = exact_match
                issue_text = (
                    str(rule.description).strip()
                    if rule.description
                    else f"Сработало правило «{rule.name}»."
                )
                suggestion = (
                    str(rule.suggestion_template).strip()
                    if rule.suggestion_template
                    else "Проверьте этот фрагмент по корпоративным правилам и терминологии."
                )
                reason = f"Нарушение шаблонного правила: {rule.name}."
                finding = {
                    "fragment": fragment,
                    "suggestion": suggestion,
                    "reason": reason,
                    "confidence": "medium",
                    "severity": severity,
                    "source_ref": _source_payload(source),
                    "rule_origin": f"pattern:{int(rule.id)}",
                    "replacement": _build_replacement_candidate(exact_match, suggestion),
                }
                findings.append(finding)
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
