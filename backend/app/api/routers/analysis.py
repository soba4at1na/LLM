from fastapi import APIRouter, HTTPException
from app.models.analysis import TextAnalysisRequest, TextAnalysisResponse
from app.services.analysis_service import analysis_service

router = APIRouter()

@router.post("/analyze", response_model=TextAnalysisResponse)
async def analyze_text(request: TextAnalysisRequest):
    """
    Анализирует произвольный текст на проблемы стиля и терминологии
    """
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Текст слишком короткий")

    try:
        result = await analysis_service.analyze_text(request.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")


@router.post("/analyze/document/{document_id}")
async def analyze_document(document_id: int):
    """
    Анализирует ранее загруженный документ (пока заглушка)
    """
    # Позже подключим document_service
    return {"message": f"Анализ документа {document_id} запущен", "status": "processing"}