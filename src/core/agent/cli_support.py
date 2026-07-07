"""Shared machinery for the two agent CLIs: task/keys loading, MCP wiring,
and the run flow they both follow.
"""
import json
import os
import sys

from core.sandbox import Sandbox
from core.models import SandboxConfig
from core.mcp import MCPClientBridge
from core.llm import (
    LLMClient, InvalidModelError, AllKeysExhausted,
    Provider, resolve, resolve_model, candidate_env_keys, DEFAULT_PROVIDER)
from core.agent.console import Console
from core.agent.prompts import build_tools_manual

SANDBOX_IMAGE = "python:3.11-slim"


def load_task(path: str) -> dict:
    with open(path, encoding="utf-8") as fd:
        return json.load(fd)


def load_api_keys(provider: Provider) -> tuple[list[str], str | None]:
    """Find API keys in the environment. A variable can hold several keys,
    comma-separated, which the client rotates through."""
    for name in candidate_env_keys(provider):
        raw = os.environ.get(name, "")
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if keys:
            return keys, name
    return [], None


def connect_mcp(default_tools: str, mcp_stdio: str | None,
                mcp_server: str | None) -> MCPClientBridge:
    """Connect to an MCP server: an explicit HTTP URL, an explicit stdio
    command, or our own tool server by default."""
    client = MCPClientBridge()
    if mcp_server:
        client.connect_http(mcp_server)
    elif mcp_stdio:
        client.connect_stdio(mcp_stdio)
    else:
        client.connect_stdio(["python", default_tools])
    return client


def add_common_args(parser) -> None:
    """The CLI flags both agents share."""
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", default=None,
                        help="Model id (else MODEL_NAME env, else default).")
    parser.add_argument("--provider-url", default=None,
                        help="API base URL (else PROVIDER_URL env, else "
                             "the named provider).")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER,
                        help="Known provider name; ignored with "
                             "--provider-url.")
    parser.add_argument("--mcp-stdio", default=None,
                        help="MCP server command over stdio (default: our "
                             "own tool server).")
    parser.add_argument("--mcp-server", default=None,
                        help="MCP server URL over HTTP.")
    parser.add_argument("--sandbox-config", default=None)
    parser.add_argument("--verbose", action="store_true")


def run_agent(args, *, orchestrator_cls, system_prompt, task_message,
              task_id, default_tools, max_tokens, temperature=0.0) -> None:
    """The flow both agents follow: resolve the model and keys, connect the
    MCP server, run the loop, and write the solution to --output."""
    model_name = resolve_model(args.model_name)
    try:
        provider = resolve(args.provider, args.provider_url)
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    api_keys, _ = load_api_keys(provider)
    if not api_keys:
        tried = ", ".join(candidate_env_keys(provider))
        sys.exit(f"ERROR: no API keys found. Set one of [{tried}] in .env.")

    llm = LLMClient(api_keys, model_name, provider.url,
                    temperature=temperature, max_tokens=max_tokens)

    console = Console(verbose=args.verbose)
    try:
        mcp = connect_mcp(default_tools, args.mcp_stdio, args.mcp_server)
    except Exception as e:
        sys.exit(f"ERROR: failed to connect MCP server: {e}")
    console.mcp_connected(mcp.get_available_tools_names())

    config = (SandboxConfig.from_json(args.sandbox_config)
              if args.sandbox_config else SandboxConfig())
    sandbox = Sandbox(SANDBOX_IMAGE, config, mcp)
    orchestrator = orchestrator_cls(
        sandbox=sandbox,
        call_llm=llm.call,
        system_prompt=system_prompt + build_tools_manual(mcp),
        task_id=task_id,
        model_name=model_name,
        api_url=provider.url,
        verbose=args.verbose,
    )

    try:
        solution = orchestrator.run(task_message)
    except (InvalidModelError, AllKeysExhausted) as e:
        sys.exit(f"ERROR: {e}")
    finally:
        mcp.disconnect()

    with open(args.output, "w", encoding="utf-8") as fd:
        fd.write(solution.model_dump_json(indent=2))
    print(f"Solved: {solution.success} | iterations: {solution.iterations} "
          f"| output written to {args.output}")
