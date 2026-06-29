import re
import time
from abc import ABC

from sandbox import Sandbox, FinalAnswerSignal


class BaseOrchestrator(ABC):
    # Overridden by subclasses (MBPP / SWE-bench).
    max_iterations: int
    max_input_tokens: int
    max_output_tokens: int
    timeout_seconds: int

    def __init__(
        self,
        sandbox: Sandbox,
        call_llm,
        system_prompt: str,
    ):
        self.sandbox = sandbox
        self.call_llm = call_llm
        self.conversation_history = [
            {"role": "system", "content": system_prompt}
        ]
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def extract_code_block(self, llm_response: str) -> str | None:
        """Extract the content of a ```python ... ``` block. None if absent."""
        match = re.search(r"```python\s*\n(.*?)```", llm_response, re.DOTALL)
        if match is None:
            return None
        return match.group(1)

    def run(self, task_description: str) -> str | None:
        """
        Run the agentic loop on a given task.
        Returns the final answer, or None if any limit is exceeded
        (max_iterations, token budget, or timeout) before final_answer
        was called.
        """
        self.conversation_history.append(
            {"role": "user", "content": task_description}
        )

        start_time = time.monotonic()

        for iteration in range(self.max_iterations):
            # Timeout check, before doing any more work this iteration.
            elapsed = time.monotonic() - start_time
            if elapsed > self.timeout_seconds:
                return None

            # call_llm must return (response_text, input_tokens, output_tokens)
            llm_response, input_tokens, output_tokens = self.call_llm(
                self.conversation_history
            )
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            # Token budget check, after counting this call's usage.
            if (
                self.total_input_tokens > self.max_input_tokens
                or self.total_output_tokens > self.max_output_tokens
            ):
                return None

            code = self.extract_code_block(llm_response)

            if code is None:
                observation = (
                    "ERROR: no valid Python code block "
                    "(```python ... ```) found in your response."
                )
            else:
                try:
                    observation = self.sandbox.run(code)
                except FinalAnswerSignal as signal:
                    self.conversation_history.append(
                        {"role": "assistant", "content": llm_response}
                    )
                    return signal.answer

            self.conversation_history.append(
                {"role": "assistant", "content": llm_response}
            )
            self.conversation_history.append(
                {"role": "user", "content": f"Observation:\n{observation}"}
            )

        return None