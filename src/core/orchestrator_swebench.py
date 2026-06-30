"""
SWEBenchOrchestrator: orchestrator specialized for SWE-bench tasks.
Limits from subject VI.1.2.
"""

from core.orchestrator_base import BaseOrchestrator


class SWEBenchOrchestrator(BaseOrchestrator):
    max_iterations = 30
    max_input_tokens = 300_000
    max_output_tokens = 10_000
    timeout_seconds = 900

    @property
    def benchmark(self) -> str:
        return "swebench"
