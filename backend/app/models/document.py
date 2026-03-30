from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class DocumentBase(BaseModel):
    filename: str
    original_text: str = ""

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: int
    uploaded_at: datetime
    status: str = "uploaded"  # uploaded, analyzed, error
    word_count: Optional[int] = None

    class Config:
        from_attributes = True

class AnalysisIssue(BaseModel):
    type: str
    position: str
    description: str
    suggestion: Optional[str] = None

class AnalysisResult(BaseModel):
    document_id: int
    is_correct: bool
    confidence: float
    issues: List[AnalysisIssue] = Field(default_factory=list)
    corrected_text: Optional[str] = None
    analysis_summary: Optional[str] = None
    processing_time_seconds: Optional[float] = None