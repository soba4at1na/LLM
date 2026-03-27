import requests
import json
import re
from pathlib import Path
import os

class OllamaAnalyzer:
    def __init__(self, model="qwen2.5:7b", host=None):
        # Если в Docker, используем внутренний адрес, иначе localhost
        if host is None:
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = model
        self.host = host
        print(f"🔗 Подключение к Ollama: {self.host}")
        
        self.system_prompt = """Ты — СТРОГИЙ технический анализатор текстов. Твоя задача — находить ЛЮБЫЕ проблемы.

Проблемы, которые нужно находить:
- redundancy: избыточность (повтор слов/мыслей)
- tautology: тавтология (однокоренные слова)
- ambiguity: неясность/двусмысленность
- wordiness: многословность
- imprecise_terminology: неточная терминология
- grammatical: грамматическая ошибка

ПРАВИЛА:
1. Если текст содержит ЛЮБУЮ проблему из списка — is_correct = false
2. Только идеально чистые тексты получают is_correct = true
3. confidence должен быть высоким (0.85-0.99) для корректных, (0.7-0.95) для проблемных

Формат ответа (ТОЛЬКО JSON):
{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "issues": [...],
  "corrected_text": "...",
  "analysis": "..."
}

Будь строг. Отвечай ТОЛЬКО JSON."""
    
    def analyze_text(self, text: str):
        """Анализирует текст и возвращает результат"""
        try:
            response = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Text: {text}"}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                content = response.json()["message"]["content"]
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            return {"is_correct": False, "confidence": 0.5, "issues": [], "analysis": "Ошибка парсинга"}
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            return {"is_correct": False, "confidence": 0.5, "issues": [], "analysis": str(e)}


def main():
    print("=" * 70)
    print("🔬 ТЕХНИЧЕСКИЙ АНАЛИЗАТОР ТЕКСТОВ (Ollama)")
    print("=" * 70)
    
    # Загружаем тексты
    texts_path = Path(__file__).parent / "datasets" / "test_texts.json"
    if not texts_path.exists():
        print(f"⚠️ Файл {texts_path} не найден")
        print("📁 Поместите test_texts.json в папку datasets/")
        return
    
    with open(texts_path, 'r', encoding='utf-8') as f:
        texts_data = json.load(f)
    
    print(f"\n📂 Загружено {len(texts_data)} технических текстов")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Анализируем
    analyzer = OllamaAnalyzer()
    results = []
    
    for i, item in enumerate(texts_data):
        text = item.get('text', '')
        print(f"📝 [{i+1}/{len(texts_data)}] Анализ: {text[:50]}...")
        
        result = analyzer.analyze_text(text)
        result['id'] = item.get('id', i)
        result['original_text'] = text
        results.append(result)
        
        status = "✅" if result.get('is_correct') else "⚠️"
        print(f"   {status} Уверенность: {result.get('confidence', 0):.2f}")
    
    # Сохраняем результаты
    output_path = Path(__file__).parent / "results" / "analysis_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в: {output_path}")


if __name__ == "__main__":
    main()