import io
import hashlib
import re
from typing import Dict, List, Tuple

from docx import Document as DocxDocument
from PyPDF2 import PdfReader


def normalize_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def count_sentences(text: str) -> int:
    return len(re.findall(r"[.!?]+(?:\s|$)", text))


def split_into_chunks(text: str, max_chars: int = 1200) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return [text[:max_chars]] if text else []

    chunks: List[str] = []
    current = []
    current_len = 0

    for paragraph in paragraphs:
        p_len = len(paragraph)
        if p_len > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for i in range(0, p_len, max_chars):
                part = paragraph[i:i + max_chars]
                if part.strip():
                    chunks.append(part)
            continue

        next_len = current_len + p_len + (2 if current else 0)
        if next_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = p_len
        else:
            current.append(paragraph)
            current_len = next_len

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def build_chunk_rows(text: str, max_chars: int = 1200) -> List[Dict[str, int | str]]:
    chunks = split_into_chunks(text, max_chars=max_chars)
    rows: List[Dict[str, int | str]] = []
    for idx, chunk in enumerate(chunks):
        rows.append(
            {
                "chunk_index": idx,
                "content": chunk,
                "char_count": len(chunk),
                "word_count": count_words(chunk),
                "sentence_count": count_sentences(chunk),
            }
        )
    return rows


def extract_text_from_bytes(filename: str, payload: bytes) -> Tuple[str, str]:
    lower_name = filename.lower()

    if lower_name.endswith(".txt"):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            text = payload.decode("cp1251", errors="ignore")
        return normalize_text(text), "text/plain"

    if lower_name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(payload))
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        return normalize_text("\n".join(pages_text)), "application/pdf"

    if lower_name.endswith(".docx"):
        document = DocxDocument(io.BytesIO(payload))
        paragraphs = [p.text for p in document.paragraphs]
        return normalize_text("\n".join(paragraphs)), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    raise ValueError("Unsupported file type. Allowed: .txt, .pdf, .docx")
