"""The agent loop: ask the model, run its code, feed back what happened,
repeat until it submits an answer or hits a limit.
"""
import time
from abc import ABC, abstractmethod

from core.sandbox import Sandbox, FinalAnswerSignal
from core.models import StepMetrics, SolutionOutput
from core.agent.code_extractor import CodeExtractor, ExtractionResult
from core.agent.console import Console


class BaseOrchestrator(ABC):
    # Per-benchmark limits, filled in by the subclasses below. The
    # evaluation rejects a run that goes over any of them.
    max_iterations: int
    max_input_tokens: int
    max_output_tokens: int
    timeout_seconds: int

    def __init__(
        self,
        sandbox: Sandbox,
        call_llm,          # messages -> (text, in_tokens, out_tokens, retries)
        system_prompt: str,
        task_id: str,
        model_name: str,
        api_url: str,
        verbose: bool = False,
    ):
        self.sandbox = sandbox
        self.call_llm = call_llm
        self.system_prompt = system_prompt
        self.task_id = task_id
        self.model_name = model_name
        self.api_url = api_url
        self.extractor = CodeExtractor()
        self.console = Console(verbose=verbose)
        self.messages = [{"role": "system", "content": system_prompt}]

    @property
    @abstractmethod
    def benchmark(self) -> str:
        ...

    def run(self, task_description: str) -> SolutionOutput:
        """Start the sandbox, run the loop, always clean up afterwards."""
        self.console.task_start(self.task_id, self.benchmark, self.model_name)
        self.sandbox.start()
        try:
            return self._loop(task_description)
        finally:
            self.sandbox.cleanup()

    def _loop(self, task_description: str) -> SolutionOutput:
        self.messages.append({"role": "user", "content": task_description})

        steps: list[StepMetrics] = []
        total_in = 0
        total_out = 0
        total_retries = 0
        start = time.monotonic()
        error: str | None = None
        solution = ""
        success = False

        for i in range(self.max_iterations):
            self.console.iteration(i + 1, self.max_iterations)

            if time.monotonic() - start > self.timeout_seconds:
                error = f"Timeout exceeded ({self.timeout_seconds}s)."
                self.console.error(error)
                break

            # Ask the model.
            call_start = time.monotonic()
            llm_output, in_tokens, out_tokens, retries = self.call_llm(
                self.messages)
            request_ms = (time.monotonic() - call_start) * 1000
            total_in += in_tokens
            total_out += out_tokens
            total_retries += retries
            self.console.thought(llm_output)

            # Stop as soon as a token budget is blown.
            if total_in > self.max_input_tokens:
                error = ("Input token budget exceeded "
                         f"({self.max_input_tokens}).")
                self.console.error(error)
                break
            if total_out > self.max_output_tokens:
                error = ("Output token budget exceeded "
                         f"({self.max_output_tokens}).")
                self.console.error(error)
                break

            # Turn the reply into code and run it.
            extraction = self.extractor.extract(llm_output)
            sandbox_input = extraction.code if extraction else ""
            sandbox_output = ""

            if extraction is None:
                observation = self._observation(None, "")
            else:
                self.console.code(extraction.code)
                try:
                    sandbox_output = self.sandbox.run(extraction.code)
                    observation = self._observation(extraction, sandbox_output)
                except FinalAnswerSignal as signal:
                    # The model called final_answer: record the step and stop.
                    self.messages.append(
                        {"role": "assistant", "content": llm_output})
                    steps.append(self._step(
                        i + 1, in_tokens, out_tokens, request_ms, retries,
                        llm_output, sandbox_input,
                        f"final_answer called: {signal.answer}"))
                    solution = signal.answer
                    success = True
                    break

            self.console.observation(observation)
            self.console.tokens(total_in, total_out)

            steps.append(self._step(
                i + 1, in_tokens, out_tokens, request_ms, retries,
                llm_output, sandbox_input, sandbox_output))
            # Never store an empty assistant turn: some providers (Mistral)
            # reject a message with no content on the next request. The step
            # metrics below still keep the real (possibly empty) llm_output.
            self.messages.append(
                {"role": "assistant", "content": llm_output or "(no output)"})
            self.messages.append(
                {"role": "user", "content": f"Observation:\n{observation}"})

        self.console.solved(success, len(steps))
        return SolutionOutput(
            task_id=self.task_id,
            benchmark=self.benchmark,
            success=success,
            solution=solution,
            system_prompt=self.system_prompt,
            iterations=len(steps),
            total_requests=len(steps) + total_retries,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_time_seconds=time.monotonic() - start,
            steps=steps,
            error=error,
        )

    def _step(self, n, in_tokens, out_tokens, request_ms, retries,
              llm_output, sandbox_input, sandbox_output) -> StepMetrics:
        return StepMetrics(
            step=n,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            request_time_ms=request_ms,
            api_url=self.api_url,
            model_name=self.model_name,
            llm_output=llm_output,
            sandbox_input=sandbox_input,
            sandbox_output=sandbox_output,
            retries=retries,
        )

    def _observation(
        self,
        extraction: ExtractionResult | None,
        sandbox_output: str,
    ) -> str:
        """Build the feedback the model reads next. It should never have to
        guess what happened, so we spell out every unusual case."""
        if extraction is None:
            return (
                "ERROR: No executable code found in your response.\n"
                "Supported formats: ```python ... ```, XML <invoke>, "
                "<tool_call> JSON, or ReAct Action/Action Input.\n"
                "Please try again with a valid code block."
            )

        parts = []
        if extraction.warning:
            parts.append(f"WARNING: {extraction.warning}")
        if extraction.original_format != "python":
            parts.append(
                f"NOTE: your {extraction.original_format} response was "
                "converted to Python before running.")
        parts.append(sandbox_output if sandbox_output.strip()
                     else "(no output)")
        return "\n".join(parts)


class MBPPOrchestrator(BaseOrchestrator):
    max_iterations = 10
    max_input_tokens = 6_000
    max_output_tokens = 1_500
    timeout_seconds = 120

    @property
    def benchmark(self) -> str:
        return "mbpp"


class SWEBenchOrchestrator(BaseOrchestrator):
    max_iterations = 30
    max_input_tokens = 300_000
    max_output_tokens = 10_000
    timeout_seconds = 900

    @property
    def benchmark(self) -> str:
        return "swebench"
