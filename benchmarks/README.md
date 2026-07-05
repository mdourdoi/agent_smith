# benchmarks/

Backing data for [`../BENCHMARK_REPORT.md`](../BENCHMARK_REPORT.md). Every
number in the report is read from the files here.

## Layout

```
tasks/<task>.json            dumped SWE-bench task (image + eval script)
<model>/<task>.json          the agent's solution.json for that (model, task)
<model>/<task>.val.json      the official resolution verdict for that patch
ablation/                    §5 tool-set ablation run
summary.json                 machine-readable roll-up of every run
run.log                      raw stdout/stderr of the whole batch (provenance)
validate_swe.py              the grader used to produce every *.val.json
```

A `<task>.val.json` with no matching `<task>.json` means the run produced no
patch at all (rate-limited, provider-rejected, or out of credit) - the
`status` field says which.

## The three tasks

`sympy__sympy-18189`, `sympy__sympy-13480`, `pydata__xarray-4629` - all from the
moulinette SWE-bench Verified `SEED_POOL` (`<15 min fix`).

## Grading (`validate_swe.py`)

Same logic as the moulinette's `validate swebench`: apply the patch in the
task's Docker image, run the eval script, and require FULL resolution via
swebench's `get_logs_eval` / `get_eval_tests_report` / `get_resolution_status`.
Run it with the moulinette venv (which has the `swebench` library):

```
<moulinette>/.venv/bin/python benchmarks/validate_swe.py \
    tasks/sympy-18189.json deepseek-chat/sympy-18189.json
# -> {"instance_id": "...", "resolved": true, "status": "RESOLVED_FULL", ...}
```
