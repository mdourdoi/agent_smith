import json
import uuid
import subprocess
import threading
from pathlib import Path

from core.sandbox_config import SandboxConfig
from core.final_answer_signal import FinalAnswerSignal

# Directory holding sandbox_server.py, mounted into the container.
CORE_DIR = Path(__file__).parent
MOUNT_PATH = "/agent"
SERVER_IN_CONTAINER = f"{MOUNT_PATH}/sandbox_server.py"


class Sandbox:
    """Host side of the sandbox. Runs LLM code in an isolated Docker
    container and wraps an optional MCP client: when the code calls a
    tool proxy, the container emits a tool_call, which this class routes
    to the MCP client (running here on the host, outside the container).
    """

    def __init__(
        self,
        image: str,
        config: SandboxConfig | None = None,
        mcp_client=None,
    ):
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
        """Boot the container (code mounted) and launch the server."""
        subprocess.run(
            [
                "docker", "run", "-d", "--rm",
                "--name", self.container_name,
                "--network", "none",
                "--memory", f"{self.config.max_memory_mb}m",
                "-v", f"{CORE_DIR}:{MOUNT_PATH}:ro",
                self.image,
                "sleep", "infinity",
            ],
            check=True,
            capture_output=True,
        )
        self._launch_server()

    def _launch_server(self) -> None:
        """Start (or restart) the server process inside the container.
        Tool names are passed so the server can expose them as proxies."""
        tool_arg = ",".join(self._tool_names())
        self._proc = subprocess.Popen(
            ["docker", "exec", "-i", self.container_name,
             "python", "-u", SERVER_IN_CONTAINER, tool_arg],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def run(self, code: str) -> str:
        """Send code to the server, return the observation. Tool calls
        that arrive mid-execution are handled here and do not count
        toward the sandbox timeout (subject V.2)."""
        if self._proc is None:
            raise RuntimeError("Sandbox not started. Call start() first.")

        self._send({"code": code})

        while True:
            line = self._read_with_timeout(
                self.config.max_execution_time_seconds
            )
            if line is None:
                self._restart_container()
                return (
                    "ERROR: Execution timed out after "
                    f"{self.config.max_execution_time_seconds}s "
                    "(sandbox was restarted, previous variables are lost)."
                )

            msg = json.loads(line)

            # A tool call: run the real tool on the host, feed the result
            # back into the container, then keep reading the same block.
            if "tool_call" in msg:
                self._handle_tool_call(msg["tool_call"])
                continue

            if msg.get("final_answer") is not None:
                raise FinalAnswerSignal(msg["final_answer"])

            return msg.get("error") or msg.get("output") or "(no output)"

    def _handle_tool_call(self, call: dict) -> None:
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
        """Read one response line, or None if it takes too long."""
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
        if self._proc is not None:
            self._proc.terminate()
            self._proc = None
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True,
        )