import asyncio
from pathlib import Path
from typing import Optional
from llama_cpp import Llama
from app.config import settings

class LLMService:
    _instance: Optional["LLMService"] = None
    _llm: Optional[Llama] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """Инициализация модели (вызывать один раз при старте)"""
        if self._llm is not None:
            return

        model_path = Path(settings.MODEL_PATH)
        if not model_path.exists():
            raise FileNotFoundError(f"Модель не найдена: {model_path}")

        print(f"🚀 Загрузка модели: {model_path.name} ...")
        self._llm = Llama(
            model_path=str(model_path),
            n_gpu_layers=0,           # CPU only
            n_ctx=settings.CONTEXT_SIZE,
            n_threads=settings.N_THREADS,
            n_batch=settings.N_BATCH,
            verbose=False,
            f16=False,
        )
        print("✅ Модель успешно загружена!")

    async def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        if self._llm is None:
            await self.initialize()

        async with self._lock:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._llm(
                    prompt,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=temperature or settings.TEMPERATURE,
                    stop=["<|im_end|>", "<|im_start|>"],
                )
            )
            if isinstance(response, dict) and 'choices' in response:
                return response['choices'][0]['text'].strip()
            return str(response).strip()

# Глобальный экземпляр
llm_service = LLMService()