# backend/app/core/llm_service.py
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from llama_cpp import Llama

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Сервис для работы с локальной LLM"""
    
    def __init__(self):
        self.model: Optional[Llama] = None
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized and self.model is not None
    
    def _resolve_model_path(self) -> Path:
        """
        Умное определение пути к модели:
        1. Путь из settings.MODEL_PATH
        2. Локальный путь для разработки
        3. Относительный путь
        """
        # 1. Пробуем путь из настроек
        model_path = Path(settings.MODEL_PATH)
        if model_path.exists():
            return model_path
        
        # 2. Пробуем локальные пути (для запуска вне Docker)
        local_paths = [
            Path(__file__).parent.parent.parent / "models" / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            Path(__file__).parent.parent.parent / "models" / "model.gguf",
            Path("models") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            Path("Model") / "default.gguf",
        ]
        
        for path in local_paths:
            if path.exists():
                logger.info(f"🔍 Найдена модель по локальному пути: {path}")
                return path
        
        # 3. Если не найдено — возвращаем исходный путь для понятной ошибки
        return model_path
    
    async def initialize(self) -> None:
        """Инициализация модели"""
        if self._initialized:
            return
        
        model_path = self._resolve_model_path()
        
        if not model_path.exists():
            raise FileNotFoundError(f"Модель не найдена: {model_path}")
        
        logger.info(f"📦 Загрузка модели из: {model_path}")
        
        # 🎯 Параметры загрузки
        self.model = Llama(
            model_path=str(model_path),
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=-1,  # Использовать все доступные GPU слои
            n_threads=os.cpu_count() or 4,
            verbose=False,
            # 🚀 Оптимизации для скорости
            use_mlock=True,  # Зафиксировать модель в памяти
            use_mmap=True,   # Memory mapping для экономии RAM
        )
        
        self._initialized = True
        logger.info(f"✅ Модель загружена: {model_path.name}")
    
    async def shutdown(self) -> None:
        """Очистка ресурсов"""
        if self.model:
            del self.model
            self.model = None
            self._initialized = False
            logger.info("🧹 Модель выгружена из памяти")
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Генерация ответа от модели
        
        Returns:
            Dict с полями: content, usage, error
        """
        if not self.is_initialized:
            return {
                "content": "",
                "error": "Model not initialized",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}
            }
        
        try:
            response = self.model(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature or settings.MODEL_TEMPERATURE,
                top_p=top_p or settings.MODEL_TOP_P,
                echo=False,
                stream=False,
            )
            
            return {
                "content": response["choices"][0]["text"],
                "usage": {
                    "prompt_tokens": response["usage"]["prompt_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "total_tokens": response["usage"]["total_tokens"]
                },
                "error": None
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
            return {
                "content": "",
                "error": str(e),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}
            }
    
    def format_prompt(self, instruction: str, context: str = "") -> str:
        """Форматирование промпта для Qwen2.5"""
        if context:
            return f"""<|im_start|>system
Ты технический анализатор текстов. Отвечай кратко и по делу, в формате JSON если запрошено.
<|im_end|>
<|im_start|>user
Контекст: {context}

Задача: {instruction}
<|im_end|>
<|im_start|>assistant
"""
        return f"""<|im_start|>system
Ты технический анализатор текстов. Отвечай кратко и по делу.
<|im_end|>
<|im_start|>user
{instruction}
<|im_end|>
<|im_start|>assistant
"""


# 🎯 Глобальный экземпляр сервиса
llm_service = LLMService()