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
