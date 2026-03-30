import re
from pathlib import Path
from typing import Tuple, List

def count_words(text: str) -> int:
    return len(re.findall(r'\b\w+\b', text))

def split_into_chunks(text: str, max_tokens: int = 3000) -> List[str]:
    """Разбивает длинный текст на чанки для анализа"""
    # Простая реализация по предложениям
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence.split())
        if current_length + sentence_len > max_tokens and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_len
        else:
            current_chunk.append(sentence)
            current_length += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

async def extract_text_from_file(file_path: Path) -> Tuple[str, str]:
    """Извлекает текст из PDF или DOCX (заглушка пока)"""
    suffix = file_path.suffix.lower()
    
    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8"), "text/plain"
    
    # TODO: добавить pymupdf4llm для PDF и python-docx для DOCX
    elif suffix == ".pdf":
        # Пока просто возвращаем имя файла как заглушку
        return f"[PDF content from {file_path.name}]", "application/pdf"
    
    elif suffix in [".docx", ".doc"]:
        return f"[DOCX content from {file_path.name}]", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    else:
        raise ValueError(f"Unsupported file type: {suffix}")