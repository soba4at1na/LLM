from pathlib import Path
from typing import List, Optional
from datetime import datetime
from app.models.document import DocumentResponse, DocumentCreate
from app.utils.text_processor import extract_text_from_file, count_words

class DocumentService:
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)

    async def save_document(self, file) -> DocumentResponse:
        """
        Сохраняет загруженный файл и извлекает текст
        """
        file_path = self.upload_dir / file.filename
        
        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Извлекаем текст
        text, mime_type = await extract_text_from_file(file_path)

        doc = DocumentResponse(
            id=hash(file.filename + str(datetime.now())),  # временный id, позже будет из БД
            filename=file.filename,
            original_text=text,
            uploaded_at=datetime.now(),
            status="uploaded",
            word_count=count_words(text)
        )

        return doc

    async def get_document(self, doc_id: int) -> Optional[DocumentResponse]:
        # Пока заглушка — позже будет из БД
        return None

    def get_all_documents(self) -> List[DocumentResponse]:
        # Пока заглушка
        return []

document_service = DocumentService()