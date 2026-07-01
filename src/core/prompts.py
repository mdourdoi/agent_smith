"""
System prompts fed to the LLM, per benchmark.
"""

MBPP_SYSTEM_PROMPT = """\
You are an autonomous coding agent solving a Python task.

You work in a loop:
  Thought      - briefly reason about what to do
  Code         - write Python in a ```python ... ``` block ending with <end_code>
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
- Submit only the function (and needed imports) via final_answer, not the tests.

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


def build_mbpp_task_message(
    task_definition: str,
    function_definition: str,
    test_list: list[str],
) -> str:
    """Build the user message describing the concrete MBPP task."""
    tests = "\n".join(test_list) if test_list else "(no public tests provided)"
    return (
        f"Task: {task_definition}\n"
        f"Signature: {function_definition}\n"
        f"Tests:\n{tests}\n\n"
        "Solve this task. Test your solution, then submit it with "
        "final_answer."
    )