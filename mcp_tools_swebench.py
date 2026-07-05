"""SWE-bench tool server.

The repository to fix lives at /testbed inside a task-specific Docker
container. This server owns that container and runs every tool inside it
with `docker exec`, so file reads, edits and test runs happen there and
not in the sandbox.

Configure the container with one of:
  - SWEBENCH_TASK_FILE : a dumped task.json (image + eval script)
  - SWEBENCH_IMAGE     : a Docker image (overrides the task file image)
  - SWEBENCH_CONTAINER : an already-running container to reuse (not removed)

The container is started on the first tool call and removed at exit.
"""
import atexit
import json
import os
import re
import shlex
import signal
import subprocess
import uuid

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("SWE_SERV")

WORKDIR = "/testbed"
EXEC_TIMEOUT = 120
COMMAND_TIMEOUT = 300
EVAL_TIMEOUT = int(os.environ.get("SWEBENCH_EVAL_TIMEOUT", "400"))
MAX_TEST_OUTPUT = 12000


class SweContainer:
    """The SWE-bench container the tools run inside."""

    def __init__(self):
        self.name = os.environ.get("SWEBENCH_CONTAINER") or None
        self.owned = self.name is None
        self.image = os.environ.get("SWEBENCH_IMAGE", "")
        self.eval_script = ""

        task_file = os.environ.get("SWEBENCH_TASK_FILE")
        if task_file and os.path.exists(task_file):
            with open(task_file, encoding="utf-8") as fd:
                task = json.load(fd)
            self.image = self.image or task.get("docker_image", "")
            self.eval_script = task.get("eval_script", "")

    def ensure(self) -> str:
        """Start the container on first use and return its name."""
        if self.name:
            return self.name
        if not self.image:
            raise RuntimeError(
                "No SWE-bench container configured. Set SWEBENCH_TASK_FILE, "
                "SWEBENCH_IMAGE or SWEBENCH_CONTAINER.")
        name = "agent_smith_swe_" + uuid.uuid4().hex[:12]
        # docker run pulls the image if it isn't already local.
        subprocess.run(
            ["docker", "run", "-d", "--name", name, self.image,
             "tail", "-f", "/dev/null"],
            check=True, capture_output=True, text=True)
        self.name = name
        self.owned = True
        # git won't touch a tree owned by someone else without this.
        subprocess.run(
            ["docker", "exec", name, "git", "config", "--global",
             "--add", "safe.directory", WORKDIR],
            capture_output=True, text=True)
        return name

    def cleanup(self) -> None:
        if self.name and self.owned:
            subprocess.run(["docker", "rm", "-f", self.name],
                           capture_output=True, text=True)
            self.name = None


CONTAINER = SweContainer()


