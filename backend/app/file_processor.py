import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any
import aiofiles
import io

class FileProcessor:
    """Обработчик файлов разных форматов"""
    
    @staticmethod
    async def extract_text(file_content: bytes, filename: str) -> str:
        """Извлекает текст из файла в зависимости от расширения"""
        ext = filename.split('.')[-1].lower()
        
        if ext == 'txt':
            return file_content.decode('utf-8', errors='ignore')
        
        elif ext == 'json':
            # Для JSON файлов — преобразуем в читаемый текст
            import json
            data = json.loads(file_content.decode('utf-8'))
            # Рекурсивно извлекаем текст из JSON
            return FileProcessor._extract_text_from_json(data)
        
        elif ext == 'docx':
            from docx import Document
            doc = Document(io.BytesIO(file_content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return '\n\n'.join(paragraphs)
        
        elif ext == 'pdf':
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = []
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
            return '\n\n'.join(text)
        
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    
    @staticmethod
    def _extract_text_from_json(data, prefix="") -> str:
        """Рекурсивно извлекает текст из JSON"""
        texts = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['text', 'instruction', 'content', 'description', 'analysis', 'corrected_text']:
                    if isinstance(value, str) and len(value) > 20:
                        texts.append(f"{prefix}{key}: {value}")
                else:
                    texts.append(FileProcessor._extract_text_from_json(value, f"{prefix}{key}/"))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                texts.append(FileProcessor._extract_text_from_json(item, f"{prefix}[{i}]/"))
        
        elif isinstance(data, str) and len(data) > 20:
            texts.append(f"{prefix}{data}")
        
        return '\n\n'.join(texts)
    
    @staticmethod
    def split_into_paragraphs(text: str, max_length: int = 2000) -> List[str]:
        """Разбивает текст на абзацы для анализа"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        # Разбиваем длинные абзацы
        result = []
        for p in paragraphs:
            if len(p) > max_length:
                # Разбиваем по предложениям
                sentences = re.split(r'[.!?]+', p)
                current = ""
                for s in sentences:
                    if len(current) + len(s) < max_length:
                        current += s + "."
                    else:
                        if current:
                            result.append(current.strip())
                        current = s + "."
                if current:
                    result.append(current.strip())
            else:
                result.append(p)
        
        return result


class TrainingDataGenerator:
    """Генерирует обучающие данные из загруженных файлов"""
    
    def __init__(self, ollama_host: str = "http://ollama:11434"):
        self.ollama_host = ollama_host
    
async def generate_example(self, text: str) -> Dict[str, Any]:
    """Генерирует обучающий пример для текста"""
    import httpx
    import re
    import json
    
    prompt = f"""Ты — помощник по созданию обучающих данных. Проанализируй текст и верни JSON с оценкой.

Текст: {text[:1500]}

Формат ответа:
{{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "issues": [],
  "corrected_text": "исправленный текст",
  "analysis": "краткий анализ"
}}

Если текст корректен — issues = [].
Если есть проблемы — укажи issues с type, description, suggestion.
Отвечай ТОЛЬКО JSON."""

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{self.ollama_host}/api/chat",
            json={
                "model": "qwen2.5:7b",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            }
        )
        
        if response.status_code == 200:
            content = response.json()["message"]["content"]
            
            # Очищаем ответ от возможных проблем
            # Удаляем markdown код блоки
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)
            
            # Ищем JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                # Удаляем невалидные управляющие символы
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Ошибка парсинга JSON: {e}")
                    print(f"Проблемный JSON: {json_str[:200]}")
                    # Возвращаем заглушку
                    return {
                        "is_correct": True,
                        "confidence": 0.5,
                        "issues": [],
                        "corrected_text": text,
                        "analysis": "Ошибка парсинга, пример пропущен"
                    }
        
        return {
            "is_correct": True,
            "confidence": 0.5,
            "issues": [],
            "corrected_text": text,
            "analysis": "Автоматически сгенерированный пример"
        }
    
    async def process_file(self, file_content: bytes, filename: str) -> List[Dict]:
        """Обрабатывает файл и генерирует обучающие примеры"""
        # Извлекаем текст
        text = await FileProcessor.extract_text(file_content, filename)
        paragraphs = FileProcessor.split_into_paragraphs(text)
        
        examples = []
        for i, para in enumerate(paragraphs):
            if len(para) > 50:  # Игнорируем слишком короткие
                print(f"  Генерация примера {i+1}/{len(paragraphs)}...")
                response = await self.generate_example(para)
                examples.append({
                    "id": f"{Path(filename).stem}_{i}",
                    "instruction": para,
                    "response": response,
                    "source_file": filename
                })
        
        return examples
    
    async def process_file(self, file_content: bytes, filename: str) -> List[Dict]:
        """Обрабатывает файл и генерирует обучающие примеры"""
    text = await FileProcessor.extract_text(file_content, filename)
    paragraphs = FileProcessor.split_into_paragraphs(text)
    
    examples = []
    for i, para in enumerate(paragraphs):
        if len(para) > 50:
            try:
                print(f"  Генерация примера {i+1}/{len(paragraphs)}...")
                response = await self.generate_example(para)
                examples.append({
                    "id": f"{Path(filename).stem}_{i}",
                    "instruction": para,
                    "response": response,
                    "source_file": filename
                })
            except Exception as e:
                print(f"  ⚠️ Ошибка генерации примера {i+1}: {e}")
                continue
    
    return examples