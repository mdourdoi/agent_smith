from mcp.server.fastmcp import FastMCP
from typing import List


mcp = FastMCP("agent_smith")


@mcp.tool()
def run_tests(code: str, tests: List[str]) -> str:
    """
    Executes the code passed as a parameter using
    the tests passed as a parameter

    Args:
        code: Code to test
        tests: Tests to run on the code

    Returns:
        Returns whether the code is correct or not.
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
