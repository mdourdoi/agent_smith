"""MBPP tool server: runs a candidate solution against its tests.

Serves on stdio by default; `python mcp_tools_mbpp.py http` serves the same
tools over streamable HTTP instead (endpoint http://127.0.0.1:8000/mcp).
"""
from mcp.server.fastmcp import FastMCP
from typing import List
import json
import subprocess
import sys

mcp = FastMCP("MBPP_SERV")

RUN_TESTS_TIMEOUT = 15


def _result(success: bool, output: str) -> str:
    return json.dumps({"success": success, "output": output})


@mcp.tool()
def run_tests(code: str, test_list: List[str]) -> str:
    """Run the given code against the task's assertions. Returns a JSON
    string {"success": bool, "output": str} - output confirms all tests
    passed, or lists the failing assertions.
    """
    script = code + "\n"
    for i, test in enumerate(test_list):
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
        return _result(False,
                       f"Timeout: tests did not finish within "
                       f"{RUN_TESTS_TIMEOUT}s (possible infinite loop in "
                       "the solution).")

    if proc.returncode != 0 and not proc.stdout:
        return _result(False,
                       f"Error running solution:\n{proc.stderr.strip()}")
    failures = [ln for ln in proc.stdout.splitlines() if ln.startswith("FAIL")]
    if not failures:
        return _result(True, "All tests passed.")
    return _result(False,
                   f"{len(failures)} test(s) failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["http"]:
        mcp.run(transport="streamable-http")
    elif not args:
        mcp.run()
    else:
        print("usage: python mcp_tools_mbpp.py [http]", file=sys.stderr)
        sys.exit(2)
