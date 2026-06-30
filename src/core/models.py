from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import json


class SandboxConfig(BaseModel):
    authorized_imports: list[str] = Field(default_factory=lambda: [
        "math", "math.*", "collections", "collections.*",
        "itertools", "re", "json", "typing", "typing.*",
        "functools", "operator", "heapq", "bisect", "copy",
        "string", "random", "datetime", "datetime.*",
        "array", "cmath"])
    allowed_directories: list[str] = Field(default_factory=lambda: [
        "/testbed", "/tmp/agent"])
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512

    @classmethod
    def from_json(cls, path: str) -> "SandboxConfig":
        with open(path) as f:
            return cls(**json.load(f))


class StepMetrics(BaseModel):
    step: int
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    api_url: str
    model_name: str
    llm_output: str
    sandbox_input: str
    sandbox_output: str
    retries: int
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


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


class FinalAnswerSignal(Exception):
    def __init__(self, answer: str):
        self.answer = answer
