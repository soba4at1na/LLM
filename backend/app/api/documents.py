from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.document_record import DocumentChunk, DocumentRecord
from app.models.user import User
from app.services.audit_service import log_event
from app.utils.auth import get_current_active_user
from app.utils.text_processor import (
    build_chunk_rows,
    count_words,
    extract_text_from_bytes,
    sha256_bytes,
    sha256_text,
)

router = APIRouter()


class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    purpose: str
    file_size: int
    word_count: int
    chunk_count: int
    status: str


class DocumentListItem(BaseModel):
    id: int
    filename: str
    source_type: str
    purpose: str
    file_size: int
    word_count: int
    owner_id: str | None = None
    owner_email: str | None = None
    created_at: str


class DocumentContentResponse(BaseModel):
    id: int
    filename: str
    purpose: str
    source_type: str
    file_size: int
    word_count: int
    chunk_count: int
    extracted_text: str
    owner_id: str | None = None
    owner_email: str | None = None
    created_at: str


@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    purpose: str = Form(default="check"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    purpose = (purpose or "check").strip().lower()
    if purpose not in {"check", "training"}:
        raise HTTPException(status_code=400, detail="Invalid purpose. Allowed: check, training")

    payload = await file.read()
    if len(payload) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(payload) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max size is {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in {".txt", ".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: .txt, .pdf, .docx")

    file_hash = sha256_bytes(payload)
    same_file = await db.scalar(
        select(DocumentRecord).where(
            DocumentRecord.owner_id == current_user.id,
            DocumentRecord.purpose == purpose,
            DocumentRecord.file_hash == file_hash,
        ).order_by(desc(DocumentRecord.id))
    )
    if same_file:
        chunk_count_existing = await db.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == same_file.id)
        )
        await log_event(
            db,
            action="document_upload_reused_file_hash",
            user_id=current_user.id,
            resource_type="document",
            resource_id=str(same_file.id),
            metadata={"filename": file.filename, "purpose": purpose, "file_hash": file_hash},
            ip_address=request.client.host if request and request.client else None,
        )
        await db.commit()
        return DocumentUploadResponse(
            id=same_file.id,
            filename=same_file.filename,
            purpose=same_file.purpose,
            file_size=same_file.file_size,
            word_count=same_file.word_count,
            chunk_count=int(chunk_count_existing or 0),
            status=same_file.status,
        )

    try:
        extracted_text, mime_type = extract_text_from_bytes(file.filename, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}") from e

    if not extracted_text:
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    text_hash = sha256_text(extracted_text)
    same_text = await db.scalar(
        select(DocumentRecord).where(
            DocumentRecord.owner_id == current_user.id,
            DocumentRecord.purpose == purpose,
            DocumentRecord.text_hash == text_hash,
        ).order_by(desc(DocumentRecord.id))
    )
    if same_text:
        chunk_count_existing = await db.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == same_text.id)
        )
        await log_event(
            db,
            action="document_upload_reused_text_hash",
            user_id=current_user.id,
            resource_type="document",
            resource_id=str(same_text.id),
            metadata={"filename": file.filename, "purpose": purpose, "text_hash": text_hash},
            ip_address=request.client.host if request and request.client else None,
        )
        await db.commit()
        return DocumentUploadResponse(
            id=same_text.id,
            filename=same_text.filename,
            purpose=same_text.purpose,
            file_size=same_text.file_size,
            word_count=same_text.word_count,
            chunk_count=int(chunk_count_existing or 0),
            status=same_text.status,
        )

    document = DocumentRecord(
        owner_id=current_user.id,
        filename=file.filename,
        mime_type=mime_type,
        extension=extension,
        source_type="upload",
        purpose=purpose,
        file_size=len(payload),
        file_hash=file_hash,
        file_content=payload,
        extracted_text=extracted_text,
        text_hash=text_hash,
        word_count=count_words(extracted_text),
        status="processed",
    )
    db.add(document)
    await db.flush()

    chunk_rows = build_chunk_rows(extracted_text)
    for row in chunk_rows:
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=int(row["chunk_index"]),
                content=str(row["content"]),
                char_count=int(row["char_count"]),
                word_count=int(row["word_count"]),
                sentence_count=int(row["sentence_count"]),
            )
        )

    await log_event(
        db,
        action="document_upload",
        user_id=current_user.id,
        resource_type="document",
        resource_id=str(document.id),
        metadata={
            "filename": document.filename,
            "source_type": document.source_type,
            "purpose": document.purpose,
            "file_size": document.file_size,
            "file_hash": document.file_hash,
            "text_hash": document.text_hash,
            "chunk_count": len(chunk_rows),
        },
        ip_address=request.client.host if request and request.client else None,
    )
    await db.commit()

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        purpose=document.purpose,
        file_size=document.file_size,
        word_count=document.word_count,
        chunk_count=len(chunk_rows),
        status=document.status,
    )


@router.get("/documents", response_model=List[DocumentListItem])
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    purpose: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(DocumentRecord, User.email)
        .order_by(desc(DocumentRecord.id))
        .limit(limit)
        .offset(offset)
    )
    query = query.join(User, User.id == DocumentRecord.owner_id)
    if not current_user.is_admin:
        query = query.where(DocumentRecord.owner_id == current_user.id)
    if purpose is not None:
        query = query.where(DocumentRecord.purpose == purpose)

    rows = (await db.execute(query)).all()
    return [
        DocumentListItem(
            id=doc.id,
            filename=doc.filename,
            source_type=doc.source_type,
            purpose=doc.purpose,
            file_size=doc.file_size,
            word_count=doc.word_count,
            owner_id=str(doc.owner_id) if current_user.is_admin else None,
            owner_email=str(owner_email) if current_user.is_admin else None,
            created_at=doc.created_at.isoformat(),
        )
        for doc, owner_email in rows
    ]


@router.get("/documents/{document_id}", response_model=DocumentUploadResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    document = await db.scalar(
        select(DocumentRecord).where(DocumentRecord.id == document_id)
    )
    if not document or (not current_user.is_admin and document.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = await db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)
    )
    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        purpose=document.purpose,
        file_size=document.file_size,
        word_count=document.word_count,
        chunk_count=int(chunk_count or 0),
        status=document.status,
    )


@router.get("/documents/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(DocumentRecord, User.email)
            .join(User, User.id == DocumentRecord.owner_id)
            .where(DocumentRecord.id == document_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    document, owner_email = row
    if not current_user.is_admin and document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = await db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)
    )

    return DocumentContentResponse(
        id=document.id,
        filename=document.filename,
        purpose=document.purpose,
        source_type=document.source_type,
        file_size=document.file_size,
        word_count=document.word_count,
        chunk_count=int(chunk_count or 0),
        extracted_text=document.extracted_text,
        owner_id=str(document.owner_id) if current_user.is_admin else None,
        owner_email=str(owner_email) if current_user.is_admin else None,
        created_at=document.created_at.isoformat(),
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    document = await db.scalar(select(DocumentRecord).where(DocumentRecord.id == document_id))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not current_user.is_admin and document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    await log_event(
        db,
        action="document_delete",
        user_id=current_user.id,
        resource_type="document",
        resource_id=str(document.id),
        metadata={"filename": document.filename, "purpose": document.purpose},
        ip_address=request.client.host if request and request.client else None,
    )
    await db.delete(document)
    await db.commit()
