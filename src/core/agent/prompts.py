"""System prompts and the per-task messages fed to the model, plus the
tool manual built from whatever MCP server is connected.
"""
from core.models import MBPPTaskInput, SWEBenchTaskInput

MBPP_SYSTEM_PROMPT = """\
You are an autonomous coding agent solving a Python task.

You work in a loop:
  Thought      - briefly reason about what to do
  Code         - write Python in a ```python ... ``` block, then <end_code>
  Observation  - you receive the output of your code

Your sandbox is persistent: variables and functions stay defined across steps.
Use it to test your solution before submitting.

To submit, call:
    final_answer(your_solution_code)
with the complete function definition as a string. The task then ends.

Rules:
- Be concise. Do NOT write long explanations. Go straight to the code.
- Every code block must end with <end_code> on its own line.
- Test your function against the given tests, then submit it.
- Submit only the function (and needed imports) via final_answer, not
  the tests.

Example
-------
Task: Write a function to add two numbers.
Signature: def add(a, b):
Tests: assert add(2, 3) == 5

Thought: Write and test it.
```python
def add(a, b):
    return a + b
assert add(2, 3) == 5
print("ok")
```
<end_code>
Observation: ok

Thought: Works. Submit.
```python
final_answer("def add(a, b):\\n    return a + b")
```
<end_code>
"""

SWEBENCH_SYSTEM_PROMPT = """\
You are an autonomous bug-fixing agent solving a SWE-bench task.

You work in a loop:
  Thought      - briefly reason about the next action
  Code         - write Python in a ```python ... ``` block, then <end_code>
  Observation  - you receive the result of your code execution

Your sandbox is persistent: variables and functions stay defined across
steps. The repository lives at /testbed inside a separate container: the
MCP tools are the ONLY way to read or edit it - plain open()/imports in
your sandbox code cannot reach it.

To submit your fix, call:
    final_answer(get_patch())

Rules:
- Be concise. Do NOT write long explanations. Go straight to the code.
- Every code block must end with <end_code> on its own line.
- Use the MCP tools to explore the repository and verify your patch. Their
  names, parameters and usage notes are listed in the tool manual below.
- You have NO native function/tool-calling. The only way to use a tool is to
  write it as Python inside the ```python block (e.g. print(read_file(...)));
  any tool_call you emit is ignored and wastes the turn.
- Call run_tests() (no arguments) to run the evaluation and read which
  tests pass or fail.
- Only call final_answer after your patch is complete and run_tests shows
  the tests pass.
- Do not fabricate shell output or test results.

Example
-------
Task: fix a bug in a repository

Thought: Inspect the file and run the test.
```python
print(read_file(filepath="/testbed/src/module.py", start_line=1,
                end_line=120))
```
<end_code>
Observation: ...

Thought: Apply a small patch and re-run the tests.
```python
old = "def foo():\\n    return 1\\n"
new = "def foo():\\n    return 2\\n"
print(edit_file(filepath="/testbed/src/module.py", old_str=old,
                new_str=new))
print(run_tests())
```
<end_code>
Observation: ...

Thought: Finalize and submit the patch.
```python
final_answer(get_patch())
```
<end_code>
"""


def build_mbpp_task_message(task: MBPPTaskInput) -> str:
    tests = "\n".join(task.test_list) or "(no public tests provided)"
    return (
        f"Task: {task.task_definition}\n"
        f"Signature: {task.function_definition}\n"
        f"Tests:\n{tests}\n\n"
        "Solve this task. Test your solution, then submit it with "
        "final_answer."
    )


def build_swebench_task_message(task: SWEBenchTaskInput) -> str:
    lines = [
        f"Task ID: {task.instance_id}",
        "Problem statement:",
        task.problem_statement or "(no problem statement provided)",
        "",
        f"Repository: {task.repo or '(unknown)'}",
        "",
        "Evaluation script:",
        task.eval_script or "(no eval script provided)",
        "",
    ]
    if task.hints_text.strip():
        lines += ["Hints:", task.hints_text.strip(), ""]
    lines.append(
        "Fix the bug by editing the repository files, then submit the diff "
        "with final_answer(get_patch()).")
    return "\n".join(lines)


def build_tools_manual(client) -> str:
    """List the connected server's tools - name, params and their full
    description - so the model knows what it can call and how. The usage
    notes come from each tool's own doc, so this stays agnostic and rebuilds
    itself for any server."""
    if client is None:
        return ""

    lines = ["", "Available MCP tools (call them as Python functions):"]
    for tool in client.tools_metadata:
        schema = getattr(tool, "inputSchema", None) or {}
        params = ", ".join(
            f"{name}: {info.get('type', 'any')}"
            for name, info in (schema.get("properties") or {}).items())
        desc = " ".join(ln.strip()
                        for ln in (tool.description or "").splitlines()
                        if ln.strip())
        lines.append(f"- {tool.name}({params}) - {desc}")

    resources = getattr(client, "resources_metadata", [])
    if resources:
        lines.append("")
        lines.append("MCP resources exposed by the server (read-only data):")
        for r in resources:
            uri = str(getattr(r, "uri", "") or "")
            desc = " ".join((getattr(r, "description", "") or "").split())
            lines.append(f"- {getattr(r, 'name', '') or uri} ({uri}) - {desc}")

    prompts = getattr(client, "prompts_metadata", [])
    if prompts:
        lines.append("")
        lines.append("MCP prompts exposed by the server:")
        for p in prompts:
            desc = " ".join((getattr(p, "description", "") or "").split())
            lines.append(f"- {getattr(p, 'name', '')} - {desc}")

    lines.append(
        "final_answer(answer) is always available (the sandbox provides it, "
        "not the MCP server): call it to submit and end the task.")
    return "\n".join(lines)
