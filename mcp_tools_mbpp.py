"""MBPP tool server: runs a candidate solution against its tests."""
from mcp.server.fastmcp import FastMCP
from typing import List
import subprocess
import sys

mcp = FastMCP("MBPP_SERV")

RUN_TESTS_TIMEOUT = 15


@mcp.tool()
def run_tests(code: str, tests: List[str]) -> str:
    """Run the given code against the task's assertions. Returns "All tests
    passed." or the list of failing assertions.
    """
    # code + assertions run in a separate process so a bad solution (crash,
    # infinite loop) can't take down this server.
    script = code + "\n"
    for i, test in enumerate(tests):
        script += (
            f"try:\n"
            f"    {test}\n"
            f"    print('PASS {i}')\n"
            f"except Exception as _e:\n"
            f"    print(f'FAIL {i}: {{type(_e).__name__}}: {{_e}}')\n")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=RUN_TESTS_TIMEOUT)
    except subprocess.TimeoutExpired:
        return (f"Timeout: tests did not finish within {RUN_TESTS_TIMEOUT}s "
                "(possible infinite loop in the solution).")

    if proc.returncode != 0 and not proc.stdout:
        return f"Error running solution:\n{proc.stderr.strip()}"
    failures = [ln for ln in proc.stdout.splitlines() if ln.startswith("FAIL")]
    if not failures:
        return "All tests passed."
    return f"{len(failures)} test(s) failed:\n" + "\n".join(failures)


if __name__ == "__main__":
    mcp.run()
