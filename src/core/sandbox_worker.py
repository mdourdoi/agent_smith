import io
import builtins
import resource
import contextlib
import multiprocessing
from pathlib import Path
from core.models import SandboxConfig


class SandboxWorker:
    def __init__(
            self,
            code: str,
            tools: dict,
            config: SandboxConfig,
            queue: multiprocessing.Queue):
        self.code = code
        self.tools = tools
        self.config = config
        self.queue = queue

    def _restricted_import(self, name: str, *args, **kwargs):
        base = name.split(".")[0]
        for p in self.config.authorized_imports:
            if p.endswith(".*"):
                if name == p[:-2] or name.startswith(p[:-1]):
                    return self._original_import(name, *args, **kwargs)
            elif name == p or base == p:
                return self._original_import(name, *args, **kwargs)
        raise ImportError(f"Import '{name}' is not allowed in the sandbox.")

    def _restricted_open(self, file, mode="r", *args, **kwargs):
        resolved = str(Path(str(file)).resolve())
        if not any(resolved.startswith(d)
                   for d in self.config.allowed_directories):
            raise PermissionError(f"Access to '{file}' is not allowed.")
        return self._original_open(file, mode, *args, **kwargs)

    def _build_namespace(self) -> dict:
        self._original_import = builtins.__import__
        self._original_open = builtins.open

        safe_builtins = vars(builtins).copy()
        safe_builtins["__import__"] = self._restricted_import
        safe_builtins["open"] = self._restricted_open
        for func in ("eval", "exec", "compile"):
            safe_builtins.pop(func, None)

        final_answer_holder = {}

        def final_answer(answer: str):
            final_answer_holder["value"] = answer

        return {
            "__builtins__": safe_builtins,
            "final_answer": final_answer,
            "_final_answer_holder": final_answer_holder,
            **self.tools}

    def __call__(self):
        limit = self.config.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

        namespace = self._build_namespace()
        buf = io.StringIO()
        error = None

        try:
            with contextlib.redirect_stdout(buf):
                exec(self.code, namespace)
        except Exception as e:
            error = f"ERROR: {type(e).__name__}: {e}"

        self.queue.put({
            "output": buf.getvalue(),
            "final_answer": namespace["_final_answer_holder"].get("value"),
            "error": error,
        })
