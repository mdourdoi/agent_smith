import multiprocessing
from core.models import SandboxConfig, FinalAnswerSignal
from core.sandbox_worker import SandboxWorker


class Sandbox:
    def __init__(self, tools: dict | None = None,
                 config: SandboxConfig | None = None):
        self.tools = tools or {}
        self.config = config or SandboxConfig()

    def run(self, code: str) -> str:
        queue = multiprocessing.Queue()
        worker = SandboxWorker(code, self.tools, self.config, queue)
        process = multiprocessing.Process(target=worker)
        process.start()
        process.join(timeout=self.config.max_execution_time_seconds)

        if process.is_alive():
            process.terminate()
            process.join()
            ret = "ERROR: Execution timed out after "
            ret += f"{self.config.max_execution_time_seconds}s."
            return ret

        result = queue.get()

        if result["final_answer"] is not None:
            raise FinalAnswerSignal(result["final_answer"])

        return result["error"] or result["output"] or "(no output)"
