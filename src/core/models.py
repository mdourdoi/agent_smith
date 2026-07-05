"""Pydantic models: the task inputs we read and the solution we produce.

The StepMetrics / SolutionOutput shapes are the contract the moulinette
validates, so the field names here must match models_public.py.
"""
import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MBPPTaskInput(BaseModel):
    """An MBPP problem to solve."""
    task_id: int
    task_definition: str
    function_definition: str
    test_imports: list[str] = Field(default_factory=list)
    test_list: list[str] = Field(default_factory=list)


class SWEBenchTaskInput(BaseModel):
    """A SWE-bench issue to fix. The agent must produce a git patch."""
    instance_id: str
    problem_statement: str
    docker_image: str
    eval_script: str
    hints_text: str = ""
    repo: str = ""


class StepMetrics(BaseModel):
    """What happened during one iteration of the agent loop."""
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
    """The full result of a run, written to solution.json."""
    task_id: str
    benchmark: str  # "mbpp" or "swebench"
    success: bool
    solution: str   # the code for MBPP, the git patch for SWE-bench
    system_prompt: str
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: list[StepMetrics] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SandboxConfig(BaseModel):
    """Limits the sandbox enforces. Loadable from a JSON file."""
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
        with open(path, encoding="utf-8") as f:
            return cls(**json.load(f))
