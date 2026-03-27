from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import aiofiles
from datetime import datetime
import httpx

from .models import AnalysisRequest, AnalysisResponse, SystemMetrics
from .analyzer import TextAnalyzer
from .monitor import SystemMonitor
from .file_processor import FileProcessor, TrainingDataGenerator

# Создаём приложение
app = FastAPI(title="Text Analyzer API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация
analyzer = TextAnalyzer()
monitor = SystemMonitor()
train_generator = TrainingDataGenerator()

# Пути
DATA_DIR = Path("/app/data")
TRAIN_DIR = DATA_DIR / "train"
TEST_DIR = DATA_DIR / "test"
RESULTS_DIR = DATA_DIR / "results"
MODELS_DIR = DATA_DIR / "models"

for dir_path in [TRAIN_DIR, TEST_DIR, RESULTS_DIR, MODELS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def root():
    return {"message": "Text Analyzer API", "version": "1.0.0"}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_text(request: AnalysisRequest):
    result = await analyzer.analyze(request.text, request.model)
    
    result_file = RESULTS_DIR / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    async with aiofiles.open(result_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps({
            "text": request.text,
            "model": request.model,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2))
    
    return AnalysisResponse(**result, original_text=request.text)


@app.post("/upload/train")
async def upload_train_file(file: UploadFile = File(...)):
    """Загружает файл для обучения - автоматически генерирует примеры"""
    content = await file.read()
    
    # Сохраняем исходный файл
    file_path = TRAIN_DIR / file.filename
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Генерируем обучающие примеры
    examples = await train_generator.process_file(content, file.filename)
    
    # Сохраняем в общий датасет
    dataset_path = DATA_DIR / "generated_dataset.json"
    
    existing = []
    if dataset_path.exists():
        async with aiofiles.open(dataset_path, 'r', encoding='utf-8') as f:
            try:
                existing = json.loads(await f.read())
            except:
                existing = []
    
    existing.extend(examples)
    
    async with aiofiles.open(dataset_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(existing, ensure_ascii=False, indent=2))
    
    return {
        "message": f"File {file.filename} processed",
        "examples_generated": len(examples),
        "total_examples": len(existing)
    }


@app.post("/upload/test")
async def upload_test_file(file: UploadFile = File(...)):
    """Загружает файл для проверки - анализирует все абзацы"""
    content = await file.read()
    
    # Сохраняем файл
    file_path = TEST_DIR / file.filename
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Извлекаем текст
    text = await FileProcessor.extract_text(content, file.filename)
    paragraphs = FileProcessor.split_into_paragraphs(text)
    
    # Анализируем ВСЕ абзацы
    results = []
    for i, para in enumerate(paragraphs):
        if len(para) > 50:  # Игнорируем слишком короткие
            print(f"  Анализ абзаца {i+1}/{len(paragraphs)}...")
            result = await analyzer.analyze(para)
            results.append({
                "paragraph": i + 1,
                "text": para[:200] + "..." if len(para) > 200 else para,
                "full_text": para,
                "result": result
            })
    
    # Сохраняем все результаты
    result_path = RESULTS_DIR / f"test_{file.filename}.json"
    async with aiofiles.open(result_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(results, ensure_ascii=False, indent=2))
    
    return {
        "message": f"File {file.filename} analyzed",
        "total_paragraphs": len(paragraphs),
        "analyzed": len(results),
        "results": results[:10]
    }


@app.get("/train/list")
async def list_train_files():
    """Список обучающих файлов"""
    files = [f.name for f in TRAIN_DIR.iterdir() if f.is_file()]
    return {"files": files}


@app.get("/test/list")
async def list_test_files():
    """Список тестовых файлов"""
    files = [f.name for f in TEST_DIR.iterdir() if f.is_file()]
    return {"files": files}


@app.delete("/train/delete/{filename}")
async def delete_train_file(filename: str):
    """Удалить обучающий файл"""
    file_path = TRAIN_DIR / filename
    if file_path.exists():
        file_path.unlink()
    return {"message": f"Deleted {filename}"}


@app.delete("/test/delete/{filename}")
async def delete_test_file(filename: str):
    """Удалить тестовый файл"""
    file_path = TEST_DIR / filename
    if file_path.exists():
        file_path.unlink()
    return {"message": f"Deleted {filename}"}


@app.get("/results")
async def get_results(limit: int = 10):
    """Последние результаты анализа"""
    results = []
    for file_path in sorted(RESULTS_DIR.glob("result_*.json"), reverse=True)[:limit]:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            results.append(json.loads(content))
    return {"results": results}


@app.get("/results/test/{filename}")
async def get_test_results(filename: str):
    """Получить результаты анализа тестового файла"""
    result_path = RESULTS_DIR / f"test_{filename}.json"
    if result_path.exists():
        async with aiofiles.open(result_path, 'r', encoding='utf-8') as f:
            return json.loads(await f.read())
    return {"error": "Results not found"}


@app.get("/metrics", response_model=SystemMetrics)
async def get_metrics():
    """Системная метрика"""
    return SystemMetrics(**monitor.get_metrics())


@app.get("/models")
async def get_models():
    """Список доступных моделей Ollama"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://ollama:11434/api/tags")
            return response.json()
    except:
        return {"models": [], "error": "Ollama not available"}


@app.get("/dataset")
async def get_dataset():
    """Получить текущий обучающий датасет"""
    dataset_path = DATA_DIR / "generated_dataset.json"
    if dataset_path.exists():
        async with aiofiles.open(dataset_path, 'r', encoding='utf-8') as f:
            return json.loads(await f.read())
    return []


@app.get("/dataset/stats")
async def get_dataset_stats():
    """Статистика датасета"""
    dataset_path = DATA_DIR / "generated_dataset.json"
    if dataset_path.exists():
        async with aiofiles.open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())
            total = len(data)
            correct = sum(1 for item in data if item.get('response', {}).get('is_correct', False))
            return {"total": total, "correct": correct, "incorrect": total - correct}
    return {"total": 0, "correct": 0, "incorrect": 0}


@app.get("/gpu-status")
async def get_gpu_status():
    """Получить статус GPU через Ollama API"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://ollama:11434/api/tags")
            if response.status_code == 200:
                tags = response.json()
                models = tags.get('models', [])
                if models:
                    return {
                        "available": True,
                        "message": "GPU активен через Ollama",
                        "models": [m.get('name', 'qwen2.5:7b') for m in models]
                    }
    except Exception as e:
        print(f"Ollama error: {e}")
    
    return {"available": False, "message": "Ollama не доступен"}