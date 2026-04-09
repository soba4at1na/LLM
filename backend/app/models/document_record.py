from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(127), nullable=False, default="application/octet-stream")
    extension = Column(String(16), nullable=True)
    source_type = Column(String(20), nullable=False, default="upload")  # upload | text
    purpose = Column(String(20), nullable=False, default="check")  # check | training
    file_size = Column(Integer, nullable=False, default=0)
    file_content = Column(LargeBinary, nullable=True)
    extracted_text = Column(Text, nullable=False, default="")
    word_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="processed")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)
    word_count = Column(Integer, nullable=False, default=0)
    sentence_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
