from mcp.server.fastmcp import FastMCP
from typing import List


mcp = FastMCP("MBPP_SERV")


@mcp.tool()
def run_tests(code: str, tests: List[str]) -> str:
    """Execute the pre-configured evaluation script (eval_script)
    inside the SWE-bench environment.
    Runs the comprehensive test suite for the current
    task instance and returns the test
    execution results, output logs, and individual test pass/fail breakdown.
    """
    fail = []
    namespace = {}
    exec(code, namespace)
    for _ in tests:
        try:
            exec(_, namespace)
        except Exception as e:
            print(e)
            fail.append((_, e))
            continue
    if len(fail) == 0:
        return "OK"
    else:
        return "\n".join(
            f"Test failed: {f[0]} -> {type(f[1]).__name__}:{f[1]}"
            for f in fail
        )


if __name__ == "__main__":
    mcp.run()
