import io
import hashlib
import os
import re
import subprocess
import tempfile
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
        candidates: List[str] = []
        for encoding in ("utf-8-sig", "utf-16", "cp1251", "latin-1"):
            try:
                candidates.append(payload.decode(encoding))
            except UnicodeDecodeError:
                continue
        if not candidates:
            candidates.append(payload.decode("utf-8", errors="ignore"))
        text = max(candidates, key=_text_quality_score, default="")
        return normalize_text(text), "text/plain"

    if lower_name.endswith(".pdf"):
        candidates: List[str] = []

        # Strategy 1: PyPDF2 (fast baseline)
        try:
            reader = PdfReader(io.BytesIO(payload))
            pages_text = []
            for page in reader.pages:
                pages_text.append(page.extract_text() or "")
            candidates.append("\n".join(pages_text))
        except Exception:
            pass

        # Strategy 2: pdfplumber (better for some Cyrillic PDFs)
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(io.BytesIO(payload)) as pdf:
                pages_text = [(page.extract_text() or "") for page in pdf.pages]
            candidates.append("\n".join(pages_text))
        except Exception:
            pass

        # Strategy 3: pdftotext CLI if available in container/host
        tmp_in = None
        tmp_out = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f_in:
                f_in.write(payload)
                tmp_in = f_in.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f_out:
                tmp_out = f_out.name
            result = subprocess.run(
                ["pdftotext", "-enc", "UTF-8", "-layout", tmp_in, tmp_out],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            if result.returncode == 0 and tmp_out and os.path.exists(tmp_out):
                with open(tmp_out, "r", encoding="utf-8", errors="ignore") as f_txt:
                    candidates.append(f_txt.read())
        except Exception:
            pass
        finally:
            if tmp_in and os.path.exists(tmp_in):
                os.unlink(tmp_in)
            if tmp_out and os.path.exists(tmp_out):
                os.unlink(tmp_out)

        best = max(candidates, key=_text_quality_score, default="")
        normalized = normalize_text(best)
        if not normalized:
            raise ValueError("Could not extract text from PDF")
        return normalized, "application/pdf"

    if lower_name.endswith(".docx"):
        document = DocxDocument(io.BytesIO(payload))
        paragraphs = [p.text for p in document.paragraphs]
        return normalize_text("\n".join(paragraphs)), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    raise ValueError("Unsupported file type. Allowed: .txt, .pdf, .docx")


def _text_quality_score(text: str) -> float:
    value = str(text or "")
    if not value:
        return 0.0

    total = len(value)
    if total == 0:
        return 0.0

    readable = 0
    bad = 0
    for ch in value:
        code = ord(ch)
        if ch.isalnum() or ch.isspace() or ch in ".,;:!?()[]{}\"'«»-—–/\\_%@#*+=":
            readable += 1
        # Box-drawing / block characters often indicate mojibake in Cyrillic
        if (0x2500 <= code <= 0x259F) or ch in {"�", "\x00"}:
            bad += 1

    readable_ratio = readable / total
    bad_ratio = bad / total
    return readable_ratio - bad_ratio * 2.0
