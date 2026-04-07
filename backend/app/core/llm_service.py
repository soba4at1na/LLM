import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from llama_cpp import Llama

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.model: Optional[Llama] = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized and self.model is not None

    def _resolve_model_path(self) -> Path:
        """Ищем модель по нескольким путям"""
        model_path = Path(settings.MODEL_PATH)
        if model_path.exists():
            return model_path

        # Альтернативные пути
        local_paths = [
            Path("models") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            Path(__file__).parent.parent.parent / "models" / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            Path("Model") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
        ]

        for path in local_paths:
            if path.exists():
                logger.info(f"Модель найдена по пути: {path}")
                return path

        return model_path

    async def initialize(self) -> None:
        if self._initialized:
            return

        model_path = self._resolve_model_path()

        if not model_path.exists():
            raise FileNotFoundError(f"Модель не найдена: {model_path}")

        logger.info(f"Загрузка модели: {model_path.name}")

        self.model = Llama(
            model_path=str(model_path),
            n_ctx=6144,                    # уменьшили — сильно влияет на скорость
            n_gpu_layers=0,
            n_threads=14,                  # оптимально для 5700X
            n_threads_batch=14,
            n_batch=512,
            rope_freq_base=1_000_000,
            verbose=False,
            use_mlock=True,
            use_mmap=True,
        )

        self._initialized = True
        logger.info(f"✅ Модель успешно загружена")


    def generate(
        self,
        prompt: str,
        max_tokens: int = 800,           # уменьшили — ответы быстрее
        temperature: Optional[float] = 0.2,
        top_p: Optional[float] = 0.9,
    ) -> Dict[str, Any]:
        if not self.is_initialized:
            return {"content": "", "error": "Model not initialized", "usage": {}}

        try:
            response = self.model(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                echo=False,
                stream=False,
            )

            return {
                "content": response["choices"][0]["text"],
                "usage": response.get("usage", {}),
                "error": None
            }

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return {"content": "", "error": str(e), "usage": {}}

    async def shutdown(self) -> None:
        if self.model:
            del self.model
            self.model = None
            self._initialized = False
            logger.info("Модель выгружена из памяти")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,           # уменьшили, чтобы быстрее отвечала
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.is_initialized:
            return {"content": "", "error": "Model not initialized", "usage": {}}

        try:
            response = self.model(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature or settings.MODEL_TEMPERATURE,
                top_p=top_p or 0.9,
                echo=False,
                stream=False,
            )

            return {
                "content": response["choices"][0]["text"],
                "usage": response.get("usage", {}),
                "error": None
            }

        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return {"content": "", "error": str(e), "usage": {}}


llm_service = LLMService()