def _exec(args, input_text=None, workdir=None, timeout=EXEC_TIMEOUT):
    """Run a command in the container. Returns (exit_code, stdout, stderr)."""
    container = CONTAINER.ensure()
    cmd = ["docker", "exec"]
    if input_text is not None:
        cmd.append("-i")
    if workdir:
        cmd += ["-w", workdir]
    cmd.append(container)
    cmd += args
    try:
        proc = subprocess.run(cmd, input=input_text, capture_output=True,
                              text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "Timed out after %ds inside the container." % timeout
    return proc.returncode, proc.stdout, proc.stderr


def _format_grep(out: str) -> str:
    """Turn grep's 'path:line:content' into 'path:line content'."""
    lines = []
    for line in out.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3:
            lines.append("%s:%s %s" % tuple(parts))
        elif line.strip():
            lines.append(line)
    return "\n".join(lines)


@mcp.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read a file between two line numbers, one '<number>: <text>' each."""
    rc, out, err = _exec(["cat", "--", filepath])
    if rc != 0:
        reason = err.strip() or "not found"
        return "Error reading '%s': %s" % (filepath, reason)
    lines = out.splitlines()
    total = len(lines)
    if start_line > end_line:
        return "Error: start_line (%d) > end_line (%d)." % (
            start_line, end_line)
    if (start_line < 1 or end_line < 1
            or start_line > total or end_line > total):
        return "Error: lines %d-%d out of range (file has %d lines)." % (
            start_line, end_line, total)
    return "\n".join("%d: %s" % (i, lines[i - 1])
                     for i in range(start_line, end_line + 1))


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Replace an exact block of text in a file.

    old_str must match the file exactly, indentation included: copy it from
    read_file's output, dropping the 'N: ' prefix. Keep it short and unique
    (often one line) so the indentation is easy to get right. A syntax error
    introduced in a .py file is reported back.
    """
    rc, out, err = _exec(["cat", "--", filepath])
    if rc != 0:
        return "Error: cannot read '%s': %s" % (filepath, err.strip())
    count = out.count(old_str)
    if count == 0:
        return ("Error: old_str not found in '%s'. Copy the lines exactly "
                "from read_file (drop the 'N: ' prefix), keeping every "
                "leading space." % filepath)
    new_content = out.replace(old_str, new_str)

    warning = ""
    if filepath.endswith(".py"):
        try:
            compile(new_content, filepath, "exec")
        except SyntaxError as e:
            warning = (" WARNING: the file now has a syntax error "
                       "(line %s: %s)." % (e.lineno, e.msg))

    rc, _, err = _exec(["sh", "-c", 'cat > "$1"', "_", filepath],
                       input_text=new_content)
    if rc != 0:
        return "Error writing '%s': %s" % (filepath, err.strip())
    return "Success: '%s' updated (%d replaced).%s" % (
        filepath, count, warning)


@mcp.tool()
def list_files(directory: str, pattern: str) -> str:
    """List files in a directory matching a glob pattern (e.g. '*.py')."""
    cmd = "find %s -name %s -type f 2>/dev/null | sort" % (
        shlex.quote(directory), shlex.quote(pattern))
    _, out, _ = _exec(["sh", "-c", cmd])
    files = [line for line in out.splitlines() if line.strip()]
    if not files:
        return "No files matching '%s' in '%s'." % (pattern, directory)
    return "\n".join(files)


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*") -> str:
    """grep-like search. Output is '/absolute/path.py:<line> <text>'."""
    cmd = "grep -rnI"
    if file_pattern and file_pattern != "*":
        cmd += " --include=%s" % shlex.quote(file_pattern)
    cmd += " -e %s %s 2>/dev/null" % (
        shlex.quote(pattern), shlex.quote(WORKDIR))
    _, out, _ = _exec(["sh", "-c", cmd])
    return _format_grep(out) or "No matches for '%s'." % pattern


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """Find where a function or class is defined (search_code format)."""
    ere = "^[[:space:]]*(def|class)[[:space:]]+" + re.escape(name) + "\\b"
    cmd = "grep -rnI -E --include=%s -e %s %s 2>/dev/null" % (
        shlex.quote("*.py"), shlex.quote(ere), shlex.quote(WORKDIR))
    _, out, _ = _exec(["sh", "-c", cmd])
    return _format_grep(out) or "Definition of '%s' not found." % name


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Find where a symbol is used across the repo (search_code format)."""
    cmd = "grep -rnwI --include=%s -e %s %s 2>/dev/null" % (
        shlex.quote("*.py"), shlex.quote(name), shlex.quote(WORKDIR))
    _, out, _ = _exec(["sh", "-c", cmd])
    return _format_grep(out) or "No references found for '%s'." % name


@mcp.tool()
def get_patch() -> str:
    """Return the git diff of every change made to the repo so far."""
    rc, out, err = _exec(["git", "-c", "core.fileMode=false", "diff"],
                         workdir=WORKDIR)
    if rc != 0:
        return "Error generating patch: %s" % err.strip()
    return out if out.strip() else "No changes made yet (empty diff)."


@mcp.tool()
def run_command(command: str, workdir: str = WORKDIR) -> str:
    """Run a shell command in the container (stdout, stderr, exit code)."""
    rc, out, err = _exec(["sh", "-c", command], workdir=workdir or WORKDIR,
                         timeout=COMMAND_TIMEOUT)
    return "Exit Code: %d\n--- STDOUT ---\n%s\n--- STDERR ---\n%s" % (
        rc, out or "(empty)", err or "(empty)")


@mcp.tool()
def run_tests() -> str:
    """Run the evaluation script and report which tests pass or fail."""
    if not CONTAINER.eval_script:
        return ("Error: no evaluation script configured (set "
                "SWEBENCH_TASK_FILE). Use run_command to run tests manually.")
    rc, _, err = _exec(["sh", "-c", "cat > /tmp/eval.sh"],
                       input_text=CONTAINER.eval_script)
    if rc != 0:
        return "Error preparing eval script: %s" % err.strip()
    rc, out, err = _exec(["bash", "/tmp/eval.sh"], timeout=EVAL_TIMEOUT)
    # Put the test output last: its pass/fail summary is at the very end,
    # so it survives the truncation below.
    parts = []
    if err.strip():
        parts.append("--- setup / stderr ---\n" + err.strip())
    parts.append("--- test output ---\n" + out.strip())
    combined = "\n".join(parts)
    if len(combined) > MAX_TEST_OUTPUT:
        dropped = len(combined) - MAX_TEST_OUTPUT
        combined = ("... [%d earlier characters truncated]\n" % dropped
                    + combined[-MAX_TEST_OUTPUT:])
    return combined


def _on_signal(signum, frame):
    CONTAINER.cleanup()
    raise SystemExit(0)


atexit.register(CONTAINER.cleanup)
for _sig in (getattr(signal, "SIGINT", None),
             getattr(signal, "SIGTERM", None)):
    if _sig is not None:
        try:
            signal.signal(_sig, _on_signal)
        except (ValueError, OSError):
            pass


if __name__ == "__main__":
    mcp.run()
