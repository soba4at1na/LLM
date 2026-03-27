from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class AnalysisRequest(BaseModel):
    text: str
    model: str = "qwen2.5:7b"

class AnalysisResponse(BaseModel):
    is_correct: bool
    confidence: float
    issues: List[Dict[str, str]] = []
    corrected_text: str = ""
    analysis: str = ""
    timestamp: datetime = datetime.now()
    original_text: Optional[str] = None

class SystemMetrics(BaseModel):
    cpu_percent: float
    cpu_count: Optional[int] = None
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    gpu_available: bool
    gpu_details: Optional[Dict] = None
    gpu_utilization: Optional[float] = None
    gpu_memory_used_gb: Optional[float] = None
    gpu_memory_total_gb: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    gpu_temperature: Optional[float] = None
    gpu_power_draw: Optional[float] = None
    gpu_processes: Optional[List[Dict]] = None
    disk_used_gb: float
    disk_total_gb: float