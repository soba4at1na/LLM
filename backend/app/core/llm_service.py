import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from llama_cpp import Llama

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Сервис для работы с локальной LLM (Qwen2.5)"""

    def __init__(self):
        self.model: Optional[Llama] = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Инициализация модели"""
        if self._initialized:
            return

        model_path = Path(settings.MODEL_PATH)
        
        # Автоматический поиск модели
        if not model_path.exists():
            possible_paths = [
                Path("models") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
                Path("Model") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
                Path(__file__).parent.parent.parent / "models" / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            ]
            for p in possible_paths:
                if p.exists():
                    model_path = p
                    break

        if not model_path.exists():
            raise FileNotFoundError(f"Модель не найдена: {model_path}")

        logger.info(f"🚀 Загрузка модели: {model_path.name}")

        self.model = Llama(
            model_path=str(model_path),
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=settings.N_GPU_LAYERS,
            n_threads=settings.N_THREADS or (os.cpu_count() or 8),
            n_batch=512,
            verbose=False,
            use_mlock=True,
            use_mmap=True,
        )

        self._initialized = True
        logger.info(f"✅ Модель успешно загружена: {model_path.name}")

    async def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        """Асинхронная генерация текста"""
        if not self.model:
            await self.initialize()

        async with self._lock:
            try:
                response = await asyncio.to_thread(
                    self.model,
                    prompt,
                    max_tokens=1024,
                    temperature=temperature or settings.MODEL_TEMPERATURE,
                    top_p=settings.MODEL_TOP_P,
                    echo=False,
                    stop=["<|im_end|>", "<|im_start|>"],
                )
                return response["choices"][0]["text"].strip()
            except Exception as e:
                logger.error(f"Ошибка генерации: {e}")
                return f"Ошибка при генерации: {str(e)}"

    async def shutdown(self):
        if self.model:
            del self.model
            self.model = None
            self._initialized = False


# Глобальный экземпляр
llm_service = LLMService()