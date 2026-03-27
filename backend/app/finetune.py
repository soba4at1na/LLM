from unsloth import FastLanguageModel
import torch
from datasets import Dataset
import json

# Загружаем датасет
with open('generated_dataset.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Форматируем для обучения
train_data = []
for item in data:
    instruction = item['instruction']
    response = json.dumps(item['response'], ensure_ascii=False)
    
    train_data.append({
        "text": f"### Instruction:\nAnalyze the technical text and identify issues.\n\nText: {instruction}\n\n### Response:\n{response}"
    })

dataset = Dataset.from_list(train_data)

# Загружаем модель
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-7B",
    max_seq_length = 4096,
    dtype = None,
    load_in_4bit = True,
)

# Добавляем LoRA
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 42,
)

# Обучение
from trl import SFTTrainer
from transformers import TrainingArguments

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = 4096,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 200,
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 1,
        output_dir = "outputs",
        save_steps = 50,
    ),
)
trainer.train()

# Сохраняем адаптер
model.save_pretrained("lora_model")