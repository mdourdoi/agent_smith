import argparse
import sys
from pathlib import Path

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig


def load_sandbox_config(config_path: str | None) -> SandboxConfig:
    if config_path is None:
        return SandboxConfig()
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(
            f"Sandbox config file not found: {config_file}"
        )
    return SandboxConfig.from_json(str(config_file))


def connect_mcp_client(mcp_stdio: str | None, mcp_server: str | None):
    if not mcp_stdio and not mcp_server:
        return None

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "serveur"))
    from mcp_client import MCPClientBridge

    client = MCPClientBridge()
    if mcp_stdio:
        client.connect_stdio(mcp_stdio)
    else:
        client.connect_http(mcp_server)
    return client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Python code inside an isolated sandbox container."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--code",
        help="Python code to execute in the sandbox.",
    )
    group.add_argument(
        "--file",
        help=(
            "Path to a Python file whose contents will be executed in the "
            "sandbox."
        ),
    )
    parser.add_argument(
        "--sandbox-config",
        default=None,
        help="Path to a JSON sandbox configuration file.",
    )
    parser.add_argument(
        "--image",
        default="python:3.11-slim",
        help="Docker image used for the sandbox container.",
    )
    parser.add_argument(
        "--mcp-stdio",
        default=None,
        help=(
            "Command to launch an MCP server over stdio, e.g. "
            "'serveur/mcp_tools_swebench.py'."
        ),
    )
    parser.add_argument(
        "--mcp-server",
        default=None,
        help="URL of an MCP server over HTTP.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code = args.code
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}", file=sys.stderr)
            return 1
        code = file_path.read_text(encoding="utf-8")

    try:
        sandbox_config = load_sandbox_config(args.sandbox_config)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    mcp_client = None
    try:
        if args.mcp_stdio or args.mcp_server:
            mcp_client = connect_mcp_client(args.mcp_stdio, args.mcp_server)
    except Exception as exc:
        print(
            f"ERROR: failed to initialize MCP client: {exc}",
            file=sys.stderr,
        )
        return 1

    sandbox = Sandbox(
        image=args.image,
        config=sandbox_config,
        mcp_client=mcp_client,
    )

    try:
        sandbox.start()
        result = sandbox.run(code)
        print(result)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        sandbox.cleanup()
        if mcp_client is not None:
            mcp_client.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
