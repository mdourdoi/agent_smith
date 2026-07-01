import sys
import io
import json
import contextlib

# Cap on how much stdout we send back per execution. Beyond this the
# output is truncated with an explicit notice, so the LLM knows it did
# not see everything (subject V.1: feedback on truncation) and so a huge
# output cannot blow the input-token budget on the next step.
MAX_OUTPUT_CHARS = 8000


class SandboxServer:
    """Runs inside the container. Executes LLM code in a persistent
    namespace. MCP tools are exposed as proxy functions: calling one
    emits a tool_call to the host over stdout and blocks on stdin for
    the result. The real tool runs on the host, outside the sandbox
    (subject V.2: MCP tool actions happen outside the sandbox).
    """

    def __init__(self, tool_names: list[str] | None = None):
        self.namespace: dict = {}
        self._install_final_answer()
        for name in (tool_names or []):
            self.namespace[name] = self._make_tool_proxy(name)

    def _install_final_answer(self) -> None:
        """final_answer stores its value in a holder we read after exec."""
        self._final_answer_holder: dict = {}

        def final_answer(answer):
            self._final_answer_holder["value"] = answer

        self.namespace["final_answer"] = final_answer

    def _make_tool_proxy(self, name: str):
        """Return a function that, when called, asks the host to run the
        real MCP tool and returns its result. It talks on the real
        stdio streams (__stdout__/__stdin__), not the ones redirect_stdout
        swaps in during execute(), so the tool_call reaches the host and
        not the captured output buffer."""
        def proxy(**kwargs):
            payload = {"tool_call": {"name": name, "args": kwargs}}
            sys.__stdout__.write(json.dumps(payload) + "\n")
            sys.__stdout__.flush()
            line = sys.__stdin__.readline()
            try:
                reply = json.loads(line) if line.strip() else {}
            except json.JSONDecodeError:
                reply = {}
            return reply.get("tool_result", "")
        return proxy

    def _truncate(self, text: str) -> str:
        if len(text) <= MAX_OUTPUT_CHARS:
            return text
        head = text[:MAX_OUTPUT_CHARS]
        dropped = len(text) - MAX_OUTPUT_CHARS
        return (
            f"{head}\n"
            f"... [output truncated: {dropped} more characters were "
            f"dropped because it exceeded {MAX_OUTPUT_CHARS} characters]"
        )

    def execute(self, code: str) -> dict:
        self._final_answer_holder.clear()
        buf = io.StringIO()
        error = None

        try:
            with contextlib.redirect_stdout(buf):
                exec(code, self.namespace)
        except Exception as e:
            error = f"ERROR: {type(e).__name__}: {e}"

        return {
            "output": self._truncate(buf.getvalue()),
            "final_answer": self._final_answer_holder.get("value"),
            "error": error,
        }

    def serve(self) -> None:
        """Main loop: read one request per line, run it, respond."""
        while True:
            request = self._read_line()
            if request is None:
                break
            if "code" not in request:
                continue
            self._emit(self.execute(request["code"]))

    def _read_line(self) -> dict | None:
        """Read and parse one JSON line from stdin (None at EOF)."""
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            return {}
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {}

    def _emit(self, payload: dict) -> None:
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    names = sys.argv[1].split(",") if len(sys.argv) > 1 and sys.argv[1] else []
    SandboxServer(tool_names=names).serve()