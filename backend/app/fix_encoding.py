import json
import chardet

input_file = "datasets/test_texts.json"
output_file = "datasets/test_texts_fixed.json"

print("=" * 60)
print("🔧 ИСПРАВЛЕНИЕ КОДИРОВКИ И ФОРМАТА")
print("=" * 60)

# 1. Определяем текущую кодировку
with open(input_file, 'rb') as f:
    raw_data = f.read()
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    print(f"📊 Определена кодировка: {encoding}")

# 2. Читаем файл в правильной кодировке
with open(input_file, 'r', encoding=encoding) as f:
    content = f.read()

# 3. Удаляем BOM если есть
if content.startswith('\ufeff'):
    content = content[1:]
    print("🗑️ Удален BOM")

# 4. Парсим JSON
try:
    data = json.loads(content)
    print(f"✅ JSON валидный, {len(data)} записей")
except json.JSONDecodeError as e:
    print(f"⚠️ Ошибка JSON: {e}")
    exit(1)

# 5. Проверяем структуру и преобразуем
if data and isinstance(data, list):
    first_item = data[0]
    print(f"\n📋 Структура записи: {list(first_item.keys())}")
    
    # Если есть поле 'instruction' но нет 'text', преобразуем
    if 'instruction' in first_item and 'text' not in first_item:
        print("🔄 Преобразуем формат: instruction → text")
        for item in data:
            item['text'] = item.pop('instruction')
        print("✅ Преобразовано")
    elif 'text' in first_item:
        print("✅ Формат уже правильный (есть поле 'text')")
    else:
        print(f"⚠️ Неизвестный формат. Доступные поля: {list(first_item.keys())}")
        print("Сохраняем как есть")

# 6. Сохраняем в UTF-8
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n💾 Сохранено {len(data)} записей в {output_file} (UTF-8)")

# 7. Показываем пример
print("\n📝 Пример первой записи:")
if 'text' in data[0]:
    print(f"   text: {data[0]['text'][:80]}...")
else:
    print(f"   {list(data[0].keys())[0]}: {str(data[0][list(data[0].keys())[0]])[:80]}...")

print("\n✅ Готово! Теперь можно использовать файл.")