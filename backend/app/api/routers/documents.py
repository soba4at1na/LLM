from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from typing import List
from app.models.document import DocumentResponse
from app.services.document_service import document_service

router = APIRouter()

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Загрузка документа (PDF, DOCX, TXT)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    allowed_types = {".txt", ".pdf", ".docx", ".doc"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Неподдерживаемый формат. Разрешено: {', '.join(allowed_types)}"
        )

    try:
        document = await document_service.save_document(file)
        return document
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {str(e)}")


@router.get("/", response_model=List[DocumentResponse])
async def list_documents():
    """Список всех загруженных документов"""
    return document_service.get_all_documents()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int):
    """Получить документ по ID"""
    doc = await document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc