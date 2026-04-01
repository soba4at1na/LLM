# backend/app/api/analyze.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import re

from app.utils.auth import get_current_active_user
from app.models.user import User
from app.core.llm_service import llm_service

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Текст документа для анализа")


class AnalyzeResponse(BaseModel):
    overall_score: int
    readability_score: int
    grammar_score: int
    structure_score: int
    issues: List[str]
    recommendations: List[str]
    summary: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Анализ качества документа с помощью LLM"""
    
    if not llm_service.is_initialized:
        # Если LLM отключена — возвращаем демо-данные
        return get_mock_analysis(request.text)
    
    # Промпт для анализа
    prompt = f"""Проанализируй следующий документ и оцени его качество по шкале от 0 до 100.

Текст документа:
---
{request.text[:3000]}  # Ограничиваем длину
---

Верни ответ ТОЛЬКО в формате JSON:
{{
    "overall_score": 85,
    "readability_score": 80,
    "grammar_score": 90,
    "structure_score": 85,
    "issues": ["Проблема 1", "Проблема 2"],
    "recommendations": ["Рекомендация 1", "Рекомендация 2"],
    "summary": "Краткое резюме анализа"
}}

Будь критичен, но конструктивен. Найди реальные проблемы в тексте."""

    try:
        result = llm_service.generate(prompt, max_tokens=1000, temperature=0.3)
        
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Парсим JSON из ответа
        import json
        content = result.get("content", "")
        
        # Пытаемся найти JSON в ответе
        import re
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = json.loads(content)
        
        return AnalyzeResponse(**analysis)
        
    except Exception as e:
        # При ошибке возвращаем мок
        return get_mock_analysis(request.text)


def get_mock_analysis(text: str) -> AnalyzeResponse:
    """Демо-анализ для тестирования без LLM"""
    
    word_count = len(text.split())
    sentence_count = len(re.findall(r'[.!?]', text))
    avg_sentence_length = word_count / max(sentence_count, 1)
    
    # Простая эвристика
    readability = min(100, max(0, 100 - abs(avg_sentence_length - 20) * 3))
    grammar = min(100, max(0, 95 - text.count('  ') * 5))  # Двойные пробелы
    structure = min(100, max(0, 80 + (text.count('\n') > 5) * 20))
    overall = int((readability + grammar + structure) / 3)
    
    issues = []
    recommendations = []
    
    if avg_sentence_length > 25:
        issues.append("Предложения слишком длинные (в среднем {:.0f} слов)".format(avg_sentence_length))
        recommendations.append("Разбейте длинные предложения на более короткие")
    
    if text.count('  ') > 0:
        issues.append("Найдены двойные пробелы")
        recommendations.append("Удалите лишние пробелы")
    
    if word_count < 100:
        issues.append("Текст слишком короткий для полноценного анализа")
        recommendations.append("Добавьте больше содержания")
    
    if not issues:
        issues.append("Явных проблем не найдено")
    
    if not recommendations:
        recommendations.append("Текст соответствует базовым требованиям качества")
    
    return AnalyzeResponse(
        overall_score=overall,
        readability_score=int(readability),
        grammar_score=int(grammar),
        structure_score=int(structure),
        issues=issues,
        recommendations=recommendations,
        summary=f"Проанализировано {word_count} слов. Общее качество: {'хорошее' if overall > 70 else 'требует улучшений'}."
    )