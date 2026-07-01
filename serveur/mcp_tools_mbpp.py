from mcp.server.fastmcp import FastMCP
from typing import List
import subprocess
import sys


mcp = FastMCP("MBPP_SERV")

RUN_TESTS_TIMEOUT = 15


@mcp.tool()
def run_tests(code: str, tests: List[str]) -> str:
    """Run the MBPP task's tests against a candidate solution.

    The provided `code` (the function definition) and each assertion in
    `tests` are executed together in an isolated Python subprocess. This
    keeps a faulty solution (infinite loop, crash, exit) from affecting
    the MCP server itself.

    Returns "All tests passed." on success, otherwise a report listing
    each failing assertion and its error.
    """
    script = code + "\n"
    for i, test in enumerate(tests):
        script += (
            f"try:\n"
            f"    {test}\n"
            f"    print('PASS {i}')\n"
            f"except Exception as _e:\n"
            f"    print(f'FAIL {i}: {{type(_e).__name__}}: {{_e}}')\n"
        )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=RUN_TESTS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return (
            f"Timeout: tests did not finish within {RUN_TESTS_TIMEOUT}s "
            "(possible infinite loop in the solution)."
        )
    if proc.returncode != 0 and not proc.stdout:
        return f"Error running solution:\n{proc.stderr.strip()}"
    failures = [
        line for line in proc.stdout.splitlines()
        if line.startswith("FAIL")
    ]
    if not failures:
        return "All tests passed."
    report = "\n".join(failures)
    return f"{len(failures)} test(s) failed:\n{report}"


if __name__ == "__main__":
    mcp.run()