import json
import re
import asyncio
from typing import List, Dict, Tuple
from pathlib import Path
from dataclasses import dataclass
from difflib import SequenceMatcher

try:
    from llama_cpp import Llama
except ImportError:
    print("⚠️ Установите: pip install llama-cpp-python")
    exit(1)

MODEL_PATH = r"Model\Qwen3.5-9B-Q4_K_M.gguf"
CONTEXT_SIZE = 4096
MAX_TOKENS = 512


@dataclass
class ValidationResult:
    entry_id: int
    original: str
    corrected: str
    error_type: str
    predicted_error: str
    error_detected: bool
    fix_suggested: str
    match_score: float
    issues_found: List[str]


class DatasetValidator:
    def __init__(self, model_path: str):
        print(f"🚀 Загрузка модели: {model_path}...")
        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=0,
            f16=False,
            n_ctx=CONTEXT_SIZE,
            verbose=False
        )
        self._lock = asyncio.Lock()
        print("✅ Модель загружена!")

    async def validate(self, prompt: str) -> str:
        async with self._lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._validate_sync, prompt)

    def _validate_sync(self, prompt: str) -> str:
        try:
            response = self.llm(
                prompt,
                max_tokens=512,
                temperature=0.1,
                stop=["<|im_end|>", "<|im_start|>"]
            )
            if isinstance(response, dict) and 'choices' in response:
                return response['choices'][0]['text'].strip()
            return str(response).strip()
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            return ""

    def create_validation_prompt(self, original: str, error_type: str, corrected: str) -> str:
        return f"""<|im_start|>system
/no_think
Ты — валидатор обучающих данных. Проверь, есть ли в тексте указанная ошибка.

ВЫХОДНОЙ ФОРМАТ (только JSON):
{{
  "error_detected": true/false,
  "predicted_error_type": "тип ошибки который ты видишь",
  "issues": ["список найденных проблем"],
  "fix_suggestion": "как исправить",
  "match_score": 0.0-1.0 (насколько ошибка соответствует типу)
}}
<|im_end|>
<|im_start|>user
ПРОВЕРЬ ТЕКСТ: {original}

ОЖИДАЕМАЯ ОШИБКА: {error_type}

ЭТАЛОННОЕ ИСПРАВЛЕНИЕ: {corrected}
<|im_end|>
<|im_start|>assistant
"""

    async def validate_entry(self, entry: Dict) -> ValidationResult:
        prompt = self.create_validation_prompt(
            entry['original'],
            entry['error_type'],
            entry['corrected']
        )
        response = await self.validate(prompt)

        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ValidationResult(
                    entry_id=entry['id'],
                    original=entry['original'],
                    corrected=entry['corrected'],
                    error_type=entry['error_type'],
                    predicted_error=data.get('predicted_error_type', ''),
                    error_detected=data.get('error_detected', False),
                    fix_suggested=data.get('fix_suggestion', ''),
                    match_score=data.get('match_score', 0.0),
                    issues_found=data.get('issues', [])
                )
        except:
            pass

        return ValidationResult(
            entry_id=entry['id'],
            original=entry['original'],
            corrected=entry['corrected'],
            error_type=entry['error_type'],
            predicted_error='',
            error_detected=False,
            fix_suggested='',
            match_score=0.0,
            issues_found=[]
        )


def calculate_metrics(results: List[ValidationResult]) -> Dict:
    total = len(results)
    
    detected = sum(1 for r in results if r.error_detected)
    
    error_type_match = 0
    for r in results:
        if r.error_detected and r.error_type == r.predicted_error:
            error_type_match += 1
    
    avg_score = sum(r.match_score for r in results) / total if total else 0
    
    by_type = {}
    for r in results:
        t = r.error_type
        if t not in by_type:
            by_type[t] = {'total': 0, 'detected': 0, 'avg_score': 0}
        by_type[t]['total'] += 1
        if r.error_detected:
            by_type[t]['detected'] += 1
        by_type[t]['avg_score'] += r.match_score

    for t in by_type:
        by_type[t]['avg_score'] /= by_type[t]['total']
        by_type[t]['detection_rate'] = by_type[t]['detected'] / by_type[t]['total']

    return {
        'total': total,
        'detected': detected,
        'detection_rate': detected / total if total else 0,
        'error_type_accuracy': error_type_match / detected if detected else 0,
        'avg_match_score': avg_score,
        'by_error_type': by_type
    }


def print_report(results: List[ValidationResult], metrics: Dict):
    print("\n" + "=" * 70)
    print("📊 ОТЧЁТ ПО ВАЛИДАЦИИ ДАТАСЕТА")
    print("=" * 70)

    print(f"\n{'─' * 70}")
    print(f"  📁 Всего записей:              {metrics['total']}")
    print(f"  ✅ Ошибки обнаружены:          {metrics['detected']} ({metrics['detection_rate']*100:.1f}%)")
    print(f"  🎯 Точность определения типа:  {metrics['error_type_accuracy']*100:.1f}%")
    print(f"  📈 Средний match score:        {metrics['avg_match_score']:.2f}")
    print(f"{'─' * 70}")

    print("\n  📋 ПО ТИПАМ ОШИБОК:")
    print(f"  {'─' * 70}")
    print(f"  {'Тип ошибки':<25} {'Найдено':<12} {'Точность':<12} {'Score':<8}")
    print(f"  {'─' * 70}")
    
    for error_type, stats in sorted(metrics['by_error_type'].items()):
        bar_len = int(stats['detection_rate'] * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {error_type:<25} {stats['detected']}/{stats['total']:<8} {bar} {stats['detection_rate']*100:.0f}%   {stats['avg_score']:.2f}")

    print(f"{'─' * 70}")

    bad_samples = [r for r in results if not r.error_detected or r.match_score < 0.5]
    if bad_samples:
        print(f"\n  ⚠️ ПРОБЛЕМНЫЕ ПРИМЕРЫ ({len(bad_samples)}):")
        print(f"  {'─' * 70}")
        for r in bad_samples[:5]:
            print(f"\n  [{r.entry_id}] {r.error_type}")
            print(f"     Текст: {r.original[:60]}...")
            print(f"     Оценка: {r.match_score:.2f}")
    else:
        print(f"\n  ✅ Все примеры валидны!")


async def main():
    print("=" * 70)
    print("🔍 ВАЛИДАТОР СГЕНЕРИРОВАННОГО ДАТАСЕТА")
    print("=" * 70)

    validator = DatasetValidator(MODEL_PATH)

    dataset_path = Path(__file__).parent / "datasets" / "generated_dataset.json"
    
    if not dataset_path.exists():
        print(f"\n❌ Датасет не найден: {dataset_path}")
        print("   Сначала запустите dataset_generator.py")
        return

    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    data = dataset.get('data', dataset.get('entries', []))
    print(f"\n📂 Загружено {len(data)} записей")
    print("-" * 70)

    results: List[ValidationResult] = []
    
    for i, entry in enumerate(data):
        print(f"  [{i+1}/{len(data)}] Проверка: {entry['original'][:40]}...")
        result = await validator.validate_entry(entry)
        results.append(result)

    metrics = calculate_metrics(results)
    print_report(results, metrics)

    output_path = Path(__file__).parent / "datasets" / "validation_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'metrics': metrics,
            'results': [vars(r) for r in results]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Детали сохранены: {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Прервано")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
