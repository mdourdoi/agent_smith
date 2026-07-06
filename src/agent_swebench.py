"""CLI: solve one SWE-bench task and write the git patch to a JSON file."""
import os
import argparse
import sys

from dotenv import load_dotenv

from core.models import SWEBenchTaskInput
from core.agent import (
    SWEBenchOrchestrator, SWEBENCH_SYSTEM_PROMPT, build_swebench_task_message,
    load_task, add_common_args, run_agent)

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_TOOLS = os.path.join(REPO_ROOT, "mcp_tools_swebench.py")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Solve one SWE-bench task.")
    add_common_args(parser)
    args = parser.parse_args()

    task = SWEBenchTaskInput.model_validate(load_task(args.task_file))
    os.environ["SWEBENCH_TASK_FILE"] = os.path.abspath(args.task_file)

    run_agent(
        args,
        orchestrator_cls=SWEBenchOrchestrator,
        system_prompt=SWEBENCH_SYSTEM_PROMPT,
        task_message=build_swebench_task_message(task),
        task_id=task.instance_id,
        default_tools=DEFAULT_TOOLS,
        max_tokens=3000,
        temperature=0.5,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
