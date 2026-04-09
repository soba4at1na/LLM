import logging
from pathlib import Path
from typing import Any, Dict, Optional

from llama_cpp import Llama

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self) -> None:
        self.model: Optional[Llama] = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized and self.model is not None

    def _resolve_model_path(self) -> Path:
        configured_path = Path(settings.MODEL_PATH)
        if configured_path.exists():
            return configured_path

        fallbacks = [
            Path("models") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            Path(__file__).resolve().parents[2] / "models" / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            Path("Model") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
        ]
        for path in fallbacks:
            if path.exists():
                logger.info("Model found at fallback path: %s", path)
                return path

        return configured_path

    async def initialize(self) -> None:
        if self._initialized:
            return

        model_path = self._resolve_model_path()
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        logger.info("Loading model: %s", model_path.name)
        self.model = Llama(
            model_path=str(model_path),
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=0,
            n_threads=14,
            n_threads_batch=14,
            n_batch=512,
            rope_freq_base=1_000_000,
            verbose=False,
            use_mlock=True,
            use_mmap=True,
        )
        self._initialized = True
        logger.info("Model loaded successfully")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 700,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.is_initialized:
            return {"content": "", "error": "Model not initialized", "usage": {}}

        try:
            response = self.model(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature if temperature is not None else settings.MODEL_TEMPERATURE,
                top_p=top_p if top_p is not None else 0.9,
                echo=False,
                stream=False,
            )
            return {
                "content": response["choices"][0]["text"],
                "usage": response.get("usage", {}),
                "error": None,
            }
        except Exception as e:
            logger.error("Generation error: %s", e)
            return {"content": "", "error": str(e), "usage": {}}

    async def shutdown(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
        self._initialized = False
        logger.info("Model unloaded")


llm_service = LLMService()
