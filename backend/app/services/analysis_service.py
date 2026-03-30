import time
from typing import List
from app.models.analysis import TextAnalysisResponse   # AnalysisIssue больше не импортируем здесь
from app.core.llm_service import llm_service
from app.models.analysis import TextAnalysisResponse, AnalysisIssue

class AnalysisService:
    async def analyze_text(self, text: str) -> TextAnalysisResponse:
        start_time = time.time()

        # Создаём промпт (можно вынести в отдельный файл позже)
        prompt = f"""<|im_start|>system
Ты — строгий технический редактор корпоративной документации.
Анализируй текст на наличие стилистических, терминологических и логических проблем.

Верни ответ строго в формате JSON:
{{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "issues": [
    {{
      "type": "redundancy|tautology|wordiness|ambiguity|imprecise_terminology|grammatical",
      "position": "где проблема",
      "description": "описание",
      "suggestion": "как исправить"
    }}
  ],
  "corrected_text": "полностью исправленный текст",
  "analysis": "краткий вывод"
}}
<|im_end|>
<|im_start|>user
Текст для анализа:

{text}
<|im_end|>
<|im_start|>assistant
"""

        response_text = await llm_service.generate(prompt, temperature=0.1)

        # Парсинг JSON из ответа (с защитой)
        try:
            import json
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return TextAnalysisResponse(
                    is_correct=data.get("is_correct", False),
                    confidence=data.get("confidence", 0.5),
                    issues=data.get("issues", []),
                    corrected_text=data.get("corrected_text", ""),
                    analysis=data.get("analysis", "")
                )
        except Exception:
            pass

        # Fallback
        return TextAnalysisResponse(
            is_correct=True,
            confidence=0.6,
            issues=[],
            corrected_text=text,
            analysis="Не удалось разобрать ответ модели. Текст принят как корректный."
        )

analysis_service = AnalysisService()