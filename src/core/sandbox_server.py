import sys
import io
import json
import contextlib


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
            "output": buf.getvalue(),
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
