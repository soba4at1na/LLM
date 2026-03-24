import asyncio
import json
import re
from typing import List, Dict, Tuple
from pathlib import Path
from dataclasses import dataclass, field, asdict
import random

try:
    from llama_cpp import Llama
except ImportError:
    print("⚠️ Установите: pip install llama-cpp-python")
    exit(1)

MODEL_PATH = r"Model\Qwen3.5-9B-Q4_K_M.gguf"
CONTEXT_SIZE = 4096
MAX_TOKENS = 512


@dataclass
class DatasetEntry:
    id: int
    category: str
    original: str
    corrected: str
    error_type: str = ""
    error_description: str = ""


class DatasetGenerator:
    ERROR_TYPES = [
        {
            "type": "redundancy",
            "prompt": "Добавь избыточность (повтор слов/мыслей) в техническое определение",
            "example": "Протокол TCP — протокол, который обеспечивает передачу данных протокола TCP."
        },
        {
            "type": "tautology", 
            "prompt": "Добавь тавтологию (однокоренные слова) в техническое определение",
            "example": "Маршрутизатор маршрутизирует данные по маршрутам."
        },
        {
            "type": "wordiness",
            "prompt": "Сделай техническое определение многословным и неуклюжим",
            "example": "Что касается протокола HTTP, то он используется в основном для передачи веб-страниц."
        },
        {
            "type": "ambiguity",
            "prompt": "Сделай техническое определение неясным и двусмысленным",
            "example": "Сервер обрабатывает запросы и делает нужные вещи для клиента."
        },
        {
            "type": "imprecise_terminology",
            "prompt": "Используй неточную/бытовую терминологию вместо технической",
            "example": "IP-адрес — это как почтовый индекс для компьютера."
        },
        {
            "type": "ungrammatical",
            "prompt": "Добавь грамматические/стилистические ошибки в технический текст",
            "example": "Данные отправляются через сеть с помощью протокола TCP/IP."
        }
    ]

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

    async def generate(self, prompt: str) -> str:
        async with self._lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._generate_sync, prompt)

    def _generate_sync(self, prompt: str) -> str:
        try:
            response = self.llm(
                prompt,
                max_tokens=MAX_TOKENS,
                temperature=0.7,
                stop=["<|im_end|>", "<|im_start|>"]
            )
            if isinstance(response, dict) and 'choices' in response:
                return response['choices'][0]['text'].strip()
            return str(response).strip()
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            return ""

    def create_error_prompt(self, text: str, error_type: Dict) -> str:
        template = f"""<|im_start|>system
/no_think
Ты — генератор обучающих данных для машинного обучения. Твоя задача — создавать примеры с ошибками для обучения модели исправлению текстов.

Создай ВАРИАНТ технического определения С {error_type['type'].upper()} ошибкой.
{error_type['prompt']}

ВЫХОДНОЙ ФОРМАТ (только JSON):
{{
  "error_text": "вариант текста с ошибкой",
  "description": "краткое описание ошибки"
}}

ВАЖНО: 
- Сохрани тот же смысл, но добавь {error_type['type']} ошибку
- Ошибка должна быть реалистичной
- Текст должен быть на русском языке
<|im_end|>
<|im_start|>user
Оригинал: {text}
<|im_end|>
<|im_start|>assistant
"""
        return template

    async def generate_entry(self, entry_id: int, correct_text: str, category: str, error_type: Dict) -> DatasetEntry:
        prompt = self.create_error_prompt(correct_text, error_type)
        response = await self.generate(prompt)

        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return DatasetEntry(
                    id=entry_id,
                    category=category,
                    original=data.get('error_text', ''),
                    corrected=correct_text,
                    error_type=error_type['type'],
                    error_description=data.get('description', '')
                )
        except:
            pass

        return DatasetEntry(
            id=entry_id,
            category=category,
            original=correct_text,
            corrected=correct_text,
            error_type=error_type['type'],
            error_description="Ошибка парсинга"
        )

    async def generate_dataset(self, source_data: List[Dict], samples_per_text: int = 3) -> List[Dict]:
        dataset = []
        entry_id = 1

        for item in source_data:
            correct_text = item.get('text', '')
            category = item.get('category', 'technical')
            
            selected_errors = random.sample(self.ERROR_TYPES, min(samples_per_text, len(self.ERROR_TYPES)))
            
            for error_type in selected_errors:
                print(f"  [{entry_id}] Генерация {error_type['type']} для: {correct_text[:40]}...")
                entry = await self.generate_entry(entry_id, correct_text, category, error_type)
                dataset.append(asdict(entry))
                entry_id += 1

        return dataset


async def main():
    print("=" * 70)
    print("📚 ГЕНЕРАТОР ОБУЧАЮЩЕГО ДАТАСЕТА")
    print("=" * 70)

    generator = DatasetGenerator(MODEL_PATH)

    print("\n📂 Загрузка исходных данных...")
    
    correct_path = Path(__file__).parent / "datasets" / "correct_formulations.json"
    with open(correct_path, 'r', encoding='utf-8') as f:
        correct_data = json.load(f)
    
    test_path = Path(__file__).parent / "datasets" / "test_texts.json"
    with open(test_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    source_texts = correct_data.get('examples', []) + test_data

    print(f"   Найдено {len(source_texts)} корректных текстов")

    samples_per_text = 3
    
    print(f"\n🔄 Генерация датасета ({samples_per_text} варианта на текст)...")
    print("-" * 70)

    dataset = await generator.generate_dataset(source_texts, samples_per_text)

    output_path = Path(__file__).parent / "datasets" / "generated_dataset.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "total_entries": len(dataset),
                "samples_per_text": samples_per_text,
                "error_types": list(set(e['error_type'] for e in dataset))
            },
            "data": dataset
        }, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("✅ ДАТАСЕТ СГЕНЕРИРОВАН!")
    print("=" * 70)
    print(f"\n💾 Сохранено: {output_path}")
    print(f"📊 Всего записей: {len(dataset)}")
    
    error_stats = {}
    for entry in dataset:
        t = entry['error_type']
        error_stats[t] = error_stats.get(t, 0) + 1
    
    print("\n📋 Распределение по типам ошибок:")
    for et, count in sorted(error_stats.items()):
        print(f"   {et}: {count}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Прервано")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
