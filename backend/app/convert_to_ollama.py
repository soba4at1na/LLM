import json

def convert_to_ollama_format(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in data:
            instruction = item['instruction']
            response = json.dumps(item['response'], ensure_ascii=False)
            
            # Формат для Ollama
            text = f"""### Instruction:
Analyze the technical text and identify issues.

Text: {instruction}

### Response:
{response}"""
            
            f.write(json.dumps({"text": text}, ensure_ascii=False) + '\n')
    
    print(f"✅ Конвертировано {len(data)} примеров в {output_file}")

# Использование — путь к файлу в папке datasets
convert_to_ollama_format('datasets/generated_dataset.json', 'ollama_dataset.jsonl')