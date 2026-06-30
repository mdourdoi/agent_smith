import time
from abc import ABC

from core.sandbox import Sandbox, FinalAnswerSignal
from core.step_metrics import StepMetrics
from core.solution_output import SolutionOutput
from core.code_extractor import CodeExtractor, ExtractionResult
from core.console import Console


class BaseOrchestrator(ABC):
    max_iterations: int
    max_input_tokens: int
    max_output_tokens: int
    timeout_seconds: int

    def __init__(
        self,
        sandbox: Sandbox,
        # function: (messages: list[dict]) -> (str, int, int)
        call_llm,
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
        self.conversation_history = [
            {"role": "system", "content": system_prompt}
        ]

    @property
    def benchmark(self) -> str: ...

    def _build_observation(
        self,
        extraction: ExtractionResult | None,
        sandbox_output: str,
    ) -> str:
        parts = []

        if extraction is None:
            return (
                "ERROR: No executable code found in your response.\n"
                "Supported formats: ```python ... ```, XML <invoke>, "
                "<tool_call> JSON, or ReAct Action/Action Input.\n"
                "Please try again with a valid code block."
            )

        if extraction.warning:
            parts.append(f"WARNING: {extraction.warning}")

        if extraction.original_format != "python":
            parts.append(
                "NOTE: Your response was in "
                f"{extraction.original_format!r} format "
                "and was automatically converted to Python before execution."
            )

        if not sandbox_output.strip():
            parts.append("(no output)")
        else:
            parts.append(sandbox_output)

        return "\n".join(parts)

    def run(self, task_description: str) -> SolutionOutput:
        self.console.task_start(self.task_id, self.benchmark, self.model_name)
        self.sandbox.start()
        try:
            return self._run_loop(task_description)
        finally:
            self.sandbox.cleanup()

    def _run_loop(self, task_description: str) -> SolutionOutput:
        self.conversation_history.append(
            {"role": "user", "content": task_description}
        )

        steps: list[StepMetrics] = []
        total_input_tokens = 0
        total_output_tokens = 0
        start_time = time.monotonic()
        error: str | None = None
        solution: str = ""
        success = False

        for iteration in range(self.max_iterations):
            self.console.iteration(iteration + 1, self.max_iterations)

            elapsed = time.monotonic() - start_time
            if elapsed > self.timeout_seconds:
                error = f"Timeout exceeded ({self.timeout_seconds}s)."
                self.console.error(error)
                break

            step_start = time.monotonic()
            llm_response, input_tokens, output_tokens = self.call_llm(
                self.conversation_history
            )
            request_time_ms = (time.monotonic() - step_start) * 1000

            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            self.console.thought(llm_response)

            if total_input_tokens > self.max_input_tokens:
                error = "Input token budget exceeded "
                error += f"({self.max_input_tokens})."
                self.console.error(error)
                break
            if total_output_tokens > self.max_output_tokens:
                error = "Output token budget exceeded "
                error += f"({self.max_output_tokens})."
                self.console.error(error)
                break

            extraction = self.extractor.extract(llm_response)
            sandbox_input = extraction.code if extraction else ""
            sandbox_output = ""

            if extraction is None:
                observation = self._build_observation(None, "")
            else:
                self.console.code(extraction.code)
                try:
                    sandbox_output = self.sandbox.run(extraction.code)
                    observation = self._build_observation(
                        extraction, sandbox_output)
                except FinalAnswerSignal as signal:
                    self.conversation_history.append(
                        {"role": "assistant", "content": llm_response}
                    )
                    steps.append(StepMetrics(
                        step=iteration + 1,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        request_time_ms=request_time_ms,
                        api_url=self.api_url,
                        model_name=self.model_name,
                        llm_output=llm_response,
                        sandbox_input=sandbox_input,
                        sandbox_output=f"final_answer called: {signal.answer}",
                        retries=0,
                    ))
                    solution = signal.answer
                    success = True
                    break

            self.console.observation(observation)
            self.console.tokens(total_input_tokens, total_output_tokens)

            steps.append(StepMetrics(
                step=iteration + 1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_time_ms=request_time_ms,
                api_url=self.api_url,
                model_name=self.model_name,
                llm_output=llm_response,
                sandbox_input=sandbox_input,
                sandbox_output=sandbox_output,
                retries=0,
            ))

            self.conversation_history.append(
                {"role": "assistant", "content": llm_response}
            )
            self.conversation_history.append(
                {"role": "user", "content": f"Observation:\n{observation}"}
            )

        self.console.solved(success, len(steps))

        return SolutionOutput(
            task_id=self.task_id,
            benchmark=self.benchmark,
            success=success,
            solution=solution,
            system_prompt=self.system_prompt,
            iterations=len(steps),
            total_requests=len(steps),
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_time_seconds=time.monotonic() - start_time,
            steps=steps,
            error=error,
        )
