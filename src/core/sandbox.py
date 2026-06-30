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
    def __init__(self, image: str, config: SandboxConfig | None = None):
        self.image = image
        self.config = config or SandboxConfig()
        self.container_name = f"agent_smith_{uuid.uuid4().hex[:12]}"
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        """Boot the container (with our code mounted) and launch the server."""
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
        """Start (or restart) the server process inside the container."""
        self._proc = subprocess.Popen(
            ["docker", "exec", "-i", self.container_name,
             "python", "-u", SERVER_IN_CONTAINER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def run(self, code: str) -> str:
        """Send code to the server, return the observation."""
        if self._proc is None:
            raise RuntimeError("Sandbox not started. Call start() first.")

        self._proc.stdin.write(json.dumps({"code": code}) + "\n")
        self._proc.stdin.flush()

        response_line = self._read_with_timeout(
            self.config.max_execution_time_seconds
        )

        if response_line is None:
            self._restart_container()
            return (
                "ERROR: Execution timed out after "
                f"{self.config.max_execution_time_seconds}s "
                "(sandbox was restarted, previous variables are lost)."
            )

        result = json.loads(response_line)

        if result["final_answer"] is not None:
            raise FinalAnswerSignal(result["final_answer"])

        return result["error"] or result["output"] or "(no output)"

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
