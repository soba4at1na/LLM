from fastapi import APIRouter
from pydantic import BaseModel
from app.core.llm_service import llm_service

router = APIRouter()   # ← важно, чтобы было именно "router"

class ChatMessage(BaseModel):
    message: str

@router.post("/")
async def chat(request: ChatMessage):
    """Простой чат с моделью"""
    prompt = f"""<|im_start|>user
{request.message}
<|im_end|>
<|im_start|>assistant
"""

    response = await llm_service.generate(prompt, temperature=0.7)
    return {"response": response}