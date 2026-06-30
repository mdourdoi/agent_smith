from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from core.step_metrics import StepMetrics


class SolutionOutput(BaseModel):
    task_id: str
    benchmark: str  # "mbpp" or "swebench"
    success: bool
    solution: str   # code for MBPP, git patch for SWE-bench
    system_prompt: str
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: list[StepMetrics] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
