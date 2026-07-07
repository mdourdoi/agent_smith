"""Host side of the sandbox.

The model's code runs in a throwaway Docker container, never on the host.
We talk to a small server inside that container over stdin/stdout. When the
code calls an MCP tool, the container asks us to run it here (outside the
sandbox) and we send the result back.
"""
import json
import time
import uuid
import subprocess
import threading
from pathlib import Path

from core.models import SandboxConfig

SERVER_LOCAL = Path(__file__).parent / "sandbox_server.py"
SERVER_IN_CONTAINER = "/agent/sandbox_server.py"


class FinalAnswerSignal(Exception):
    """Raised when the sandboxed code calls final_answer(...)."""
    def __init__(self, answer: str, output: str = ""):
        self.answer = answer
        self.output = output
        super().__init__(answer)


class Sandbox:
    def __init__(self, image: str, config: SandboxConfig | None = None,
                 mcp_client=None):
        self.image = image
        self.config = config or SandboxConfig()
        self.mcp_client = mcp_client
        self.container_name = f"agent_smith_{uuid.uuid4().hex[:12]}"
        self._proc: subprocess.Popen | None = None

    def _tool_names(self) -> list[str]:
        if self.mcp_client is None:
            return []
        return self.mcp_client.get_available_tools_names()

    def start(self) -> None:
        """Boot the container (no network, capped memory) with the server as
        its own main process, piped directly to us.

        Running the server as PID 1 (instead of a detached `sleep infinity`
        plus a separate `docker exec`) means the container's lifetime is tied
        to this pipe: if our process dies for any reason - including
        SIGKILL, which we can't catch - the kernel closes our end, the
        server sees EOF and exits, and `--rm` removes the container. No
        Python-level cleanup code has to run for that to happen.
        """
        tool_arg = ",".join(self._tool_names())
        config_arg = json.dumps({
            "authorized_imports": self.config.authorized_imports,
            "allowed_directories": self.config.allowed_directories,
            "max_memory_mb": self.config.max_memory_mb,
        })
        self._proc = subprocess.Popen(
            [
                "docker", "run", "--rm", "-i",
                "--name", self.container_name,
                "--network", "none",
                "--memory", f"{self.config.max_memory_mb}m",
                "-v", f"{SERVER_LOCAL}:{SERVER_IN_CONTAINER}:ro",
                self.image,
                "python", "-u", SERVER_IN_CONTAINER, tool_arg, config_arg,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def run(self, code: str) -> str:
        """Run one block of code and return what the model should observe."""
        if self._proc is None:
            raise RuntimeError("Sandbox not started. Call start() first.")

        self._send({"code": code})

        deadline = time.monotonic() + self.config.max_execution_time_seconds
        partial: list[str] = []

        while True:
            remaining = deadline - time.monotonic()
            line = self._read_with_timeout(max(remaining, 0))
            if line is None:
                self._restart_container()
                note = (
                    "ERROR: Execution timed out after "
                    f"{self.config.max_execution_time_seconds}s "
                    "(sandbox was restarted, previous variables are lost)."
                )
                return f"{''.join(partial)}{note}" if partial else note

            msg = json.loads(line)

            if "partial_output" in msg:
                partial.append(msg["partial_output"])
                continue

            if "tool_call" in msg:
                self._run_tool_on_host(msg["tool_call"])
                continue

            if msg.get("control") == "SystemExit":
                raise SystemExit("Sandboxed code raised SystemExit.")
            if msg.get("control") == "KeyboardInterrupt":
                raise KeyboardInterrupt(
                    "Sandboxed code raised KeyboardInterrupt.")

            if msg.get("final_answer") is not None:
                raise FinalAnswerSignal(msg["final_answer"], "".join(partial))

            return msg.get("error") or msg.get("output") or "(no output)"

    def _run_tool_on_host(self, call: dict) -> None:
        """Run the real MCP tool the code asked for, and send its result
        back into the container."""
        name = call.get("name", "")
        args = call.get("args", {})
        if self.mcp_client is None:
            result = f"ERROR: no MCP server connected, cannot call {name}."
        else:
            result = self.mcp_client.call_tool_sync(name, args)
        self._send({"tool_result": result})

    def _send(self, payload: dict) -> None:
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

    def _read_with_timeout(self, timeout: int) -> str | None:
        """Read one line from the server, or None if it takes too long."""
        result: list[str] = []

        def reader():
            line = self._proc.stdout.readline()
            if line:
                result.append(line)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            return None
        return result[0] if result else None

    def _restart_container(self) -> None:
        self.cleanup()
        self.start()

    def cleanup(self) -> None:
        """Best-effort teardown; never raises.

        The docker client is terminated and *waited on* before the rm -f:
        killed mid-creation, it can otherwise leave a never-started
        container that --rm will never reap, registered by the daemon
        after our rm -f already ran.
        """
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
            self._proc = None
        try:
            subprocess.run(["docker", "rm", "-f", self.container_name],
                           capture_output=True)
        except OSError:
            pass
