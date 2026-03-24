import json
from typing import List, Dict, Tuple
from pathlib import Path
from dataclasses import dataclass
import re
from collections import Counter


@dataclass
class TextMetrics:
    text: str
    word_count: int
    char_count: int
    avg_word_length: float
    unique_words_ratio: float
    has_tautology: bool
    has_redundancy: bool
    has_long_words: bool
    readability_score: float


def count_syllables(word: str) -> int:
    word = word.lower()
    vowels = 'аеёиоуыэюя'
    count = sum(1 for c in word if c in vowels)
    return max(1, count)


def calculate_readability(text: str) -> float:
    words = text.split()
    if not words:
        return 0
    
    total_syllables = sum(count_syllables(w) for w in words)
    avg_syllables_per_word = total_syllables / len(words)
    avg_words_per_sentence = len(words) / max(1, text.count('.') + text.count('!') + text.count('?'))
    
    score = 206.835 - (1.3 * avg_words_per_sentence) - (60.1 * avg_syllables_per_word)
    return max(0, min(100, score))


def check_tautology(text: str) -> bool:
    words = re.findall(r'\b\w+\b', text.lower())
    word_set = set(words)
    
    for word in word_set:
        for other in word_set:
            if word != other and (word in other or other in word):
                if len(word) > 3:
                    return True
    return False


def check_redundancy(text: str) -> bool:
    words = text.lower().split()
    word_counts = Counter(words)
    
    for word, count in word_counts.items():
        if count > 2 and len(word) > 4:
            return True
    return False


def calculate_text_metrics(text: str) -> TextMetrics:
    words = text.split()
    word_count = len(words)
    char_count = len(text)
    avg_word_length = char_count / word_count if word_count else 0
    
    unique_ratio = len(set(words)) / word_count if word_count else 0
    
    has_tautology = check_tautology(text)
    has_redundancy = check_redundancy(text)
    has_long_words = any(len(w) > 15 for w in words)
    
    readability = calculate_readability(text)
    
    return TextMetrics(
        text=text,
        word_count=word_count,
        char_count=char_count,
        avg_word_length=avg_word_length,
        unique_words_ratio=unique_ratio,
        has_tautology=has_tautology,
        has_redundancy=has_redundancy,
        has_long_words=has_long_words,
        readability_score=readability
    )


def compare_texts(original: str, corrected: str) -> Dict:
    metrics_orig = calculate_text_metrics(original)
    metrics_corr = calculate_text_metrics(corrected)
    
    word_diff = metrics_orig.word_count - metrics_corr.word_count
    char_diff = metrics_orig.char_count - metrics_corr.char_count
    
    improvements = []
    issues = []
    
    if metrics_orig.has_tautology and not metrics_corr.has_tautology:
        improvements.append("Устранена тавтология")
    elif metrics_orig.has_tautology:
        issues.append("Тавтология не исправлена")
    
    if metrics_orig.has_redundancy and not metrics_corr.has_redundancy:
        improvements.append("Устранена избыточность")
    elif metrics_orig.has_redundancy:
        issues.append("Избыточность не исправлена")
    
    if word_diff > 3:
        improvements.append(f"Сокращено на {word_diff} слов")
    elif word_diff < -3:
        issues.append(f"Увеличено на {abs(word_diff)} слов")
    
    if metrics_orig.readability_score < metrics_corr.readability_score:
        improvements.append("Улучшена читаемость")
    
    return {
        "original_metrics": {
            "word_count": metrics_orig.word_count,
            "char_count": metrics_orig.char_count,
            "avg_word_length": round(metrics_orig.avg_word_length, 2),
            "unique_ratio": round(metrics_orig.unique_words_ratio, 2),
            "readability": round(metrics_orig.readability_score, 2),
            "has_tautology": metrics_orig.has_tautology,
            "has_redundancy": metrics_orig.has_redundancy
        },
        "corrected_metrics": {
            "word_count": metrics_corr.word_count,
            "char_count": metrics_corr.char_count,
            "avg_word_length": round(metrics_corr.avg_word_length, 2),
            "unique_ratio": round(metrics_corr.unique_words_ratio, 2),
            "readability": round(metrics_corr.readability_score, 2),
            "has_tautology": metrics_corr.has_tautology,
            "has_redundancy": metrics_corr.has_redundancy
        },
        "differences": {
            "word_diff": word_diff,
            "char_diff": char_diff
        },
        "improvements": improvements,
        "issues": issues
    }


def analyze_dataset(input_path: Path) -> Dict:
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    entries = data.get('data', data.get('entries', []))
    
    results = []
    stats = {
        'total': len(entries),
        'improvements_found': 0,
        'issues_found': 0,
        'by_error_type': {}
    }
    
    print("\n" + "=" * 70)
    print("📊 АВТОМАТИЧЕСКИЙ АНАЛИЗ ДАТАСЕТА")
    print("=" * 70)
    
    for entry in entries:
        comparison = compare_texts(entry['original'], entry['corrected'])
        results.append({
            'id': entry['id'],
            'error_type': entry['error_type'],
            **comparison
        })
        
        stats['improvements_found'] += len(comparison['improvements'])
        stats['issues_found'] += len(comparison['issues'])
        
        et = entry['error_type']
        if et not in stats['by_error_type']:
            stats['by_error_type'][et] = {'total': 0, 'improvements': 0}
        stats['by_error_type'][et]['total'] += 1
        stats['by_error_type'][et]['improvements'] += len(comparison['improvements'])
    
    print(f"\n{'─' * 70}")
    print(f"  📁 Всего записей:         {stats['total']}")
    print(f"  ✅ Улучшений найдено:     {stats['improvements_found']}")
    print(f"  ⚠️  Проблем осталось:       {stats['issues_found']}")
    print(f"{'─' * 70}")
    
    print("\n  📋 ПО ТИПАМ ОШИБОК:")
    print(f"  {'─' * 70}")
    print(f"  {'Тип ошибки':<25} {'Всего':<8} {'Улучшений':<12} {'Эффект'}")
    print(f"  {'─' * 70}")
    
    for et, s in sorted(stats['by_error_type'].items()):
        effect = "✅" if s['improvements'] > 0 else "⚠️"
        print(f"  {et:<25} {s['total']:<8} {s['improvements']:<12} {effect}")
    
    print(f"{'─' * 70}")
    
    if results:
        avg_word_diff = sum(r['differences']['word_diff'] for r in results) / len(results)
        print(f"\n  📈 Среднее изменение длины: {avg_word_diff:+.1f} слов")
        
        readability_avg_orig = sum(r['original_metrics']['readability'] for r in results) / len(results)
        readability_avg_corr = sum(r['corrected_metrics']['readability'] for r in results) / len(results)
        print(f"  📖 Средняя читаемость:    {readability_avg_orig:.1f} → {readability_avg_corr:.1f}")
    
    return {'stats': stats, 'results': results}


def main():
    dataset_path = Path(__file__).parent / "datasets" / "generated_dataset.json"
    
    if not dataset_path.exists():
        print(f"❌ Датасет не найден: {dataset_path}")
        print("   Сначала запустите dataset_generator.py")
        return
    
    result = analyze_dataset(dataset_path)
    
    output_path = Path(__file__).parent / "datasets" / "metrics_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Детали сохранены: {output_path}")


if __name__ == "__main__":
    main()
