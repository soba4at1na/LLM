from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class AnalysisRequest(BaseModel):
    text: str
    model: str = "qwen2.5:7b"

class AnalysisResponse(BaseModel):
    is_correct: bool
    confidence: float
    issues: List[Dict[str, str]]
    corrected_text: str
    analysis: str
    timestamp: datetime = datetime.now()

class TrainRequest(BaseModel):
    text: str
    correct: bool
    issues: Optional[List[Dict]] = []
    corrected_text: Optional[str] = ""

class SystemMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    gpu_available: bool
    gpu_utilization: Optional[float] = None
    gpu_memory_used: Optional[float] = None
    gpu_memory_total: Optional[float] = None
    disk_used_gb: float
    disk_total_gb: float