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
    def __init__(self):
        # The persistent namespace: variables defined in one request
        # remain available in the next one.
        self.namespace: dict = {}
        self._install_final_answer()

    def _install_final_answer(self) -> None:
        """final_answer stores its value in a holder we can read after exec."""
        self._final_answer_holder: dict = {}

        def final_answer(answer):
            self._final_answer_holder["value"] = answer

        self.namespace["final_answer"] = final_answer

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
        """Main loop: one JSON request per line in, one response per line out.
        """
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._respond({"output": "", "final_answer": None,
                               "error": "ERROR: invalid JSON request"})
                continue

            result = self.execute(request.get("code", ""))
            self._respond(result)

    def _respond(self, payload: dict) -> None:
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    SandboxServer().serve()
