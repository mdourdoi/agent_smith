import os
import sys
import json
import argparse

from dotenv import load_dotenv

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig
from core.llm_client import LLMClient, InvalidModelError, AllKeysExhausted
from core.orchestrator_mbpp import MBPPOrchestrator, MBPP_DOCKER_IMAGE
from core.prompts import MBPP_SYSTEM_PROMPT, build_mbpp_task_message
from core.providers import get_provider, DEFAULT_PROVIDER
from core.console import Console


def load_task(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def get_tests(task: dict) -> list[str]:
    """The dumped task may use 'test_list' or 'public_test_list'."""
    return task.get("test_list") or task.get("public_test_list") or []


def load_api_keys(env_key: str) -> list[str]:
    """Read comma-separated API keys from the given env variable."""
    raw = os.environ.get(env_key, "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return keys


def connect_mcp(mcp_stdio: str | None, mcp_server: str | None):
    """Connect an MCP client if requested. Returns the client or None.

    The MCPClientBridge lives in the sibling 'serveur' package; we add it
    to sys.path so the agent can import it regardless of CWD.
    """
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


def build_tools_manual(client) -> str:
    """Generate a manual of the connected MCP tools from their schemas
    (subject V.2: manual generated dynamically from the server's tools).
    Returns "" if no client, so the base prompt is unchanged.
    """
    if client is None:
        return ""

    lines = ["", "Available MCP tools (call them as Python functions):"]
    for tool in client.tools_metadata:
        params = []
        schema = getattr(tool, "inputSchema", None) or {}
        for pname, pinfo in (schema.get("properties") or {}).items():
            ptype = pinfo.get("type", "any")
            params.append(f"{pname}: {ptype}")
        sig = ", ".join(params)
        desc = (tool.description or "").strip().splitlines()
        summary = desc[0] if desc else ""
        lines.append(f"- {tool.name}({sig}) — {summary}")
    lines.append(
        "Prefer calling these tools to verify your work when relevant "
        "(e.g. run_tests to check your solution against the tests) "
        "before calling final_answer."
    )
    return "\n".join(lines)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Solve one MBPP task.")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER,
                        help=f"Provider name (default: {DEFAULT_PROVIDER}).")
    parser.add_argument("--mcp-stdio", default=None,
                        help="Command to launch an MCP server over stdio, "
                             "e.g. 'serveur/mcp_tools_mbpp.py'.")
    parser.add_argument("--mcp-server", default=None,
                        help="URL of an MCP server over HTTP.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # The agent requires an MCP server: the sandbox exposes its tools
    # (subject V.2). One of the two transports must be provided.
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
    task_id = str(task["task_id"])

    llm = LLMClient(
        api_keys=api_keys,
        model=args.model_name,
        provider_url=provider_url,
    )

    mcp_client = connect_mcp(args.mcp_stdio, args.mcp_server)
    Console(verbose=args.verbose).mcp_connected(
        mcp_client.get_available_tools_names() if mcp_client else []
    )
    system_prompt = MBPP_SYSTEM_PROMPT + build_tools_manual(mcp_client)
    sandbox = Sandbox(
        image=MBPP_DOCKER_IMAGE,
        config=SandboxConfig(),
        mcp_client=mcp_client,
    )

    orchestrator = MBPPOrchestrator(
        sandbox=sandbox,
        call_llm=llm.call,
        system_prompt=system_prompt,
        task_id=task_id,
        model_name=args.model_name,
        api_url=provider_url,
        verbose=args.verbose,
    )

    task_message = build_mbpp_task_message(
        task_definition=task["task_definition"],
        function_definition=task["function_definition"],
        test_list=get_tests(task),
    )

    try:
        solution = orchestrator.run(task_message)
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
