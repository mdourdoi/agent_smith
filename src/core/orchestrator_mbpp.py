"""
MBPPOrchestrator: orchestrator specialized for MBPP tasks.
Limits from subject VI.1.1.
"""

from orchestrator_base import BaseOrchestrator


class MBPPOrchestrator(BaseOrchestrator):
    max_iterations = 10
    max_input_tokens = 6_000
    max_output_tokens = 1_500
    timeout_seconds = 120
