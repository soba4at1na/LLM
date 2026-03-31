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
        model_path = Path(settings.MODEL_PATH)
        if model_path.exists():
            return model_path
        
        local_paths = [
            Path(__file__).parent.parent.parent / "models" / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            Path(__file__).parent.parent.parent / "models" / "model.gguf",
            Path("models") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
        ]
        
        for path in local_paths:
            if path.exists():
                logger.info(f"Found model at local path: {path}")
                return path
        
        return model_path
    
    async def initialize(self) -> None:
        if self._initialized:
            return
        
        model_path = self._resolve_model_path()
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        logger.info(f"Loading model from: {model_path}")
        
        self.model = Llama(
            model_path=str(model_path),
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=-1,
            n_threads=os.cpu_count() or 4,
            verbose=False,
            use_mlock=True,
            use_mmap=True,
        )
        
        self._initialized = True
        logger.info(f"Model loaded: {model_path.name}")
    
    async def shutdown(self) -> None:
        if self.model:
            del self.model
            self.model = None
            self._initialized = False
            logger.info("Model unloaded from memory")
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
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
                top_p=top_p or 0.9,
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
            logger.error(f"Generation error: {e}")
            return {
                "content": "",
                "error": str(e),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}
            }


llm_service = LLMService()