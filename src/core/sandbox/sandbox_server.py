"""Runs inside the sandbox container. Standard library only (the image has
nothing else installed).

It runs the model's code with three limits enforced in Python:
  - imports: only what the allowlist permits
  - builtins: the dangerous ones are removed
  - open(): only paths under the allowed directories

Network, memory and timeout are handled outside, by Docker and the host.

Communication with the host is line-delimited JSON over stdin/stdout. The
code's own print() output is captured into a buffer (we override print),
so stdout is used *only* for that protocol - no juggling of stdout.

MCP tools show up as functions the code can call; calling one sends the
call to the host and returns whatever the host answers.
"""
import sys
import os
import json
import builtins as _builtins

MAX_OUTPUT_CHARS = 8000

_BLOCKED_BUILTINS = (
    "eval", "exec", "compile", "input",
    "breakpoint", "help", "exit", "quit",
)


def _import_allowed(name: str, authorized: list[str]) -> bool:
    """A name matches "math" (exact) or "math.*" (that module and its
    submodules)."""
    for pattern in authorized:
        if pattern == name:
            return True
        if pattern.endswith(".*"):
            base = pattern[:-2]
            if name == base or name.startswith(base + "."):
                return True
    return False


def _within(path: str, directory: str) -> bool:
    real_dir = os.path.realpath(directory)
    return path == real_dir or path.startswith(real_dir + os.sep)


class SandboxServer:
    def __init__(self, tool_names=None, authorized_imports=None,
                 allowed_directories=None):
        self.authorized_imports = authorized_imports or []
        self.allowed_directories = allowed_directories or []
        self._final_answer: dict = {}
        self._output: list = []
        self.namespace: dict = {"__builtins__": self._safe_builtins()}
        self.namespace["final_answer"] = self._final_answer_fn()
        for name in (tool_names or []):
            self.namespace[name] = self._make_tool_proxy(name)

    def _safe_builtins(self) -> dict:
        safe = dict(vars(_builtins))
        for name in _BLOCKED_BUILTINS:
            safe.pop(name, None)
        safe["__import__"] = self._safe_import
        safe["open"] = self._safe_open
        safe["print"] = self._capture_print
        return safe

    def _capture_print(self, *args, sep=" ", end="\n", file=None, **_):
        text = sep.join(str(a) for a in args) + end
        if file is None:
            self._output.append(text)
        else:
            file.write(text)

    def _safe_import(self, name, globals=None, locals=None,
                     fromlist=(), level=0):
        if not _import_allowed(name, self.authorized_imports):
            allowed = ", ".join(self.authorized_imports) or "(none)"
            raise ImportError(
                f"Import of '{name}' is blocked by the sandbox. "
                f"Allowed imports: {allowed}.")
        return _builtins.__import__(name, globals, locals, fromlist, level)

    def _safe_open(self, file, mode="r", *args, **kwargs):
        path = os.path.realpath(os.fspath(file))
        if not any(_within(path, d) for d in self.allowed_directories):
            allowed = ", ".join(self.allowed_directories) or "(none)"
            raise PermissionError(
                f"Access to '{file}' is denied by the sandbox. "
                f"Allowed directories: {allowed}.")
        return _builtins.open(file, mode, *args, **kwargs)

    def _final_answer_fn(self):
        def final_answer(answer):
            self._final_answer["value"] = answer
        return final_answer

    def _make_tool_proxy(self, name: str):
        """Build the stand-in function the code calls for an MCP tool.

        The real tool runs on the host, outside this container, so this
        proxy can't do the work. It sends the call to the host and returns
        whatever the host answers.
        """
        def call_tool(**kwargs):
            self._send({"tool_call": {"name": name, "args": kwargs}})
            return (self._receive() or {}).get("tool_result", "")
        return call_tool

    def _send(self, message: dict) -> None:
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    def _receive(self) -> dict | None:
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

    def _truncate(self, text: str) -> str:
        if len(text) <= MAX_OUTPUT_CHARS:
            return text
        dropped = len(text) - MAX_OUTPUT_CHARS
        return (f"{text[:MAX_OUTPUT_CHARS]}\n"
                f"... [output truncated: {dropped} more characters]")

    def execute(self, code: str) -> dict:
        self._final_answer.clear()
        self._output = []
        error = None
        control = None
        try:
            exec(code, self.namespace)
        except (KeyboardInterrupt, SystemExit) as e:
            control = type(e).__name__
        except Exception as e:
            error = f"ERROR: {type(e).__name__}: {e}"
        return {
            "output": self._truncate("".join(self._output)),
            "final_answer": self._final_answer.get("value"),
            "error": error,
            "control": control,
        }

    def serve(self) -> None:
        while True:
            request = self._receive()
            if request is None:
                break
            if "code" in request:
                self._send(self.execute(request["code"]))


def _parse_config(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    names = sys.argv[1].split(",") if len(sys.argv) > 1 and sys.argv[1] else []
    config = _parse_config(sys.argv[2] if len(sys.argv) > 2 else None)
    SandboxServer(
        tool_names=names,
        authorized_imports=config.get("authorized_imports", []),
        allowed_directories=config.get("allowed_directories", []),
    ).serve()
