import httpx
import json
import re
from typing import Dict, Any

class TextAnalyzer:
    def __init__(self, ollama_host: str = "http://ollama:11434"):
        self.ollama_host = ollama_host
        self.system_prompt = """Ты — строгий технический анализатор текстов.

Правила:
1. Найди ЛЮБЫЕ проблемы: тавтологию, избыточность, неясность, многословность, неточную терминологию.
2. Если есть проблема — is_correct = false.
3. Только идеально чистые тексты получают is_correct = true.

Формат ответа (ТОЛЬКО JSON):
{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "issues": [{"type": "...", "description": "...", "suggestion": "..."}],
  "corrected_text": "...",
  "analysis": "..."
}"""

    async def analyze(self, text: str, model: str = "qwen2.5:7b") -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_host}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Текст: {text[:2000]}"}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_ctx": 4096
                    }
                }
            )
            
            if response.status_code == 200:
                content = response.json()["message"]["content"]
                
                # Очищаем ответ от markdown
                content = re.sub(r'```json\s*', '', content)
                content = re.sub(r'```\s*', '', content)
                
                # Ищем JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    # Удаляем невалидные символы
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Ошибка парсинга JSON: {e}")
                        print(f"Проблемный JSON: {json_str[:200]}")
                        # Возвращаем fallback
                        return {
                            "is_correct": False,
                            "confidence": 0.5,
                            "issues": [],
                            "corrected_text": text,
                            "analysis": f"Ошибка парсинга: {str(e)[:100]}"
                        }
            
            return {
                "is_correct": False,
                "confidence": 0.5,
                "issues": [],
                "corrected_text": text,
                "analysis": "Ошибка ответа модели"
            }