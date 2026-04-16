import logging
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from llama_cpp import Llama

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self) -> None:
        self.model: Optional[Llama] = None
        self._initialized = False
        self._generate_lock = asyncio.Lock()

    @property
    def is_initialized(self) -> bool:
        return self._initialized and self.model is not None

    def _candidate_model_paths(self) -> list[Path]:
        candidates: list[Path] = []

        configured = str(settings.MODEL_PATH or "").strip()
        if configured:
            candidates.append(Path(configured))

        # Legacy fallback paths (keep backward compatibility).
        candidates.extend(
            [
                Path("models") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
                Path(__file__).resolve().parents[2] / "models" / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
                Path("Model") / "qwen2.5-14b-instruct-uncensored-q5_k_m.gguf",
            ]
        )

        if settings.MODEL_AUTO_SELECT:
            model_dir = Path(str(settings.MODEL_DIR or "/app/models"))
            if model_dir.exists() and model_dir.is_dir():
                model_files = [
                    p for p in model_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in {".gguf", ".bin"}
                ]
                model_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                if len(model_files) == 1:
                    candidates.insert(0, model_files[0])
                elif len(model_files) > 1:
                    # Prefer the most recently modified model if several are present.
                    candidates.insert(0, model_files[0])
                    logger.info(
                        "MODEL_AUTO_SELECT: found %d models in %s, selected latest: %s",
                        len(model_files),
                        model_dir,
                        model_files[0].name,
                    )

        unique: list[Path] = []
        seen: set[str] = set()
        for path in candidates:
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        return unique

    async def initialize(self) -> None:
        if self._initialized:
            return

        candidate_paths = self._candidate_model_paths()
        existing_paths = [p for p in candidate_paths if p.exists()]

        if not existing_paths:
            tried = ", ".join(str(p) for p in candidate_paths)
            raise FileNotFoundError(f"Model not found. Tried: {tried}")

        last_error: Exception | None = None
        for model_path in existing_paths:
            logger.info("Loading model: %s", model_path.name)
            try:
                self.model = await asyncio.to_thread(
                    self._create_model_sync,
                    str(model_path),
                )
                self._initialized = True
                logger.info("Model loaded successfully from: %s", model_path)
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Failed to load model from %s: %s", model_path, exc)

        tried_existing = ", ".join(str(p) for p in existing_paths)
        raise RuntimeError(f"Failed to load any available model. Tried: {tried_existing}") from last_error

    @staticmethod
    def _create_model_sync(model_path: str) -> Llama:
        return Llama(
            model_path=model_path,
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=0,
            n_threads=settings.MODEL_N_THREADS,
            n_threads_batch=settings.MODEL_N_THREADS_BATCH,
            n_batch=settings.MODEL_N_BATCH,
            rope_freq_base=1_000_000,
            verbose=False,
            use_mlock=settings.MODEL_USE_MLOCK,
            use_mmap=settings.MODEL_USE_MMAP,
        )

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.is_initialized:
            return {"content": "", "error": "Model not initialized", "usage": {}}

        try:
            response = self.model(
                prompt=prompt,
                max_tokens=max_tokens if max_tokens is not None else settings.MODEL_MAX_TOKENS,
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

    async def generate_async(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.is_initialized:
            return {"content": "", "error": "Model not initialized", "usage": {}}

        async with self._generate_lock:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        self.generate,
                        prompt,
                        max_tokens,
                        temperature,
                        top_p,
                    ),
                    timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                return {"content": "", "error": "LLM generation timeout", "usage": {}}

    async def shutdown(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
        self._initialized = False
        logger.info("Model unloaded")


llm_service = LLMService()
