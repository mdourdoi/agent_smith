# Moulinette

Evaluation tools for Project 3: Agent Smith.

## Installation

```bash
cd moulinette
uv sync
```

---

## Core Usage

### Dump a task

```bash
# Random MBPP task
uv run moulinette_eval dump mbpp --output task.json

# Specific MBPP task
uv run moulinette_eval dump mbpp --task-id 42 --output task.json

# Random SWE-bench task
uv run moulinette_eval dump swebench --output task.json

# Specific SWE-bench task
uv run moulinette_eval dump swebench --task-id sympy__sympy-23534 --output task.json
```

### Validate a solution

```bash
# Correctness + metrics
uv run moulinette_eval validate mbpp task.json solution.json
uv run moulinette_eval validate swebench task.json solution.json

# Skip metrics check
uv run moulinette_eval validate mbpp task.json solution.json --skip-metrics

# Metrics only
uv run moulinette_eval validate_metrics mbpp solution.json
uv run moulinette_eval validate_metrics swebench solution.json
```

### Display a solution

```bash
uv run moulinette_eval display solution.json
uv run moulinette_eval display solution.json --full
```

### Evaluation flow

```
MOULINETTE                      STUDENT
    │                              │
    │── dump task.json ───────────▶│
    │                              │── solve task
    │                              │── (pull docker for SWE-bench)
    │                              │── (cleanup container)
    │◀── solution.json ────────────│
    │── validate ──────────────────│
```

The moulinette only dumps tasks and validates solutions. It does NOT run student code.

---

## Corrector Guide

### Select exam tasks

```bash
uv run moulinette_eval select swebench --count 3
uv run moulinette_eval select swebench --count 3 --seed 42 --output selection.json
```

### Run exam scripts

```bash
# From src_project_3/
./exams/exam_mbpp.sh --student-path ./student --moulinette-path ./moulinette --env-file .env
./exams/exam_swebench.sh --student-path ./student --moulinette-path ./moulinette --env-file .env
./exams/exam_sandbox.sh --student-path ./student --moulinette-path ./moulinette --env-file .env
```

Results are saved to `evaluations/(mbpp|swebench|sandbox)/$DATETIME/`.

---

## Advanced Topics

### Exploring tasks (Fire CLIs)

Each submodule has a Fire CLI for direct access:

```bash
# MBPP
uv run moulinette_mbpp list_tasks
uv run moulinette_mbpp list_tasks --split test
uv run moulinette_mbpp get_task 42
uv run moulinette_mbpp evaluate_task_solution 42 "def similar_elements(a, b): return tuple(set(a) & set(b))"

# SWE-bench
uv run moulinette_swebench list_instances
uv run moulinette_swebench list_instances --repo_pattern "sympy"
uv run moulinette_swebench get_instance_info sympy__sympy-23534
uv run moulinette_swebench eval sympy__sympy-23534 --patch patch.diff
```

### Accessing gold patches

Gold patches are available in the SWE-bench dataset but hidden from students. Use the `swebench` Python library directly to access them.

### Adjusting difficulty

By default, the moulinette selects instances with difficulty `"<15 min fix"`. Modify `moulinette/swebench/interact.py` to change the default:

```python
def list_instances(
    self,
    difficulty: Union[str, List[str], Difficulty, List[Difficulty]] = Difficulty.LESS_THAN_15_MIN,
    sort_by_patch_length: bool = False,
    limit: Optional[int] = 7,
) -> List[str]:
```

Available difficulties: `LESS_THAN_15_MIN`, `MIN_15_TO_1_HOUR`, `HOURS_1_TO_4`, `MORE_THAN_4_HOURS`.

### Task selection rationale

See `experiments/task_selection/` for benchmark scripts, shortlist generation, and verification tooling.

---

## Metrics & Pass Criteria

### MBPP limits

| Metric | Limit |
|--------|-------|
| Max iterations | 10 |
| Max input tokens | 4,000 |
| Max output tokens | 1,000 |
| Timeout | 60 seconds |

### SWE-bench limits

| Metric | Limit |
|--------|-------|
| Max iterations | 30 |
| Max input tokens | 300,000 |
| Max output tokens | 10,000 |
| Timeout | 900 seconds |

### Changing limits

Edit `moulinette/models.py`:

```python
@classmethod
def mbpp_defaults(cls) -> "MetricsLimits":
    return cls(
        max_iterations=10,
        max_input_tokens=4_000,
        max_output_tokens=1_000,
        max_time_seconds=60.0,
    )
```

### Pass criteria

| Benchmark | Tasks | Pass Threshold |
|-----------|-------|----------------|
| MBPP | 5 random | 4 out of 5 |
| SWE-bench | 3 random | 2 out of 3 |
