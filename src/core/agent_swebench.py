import os
import sys
import json
import argparse

from dotenv import load_dotenv

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig
from core.llm_client import LLMClient, InvalidModelError, AllKeysExhausted
from core.orchestrator_swebench import SWEBenchOrchestrator
from core.prompts import SWEBENCH_SYSTEM_PROMPT, build_swebench_task_message
from core.providers import get_provider, DEFAULT_PROVIDER
from core.console import Console


def load_task(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_api_keys(env_key: str) -> list[str]:
    raw = os.environ.get(env_key, "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return keys


def connect_mcp(mcp_stdio: str | None, mcp_server: str | None):
    if not mcp_stdio and not mcp_server:
        return None

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, os.path.join(repo_root, "serveur"))
    from mcp_client import MCPClientBridge

    client = MCPClientBridge()
    if mcp_stdio:
        client.connect_stdio(mcp_stdio)
    else:
        client.connect_http(mcp_server)
    return client


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Solve one SWE-bench task.")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER,
                        help=f"Provider name (default: {DEFAULT_PROVIDER}).")
    parser.add_argument("--mcp-stdio", default=None,
                        help="Command to launch an MCP server over stdio, "
                             "e.g. 'serveur/mcp_tools_swebench.py'.")
    parser.add_argument("--mcp-server", default=None,
                        help="URL of an MCP server over HTTP.")
    parser.add_argument("--sandbox-config", default=None,
                        help="JSON file containing sandbox configuration.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not args.mcp_stdio and not args.mcp_server:
        print(
            "ERROR: an MCP server is required. Provide --mcp-stdio "
            "<server script> or --mcp-server <url>.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        provider = get_provider(args.provider)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    provider_url = provider.url
    api_keys = load_api_keys(provider.env_key)
    if not api_keys:
        print(
            f"ERROR: no API keys found. Set {provider.env_key} in your "
            f".env (comma-separated for multiple keys).",
            file=sys.stderr,
        )
        sys.exit(1)

    task = load_task(args.task_file)
    task_id = str(task.get("instance_id", task.get("task_id", "unknown")))

    llm = LLMClient(
        api_keys=api_keys,
        model=args.model_name,
        provider_url=provider_url,
    )

    mcp_client = connect_mcp(args.mcp_stdio, args.mcp_server)
    Console(verbose=args.verbose).mcp_connected(
        mcp_client.get_available_tools_names() if mcp_client else []
    )
    system_prompt = SWEBENCH_SYSTEM_PROMPT + build_swebench_task_message(task)
    sandbox_config = (
        SandboxConfig.from_json(args.sandbox_config)
        if args.sandbox_config
        else SandboxConfig()
    )
    sandbox = Sandbox(
        image="python:3.11-slim",
        config=sandbox_config,
        mcp_client=mcp_client,
    )

    orchestrator = SWEBenchOrchestrator(
        sandbox=sandbox,
        call_llm=llm.call,
        system_prompt=system_prompt,
        task_id=task_id,
        model_name=args.model_name,
        api_url=provider_url,
        verbose=args.verbose,
    )

    try:
        solution = orchestrator.run(system_prompt)
    except InvalidModelError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except AllKeysExhausted as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if mcp_client is not None:
            mcp_client.disconnect()

    with open(args.output, "w") as f:
        f.write(solution.model_dump_json(indent=2))

    print(f"Solved: {solution.success} | "
          f"iterations: {solution.iterations} | "
          f"output written to {args.output}")


if __name__ == "__main__":
    main()
