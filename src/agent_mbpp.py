"""CLI: solve one MBPP task and write the solution to a JSON file."""
import os
import argparse
import sys

from dotenv import load_dotenv

from core.models import MBPPTaskInput
from core.agent import (
    MBPPOrchestrator, MBPP_SYSTEM_PROMPT, build_mbpp_task_message,
    load_task, add_common_args, run_agent)

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_TOOLS = os.path.join(REPO_ROOT, "mcp_tools_mbpp.py")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Solve one MBPP task.")
    add_common_args(parser)
    args = parser.parse_args()

    task = MBPPTaskInput.model_validate(load_task(args.task_file))
    run_agent(
        args,
        orchestrator_cls=MBPPOrchestrator,
        system_prompt=MBPP_SYSTEM_PROMPT,
        task_message=build_mbpp_task_message(task),
        task_id=str(task.task_id),
        default_tools=DEFAULT_TOOLS,
        max_tokens=512,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as e:
        print(f"Interrupted: {e}" if str(e) else "Interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
