import re
from dataclasses import dataclass
from typing import List, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_record import DocumentChunk, DocumentRecord


def _tokenize(text: str) -> Set[str]:
    tokens = re.findall(r"\b\w+\b", text.lower(), flags=re.UNICODE)
    return {t for t in tokens if len(t) >= 3}


@dataclass
class RetrievedChunk:
    document_id: int
    filename: str
    chunk_index: int
    content: str
    score: float


class RetrievalService:
    async def find_relevant_chunks(
        self,
        db: AsyncSession,
        *,
        owner_id,
        query: str,
        top_k: int = 3,
        scan_limit: int = 200,
    ) -> List[RetrievedChunk]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        rows = (
            await db.execute(
                select(
                    DocumentChunk.document_id,
                    DocumentRecord.filename,
                    DocumentChunk.chunk_index,
                    DocumentChunk.content,
                )
                .join(DocumentRecord, DocumentRecord.id == DocumentChunk.document_id)
                .where(DocumentRecord.owner_id == owner_id)
                .order_by(DocumentChunk.id.desc())
                .limit(scan_limit)
            )
        ).all()

        scored: List[RetrievedChunk] = []
        for document_id, filename, chunk_index, content in rows:
            chunk_tokens = _tokenize(content)
            if not chunk_tokens:
                continue

            overlap = len(query_tokens.intersection(chunk_tokens))
            if overlap == 0:
                continue

            score = overlap / max(len(query_tokens), 1)
            scored.append(
                RetrievedChunk(
                    document_id=int(document_id),
                    filename=str(filename),
                    chunk_index=int(chunk_index),
                    content=str(content),
                    score=float(score),
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def build_context(chunks: List[RetrievedChunk], max_chars: int = 3500) -> str:
        if not chunks:
            return ""

        lines: List[str] = []
        used = 0
        for chunk in chunks:
            block = (
                f"[document_id={chunk.document_id}; file={chunk.filename}; chunk={chunk.chunk_index}]\n"
                f"{chunk.content.strip()}\n"
            )
            if used + len(block) > max_chars:
                break
            lines.append(block)
            used += len(block)
        return "\n".join(lines).strip()


retrieval_service = RetrievalService()
