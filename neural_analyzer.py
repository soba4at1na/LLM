import asyncio
import json
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass, field
from pathlib import Path

try:
    from llama_cpp import Llama
except ImportError:
    print("⚠️ Установите библиотеку: pip install llama-cpp-python")
    exit(1)

MODEL_PATH = r"C:\Model\Qwen3.5-9B-Q4_K_M.gguf"
CONTEXT_SIZE = 4096
MAX_TOKENS = 512


@dataclass
class TextAnalysis:
    id: int
    original_text: str
    is_correct: bool = False
    confidence: float = 0.0
    issues: List[Dict] = field(default_factory=list)
    corrected_text: str = ""
    analysis: str = ""


def create_analysis_prompt() -> str:
    return """<|im_start|>system
/no_think
Ты — технический аналитик ИТ-документации. Анализируй технические тексты (определения, документация, спецификации) на наличие проблем.

ТИПЫ ПРОБЛЕМ:
- redundancy: избыточность (повтор слов/мыслей)
- tautology: тавтология (однокоренные слова)
- ambiguity: неясность/двусмысленность
- wordiness: многословность
- imprecise_terminology: неточная терминология
- grammatical: грамматическая ошибка

Формат ответа (JSON):
{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "issues": [
    {
      "type": "тип проблемы",
      "position": "где в тексте",
      "description": "описание проблемы",
      "suggestion": "конкретное исправление"
    }
  ],
  "corrected_text": "исправленный вариант всего текста",
  "analysis": "краткий технический комментарий (1-2 предложения)"
}<|im_end|>
<|im_start|>user
Проанализируй технический текст:

"""


class ThreadSafeLLMClient:
    def __init__(self, model_path: str, n_ctx: int = CONTEXT_SIZE):
        print(f"🚀 Загрузка модели: {model_path}...")
        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=0,
            n_ctx=n_ctx,
            verbose=False
        )
        self._lock = asyncio.Lock()

    async def generate(self, prompt: str) -> str:
        async with self._lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._generate_sync, prompt)

    def _generate_sync(self, prompt: str) -> str:
        try:
            response = self.llm(
                prompt,
                max_tokens=MAX_TOKENS,
                temperature=0.1,
                stop=["<|im_end|>", "<|im_start|>"]
            )
            if isinstance(response, dict) and 'choices' in response:
                return response['choices'][0]['text'].strip()
            return str(response).strip()
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            return ""


class TechnicalTextAnalyzer:
    def __init__(self, llm_client: ThreadSafeLLMClient):
        self.llm = llm_client
        self.prompt_template = create_analysis_prompt()

    async def analyze_text(self, text_id: int, text: str) -> TextAnalysis:
        result = TextAnalysis(id=text_id, original_text=text)
        
        prompt = self.prompt_template + text + "<|im_end|>\n<|im_start|>assistant\n"
        
        try:
            response = await self.llm.generate(prompt)
            
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                result.is_correct = data.get('is_correct', False)
                result.confidence = data.get('confidence', 0.0)
                result.issues = data.get('issues', [])
                result.corrected_text = data.get('corrected_text', '')
                result.analysis = data.get('analysis', '')
            else:
                result.is_correct = True
                result.confidence = 0.5
                result.analysis = response[:200]

        except Exception as e:
            print(f"⚠️ Ошибка анализа текста {text_id}: {e}")

        return result


def print_statistics(results: List[TextAnalysis]):
    total = len(results)
    correct = sum(1 for r in results if r.is_correct)
    problematic = total - correct
    
    issue_types: Dict[str, int] = {}
    for r in results:
        for issue in r.issues:
            t = issue.get('type', 'unknown')
            issue_types[t] = issue_types.get(t, 0) + 1

    print("\n" + "=" * 70)
    print("📊 СТАТИСТИКА АНАЛИЗА")
    print("=" * 70)
    print(f"\n{'─' * 70}")
    print(f"  📁 Всего текстов:     {total}")
    print(f"  ✅ Корректных:        {correct} ({correct/total*100:.1f}%)")
    print(f"  ⚠️  С проблемами:      {problematic} ({problematic/total*100:.1f}%)")
    print(f"{'─' * 70}")
    
    if issue_types:
        print("\n  📋 ТИПЫ ПРОБЛЕМ:")
        print(f"  {'─' * 70}")
        for issue_type, count in sorted(issue_types.items(), key=lambda x: -x[1]):
            bar = "█" * count
            print(f"    {issue_type:<25} {bar} {count}")
    
    print(f"\n{'─' * 70}")
    print(f"  📈 Средняя уверенность: {sum(r.confidence for r in results)/total:.2f}")
    print(f"{'─' * 70}")


def print_detailed_results(results: List[TextAnalysis]):
    print("\n" + "=" * 70)
    print("📋 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 70)

    for r in results:
        status = "✅" if r.is_correct else "⚠️"
        print(f"\n{status} [{r.id}] {r.original_text[:60]}...")
        print(f"    Уверенность: {r.confidence:.2f}")
        
        if r.issues:
            print(f"    Проблемы:")
            for issue in r.issues:
                print(f"      • [{issue.get('type', '?')}] {issue.get('description', '')}")
                if issue.get('suggestion'):
                    print(f"        → {issue.get('suggestion')}")
        
        if r.corrected_text and not r.is_correct:
            print(f"    💡 Исправление:")
            print(f"       {r.corrected_text[:80]}...")
        
        if r.analysis:
            print(f"    📝 {r.analysis[:80]}...")


async def main():
    config = {
        "model_path": MODEL_PATH,
        "n_ctx": CONTEXT_SIZE
    }

    print("=" * 70)
    print("🔬 ТЕХНИЧЕСКИЙ АНАЛИЗАТОР ТЕКСТОВ")
    print("=" * 70)

    llm_client = ThreadSafeLLMClient(config['model_path'], config['n_ctx'])
    analyzer = TechnicalTextAnalyzer(llm_client)

    texts_path = Path(__file__).parent / "datasets" / "test_texts.json"
    with open(texts_path, 'r', encoding='utf-8') as f:
        texts_data = json.load(f)

    print(f"\n📂 Загружено {len(texts_data)} технических текстов")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    results: List[TextAnalysis] = []
    
    for i, item in enumerate(texts_data):
        print(f"📝 [{i + 1}/{len(texts_data)}] Анализ: {item['text'][:50]}...")
        result = await analyzer.analyze_text(item['id'], item['text'])
        results.append(result)

    print_statistics(results)
    print_detailed_results(results)

    output_path = Path(__file__).parent / "analysis_results.json"
    output_data = {
        "summary": {
            "total": len(results),
            "correct": sum(1 for r in results if r.is_correct),
            "problematic": sum(1 for r in results if not r.is_correct),
            "avg_confidence": sum(r.confidence for r in results) / len(results)
        },
        "results": [
            {
                "id": r.id,
                "original": r.original_text,
                "is_correct": r.is_correct,
                "confidence": r.confidence,
                "issues": r.issues,
                "corrected": r.corrected_text,
                "analysis": r.analysis
            }
            for r in results
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в: {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc(

        )
