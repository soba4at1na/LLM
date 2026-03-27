import requests
import json
import re
from pathlib import Path
from typing import List, Dict, Any

class OllamaAnalyzer:
    def __init__(self, model="qwen2.5:7b", host="http://localhost:11434"):
        self.model = model
        self.host = host
        self.system_prompt = """Ты — технический анализатор текстов. Отвечай ТОЛЬКО JSON, без пояснений.

Формат:
{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "issues": [],
  "corrected_text": "текст",
  "analysis": "комментарий"
}

Пример:
Text: Протокол TCP обеспечивает надежную доставку данных.
Response: {"is_correct": true, "confidence": 0.95, "issues": [], "corrected_text": "Протокол TCP обеспечивает надежную доставку данных.", "analysis": "Текст корректен"}

Теперь анализируй текст и возвращай ТОЛЬКО JSON."""
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Анализирует текст и возвращает результат в виде словаря"""
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
                        "top_p": 0.9,
                        "num_ctx": 8192
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                content = response.json()["message"]["content"]
                # Извлекаем JSON из ответа
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Ошибка парсинга JSON: {e}")
                        return self._fallback_result(text, content[:200])
                else:
                    return self._fallback_result(text, content[:200])
            else:
                return self._fallback_result(text, f"API error: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Ошибка подключения: {e}")
            return self._fallback_result(text, str(e))
    
    def _fallback_result(self, text: str, error_msg: str) -> Dict[str, Any]:
        """Возвращает результат по умолчанию при ошибке"""
        return {
            "is_correct": False,
            "confidence": 0.5,
            "issues": [],
            "corrected_text": text,
            "analysis": f"Ошибка: {error_msg[:100]}"
        }


def analyze_texts(texts_data: List[Dict]) -> List[Dict]:
    """Анализирует список текстов"""
    analyzer = OllamaAnalyzer()
    results = []
    
    for i, item in enumerate(texts_data):
        text = item.get('text', '')
        print(f"📝 [{i+1}/{len(texts_data)}] Анализ: {text[:50]}...")
        
        result = analyzer.analyze_text(text)
        result['id'] = item.get('id', i)
        result['original_text'] = text
        results.append(result)
        
        # Выводим статус
        status = "✅" if result.get('is_correct') else "⚠️"
        print(f"   {status} Уверенность: {result.get('confidence', 0):.2f}")
    
    return results


def print_statistics(results: List[Dict]):
    """Выводит статистику анализа"""
    total = len(results)
    correct = sum(1 for r in results if r.get('is_correct', False))
    
    print("\n" + "=" * 70)
    print("📊 СТАТИСТИКА АНАЛИЗА")
    print("=" * 70)
    print(f"  📁 Всего текстов:     {total}")
    print(f"  ✅ Корректных:        {correct} ({correct/total*100:.1f}%)")
    print(f"  ⚠️  С проблемами:      {total-correct} ({(total-correct)/total*100:.1f}%)")
    
    # Собираем статистику по типам проблем
    issue_stats = {}
    for r in results:
        issues = r.get('issues', [])
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict):
                    issue_type = issue.get('type', 'unknown')
                    issue_stats[issue_type] = issue_stats.get(issue_type, 0) + 1
                elif isinstance(issue, str):
                    issue_stats[issue] = issue_stats.get(issue, 0) + 1
        elif isinstance(issues, str):
            issue_stats[issues] = issue_stats.get(issues, 0) + 1
    
    if issue_stats:
        print("\n  📋 Типы проблем:")
        for issue_type, count in sorted(issue_stats.items(), key=lambda x: -x[1]):
            print(f"    {issue_type}: {count}")


def main():
    print("=" * 70)
    print("🔬 ТЕХНИЧЕСКИЙ АНАЛИЗАТОР ТЕКСТОВ (Ollama)")
    print("=" * 70)
    
    # Проверка доступности Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code != 200:
            print("⚠️ Ollama не доступен. Запустите контейнер:")
            print("   docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama")
            return
        models = response.json().get('models', [])
        print(f"✅ Ollama доступен. Модели: {[m['name'] for m in models]}")
    except Exception as e:
        print(f"⚠️ Не удалось подключиться к Ollama: {e}")
        return
    
    # Загружаем тестовые тексты
    texts_path = Path(__file__).parent / "datasets" / "test_texts.json"
    if not texts_path.exists():
        print(f"⚠️ Файл {texts_path} не найден")
        return
    
    with open(texts_path, 'r', encoding='utf-8') as f:
        texts_data = json.load(f)
    
    print(f"\n📂 Загружено {len(texts_data)} технических текстов")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Анализируем тексты
    results = analyze_texts(texts_data)
    
    # Выводим статистику
    print_statistics(results)
    
    # Сохраняем результаты
    output_path = Path(__file__).parent / "analysis_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в: {output_path}")


if __name__ == "__main__":
    main()