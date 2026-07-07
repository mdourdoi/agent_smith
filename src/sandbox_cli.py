"""CLI for the sandbox.

    uv run sandbox                                  # interactive
    uv run sandbox config.json                      # custom config
    uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" config.json
    uv run sandbox --mcp-server <URL>

Runs Python from --code, --file, or stdin inside the sandbox and prints
what happened.
"""
import argparse
import sys
from pathlib import Path

from core.sandbox import Sandbox, FinalAnswerSignal
from core.models import SandboxConfig
from core.mcp import MCPClientBridge

SANDBOX_IMAGE = "python:3.11-slim"


def load_config(path: str | None) -> SandboxConfig:
    if path is None:
        return SandboxConfig()
    if not Path(path).exists():
        raise FileNotFoundError(f"Sandbox config file not found: {path}")
    return SandboxConfig.from_json(path)


def connect_mcp(mcp_stdio: str | None, mcp_server: str | None):
    if not mcp_stdio and not mcp_server:
        return None
    client = MCPClientBridge()
    if mcp_server:
        client.connect_http(mcp_server)
    else:
        client.connect_stdio(mcp_stdio)
    return client


def run(sandbox: Sandbox, code: str) -> str:
    try:
        return sandbox.run(code)
    except FinalAnswerSignal as signal:
        prefix = f"{signal.output}\n" if signal.output.strip() else ""
        return f"{prefix}final_answer: {signal.answer}"


def interactive(sandbox: Sandbox) -> None:
    """No --code/--file given: read the whole program from stdin (piped, or
    typed then Ctrl-D) and run it in the sandbox."""
    if sys.stdin.isatty():
        print("Type Python, then Ctrl-D to run it in the sandbox.")
    code = sys.stdin.read()
    if code.strip():
        print(run(sandbox, code))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Python code inside the isolated sandbox.")
    parser.add_argument("config", nargs="?", default=None,
                        help="Optional JSON sandbox config file.")
    parser.add_argument("--mcp-stdio", default=None)
    parser.add_argument("--mcp-server", default=None)
    parser.add_argument("--code", default=None)
    parser.add_argument("--file", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        mcp = connect_mcp(args.mcp_stdio, args.mcp_server)
    except Exception as exc:
        print(f"ERROR: failed to start MCP client: {exc}", file=sys.stderr)
        return 1

    sandbox = Sandbox(SANDBOX_IMAGE, config, mcp)
    try:
        sandbox.start()
        if args.file:
            if not Path(args.file).exists():
                print(f"ERROR: File not found: {args.file}", file=sys.stderr)
                return 1
            print(run(sandbox, Path(args.file).read_text(encoding="utf-8")))
        elif args.code:
            print(run(sandbox, args.code))
        else:
            interactive(sandbox)
    except KeyboardInterrupt as exc:
        msg = f"Interrupted: {exc}" if str(exc) else "Interrupted."
        print(msg, file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        sandbox.cleanup()
        if mcp is not None:
            mcp.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
