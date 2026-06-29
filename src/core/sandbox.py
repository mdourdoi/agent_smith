"""
Sandbox for executing LLM-generated code.

SKELETON VERSION — bare exec(), no real security yet.
Will be replaced later by proper isolation (separate process,
restricted imports, timeout, memory limits).
"""

import io
import contextlib


class FinalAnswerSignal(Exception):
    """Raised when the generated code calls final_answer(...)."""

    def __init__(self, answer: str):
        self.answer = answer
        super().__init__(f"final_answer called with: {answer!r}")


class Sandbox:
    """Executes Python code and returns a textual observation."""

    def __init__(self, tools: dict | None = None):
        self._namespace = dict(tools or {})
        self._namespace["final_answer"] = self._final_answer

    def _final_answer(self, answer: str) -> None:
        raise FinalAnswerSignal(answer)

    def run(self, code: str) -> str:
        """
        Execute `code` in the persistent namespace.
        Returns the textual observation, or raises FinalAnswerSignal
        if final_answer() was called (the Orchestrator must catch it).
        """
        output_buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(output_buffer):
                exec(code, self._namespace)
        except FinalAnswerSignal:
            raise
        except Exception as e:
            return f"ERROR during execution: {type(e).__name__}: {e}"

        return output_buffer.getvalue()
