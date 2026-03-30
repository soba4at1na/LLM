from pydantic import BaseModel
from typing import List, Optional

class AnalysisIssue(BaseModel):
    type: str
    position: str
    description: str
    suggestion: Optional[str] = None


class TextAnalysisRequest(BaseModel):
    text: str
    error_types: Optional[List[str]] = None


class TextAnalysisResponse(BaseModel):
    is_correct: bool
    confidence: float
    issues: List[AnalysisIssue] = []
    corrected_text: Optional[str] = None
    analysis: str = ""