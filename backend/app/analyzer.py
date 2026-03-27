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
                        {"role": "user", "content": f"Текст: {text[:3000]}"}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                }
            )
            
            if response.status_code == 200:
                content = response.json()["message"]["content"]
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            
            return {
                "is_correct": False,
                "confidence": 0.5,
                "issues": [],
                "corrected_text": text,
                "analysis": "Ошибка анализа"
            }