"""Standalone SWE-bench patch grader.

Grades a produced patch the same way the moulinette does -- applies it in the
task's Docker image, runs the eval script, and decides FULL resolution with
swebench's own get_logs_eval / get_eval_tests_report / get_resolution_status.
It is the grader used to produce every *.val.json here.

Run with the moulinette venv (it has the swebench library + docker):
    <moulinette>/.venv/bin/python benchmarks/validate_swe.py \
        benchmarks/tasks/<task>.json benchmarks/<model>/<task>.json
Prints one JSON line and exits 0 iff the patch resolves the task.
"""
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from swebench.harness.utils import load_swebench_dataset
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.constants import (
    START_TEST_OUTPUT, END_TEST_OUTPUT, FAIL_TO_PASS, PASS_TO_PASS,
    KEY_INSTANCE_ID, FAIL_ONLY_REPOS, EvalType, ResolvedStatus,
)
from swebench.harness.grading import (
    get_logs_eval, get_eval_tests_report, get_resolution_status,
)

WORKDIR = "/testbed"
DATASET = "SWE-bench/SWE-bench_Verified"
SPLIT = "test"
EVAL_TIMEOUT = 1800


def dexec(name, args, input_bytes=None, workdir=None, timeout=None):
    cmd = ["docker", "exec"]
    if input_bytes is not None:
        cmd.append("-i")
    if workdir:
        cmd += ["-w", workdir]
    cmd.append(name)
    cmd += args
    return subprocess.run(cmd, input=input_bytes, capture_output=True,
                          timeout=timeout)


def main():
    task = json.load(open(sys.argv[1], encoding="utf-8"))
    sol = json.load(open(sys.argv[2], encoding="utf-8"))
    instance_id = task["instance_id"]
    image = task["docker_image"]
    patch = sol.get("solution", "") or ""

    ds = load_swebench_dataset(DATASET, SPLIT, [instance_id])
    test_spec = make_test_spec(ds[0])
    eval_script = test_spec.eval_script

    name = "agent_smith_val_" + uuid.uuid4().hex[:12]
    result = {"instance_id": instance_id, "resolved": False, "status": None,
              "note": ""}
    try:
        subprocess.run(["docker", "run", "-d", "--name", name, image,
                        "tail", "-f", "/dev/null"], check=True,
                       capture_output=True)
        dexec(name, ["git", "config", "--global", "--add",
                     "safe.directory", WORKDIR])

        applied = False
        if patch.strip():
            dexec(name, ["sh", "-c", "cat > /tmp/patch.diff"],
                  input_bytes=patch.encode("utf-8"))
            for cmd in ("git apply --verbose /tmp/patch.diff",
                        "git apply --verbose --reject /tmp/patch.diff",
                        "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff"):
                r = dexec(name, ["sh", "-c", cmd], workdir=WORKDIR)
                if r.returncode == 0:
                    applied = True
                    break
            if not applied:
                result["note"] = "patch did not apply"

        dexec(name, ["sh", "-c", "cat > /eval.sh"],
              input_bytes=eval_script.encode("utf-8"))
        r = dexec(name, ["bash", "/eval.sh"], timeout=EVAL_TIMEOUT)
        out = (r.stdout or b"").decode("utf-8", "replace")
        err = (r.stderr or b"").decode("utf-8", "replace")
        log = out + "\n" + err

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as fd:
            fd.write(log)
            log_path = fd.name

        status_map, found = get_logs_eval(test_spec, log_path)
        Path(log_path).unlink(missing_ok=True)
        if not found or START_TEST_OUTPUT not in log \
                or END_TEST_OUTPUT not in log:
            result["note"] = (result["note"] or "test output not parseable")
            print(json.dumps(result))
            return 1

        eval_ref = {
            KEY_INSTANCE_ID: test_spec.instance_id,
            FAIL_TO_PASS: test_spec.FAIL_TO_PASS,
            PASS_TO_PASS: test_spec.PASS_TO_PASS,
        }
        eval_type = (EvalType.FAIL_ONLY if test_spec.repo in FAIL_ONLY_REPOS
                     else EvalType.PASS_AND_FAIL)
        report = get_eval_tests_report(status_map, eval_ref,
                                       eval_type=eval_type)
        status = get_resolution_status(report)
        result["status"] = status
        result["resolved"] = (status == ResolvedStatus.FULL.value)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)

    print(json.dumps(result))
    return 0 if result["resolved"] else 1


if __name__ == "__main__":
    sys.exit(main())
