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


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Solve one MBPP task.")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER,
                        help=f"Provider name (default: {DEFAULT_PROVIDER}).")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # Resolve provider -> url + env var holding the keys.
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
    sandbox = Sandbox(image=MBPP_DOCKER_IMAGE, config=SandboxConfig())

    orchestrator = MBPPOrchestrator(
        sandbox=sandbox,
        call_llm=llm.call,
        system_prompt=MBPP_SYSTEM_PROMPT,
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

    with open(args.output, "w") as f:
        f.write(solution.model_dump_json(indent=2))

    print(f"Solved: {solution.success} | "
          f"iterations: {solution.iterations} | "
          f"output written to {args.output}")


if __name__ == "__main__":
    main()
