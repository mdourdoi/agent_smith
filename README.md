*This project has been created as part of the 42 curriculum by mdourdoi.*

# Agent Smith

Autonomous reasoning, code generation, and execution.

## Description

Agent Smith is an **agentic framework** that autonomously solves coding
challenges. An LLM reasons about a task, writes **executable Python**, runs it
in a **sandboxed environment**, observes the result, and iterates until the
task is solved - the `Thought → Code → Observation` loop.

Two benchmarks are supported:

- **MBPP** - small, self-contained Python problems. The agent writes a
  function and submits it.
- **SWE-bench** - real bug fixes in real repositories running inside Docker.
  The agent explores the codebase through tools, edits files, runs the test
  suite, and submits a `git diff` patch.

Instead of JSON tool-calling, tools are exposed as **Python functions** the
model calls directly from code (code-based tool calling), which allows
persistent variables, loops, and multi-step reasoning between steps.

## Instructions

Requirements: **Python 3.10+**, **uv**, and **Docker** (the sandbox and the
SWE-bench repositories run in containers).

```bash
uv sync
```

API keys are read from the environment (a `.env` file is loaded
automatically). The `.env` holds **only API keys** - nothing else. Multiple
keys per provider are supported, comma-separated, and rotated on rate limits:

```bash
# .env  - API keys only
OPENROUTER_API_KEY=key1,key2,key3
```

The model and provider come from the CLI: `--model-name` is optional (falls
back to the built-in default in [providers.py](src/core/llm/providers.py)), and
`--provider-url` is optional too (falls back to `--provider`, default
OpenRouter).

### MBPP

```bash
# 1. Dump a task (from the moulinette)
cd moulinette && uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json && cd ..

# 2. Run the agent
uv run python -m agent_mbpp \
    --task-file cache/mbpp_task.json \
    --output cache/mbpp_solution.json \
    --model-name "qwen/qwen3-235b-a22b-2507" \
    --provider-url "https://openrouter.ai/api/v1"

# 3. Validate
cd moulinette && uv run moulinette_eval validate mbpp \
    ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

### SWE-bench

```bash
cd moulinette && uv run moulinette_eval dump swebench --output ../cache/swebench_task.json && cd ..

uv run python -m agent_swebench \
    --task-file cache/swebench_task.json \
    --output cache/swebench_solution.json \
    --model-name "qwen/qwen3-235b-a22b-2507" \
    --provider-url "https://openrouter.ai/api/v1"

cd moulinette && uv run moulinette_eval validate swebench \
    ../cache/swebench_task.json ../cache/swebench_solution.json
```

By default each agent launches its own mandatory MCP tool server
(`mcp_tools_mbpp.py` / `mcp_tools_swebench.py`). Override with
`--mcp-stdio "<command>"` or `--mcp-server <URL>`.

### Sandbox CLI

```bash
uv run sandbox                                   # interactive REPL
uv run sandbox sandbox.example.json              # custom configuration
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox.example.json
uv run sandbox --mcp-server <URL>
echo "print(40 + 2)" | uv run sandbox            # piped program
```

## CLI reference

Everything you can launch, every flag, its allowed values, whether it is
required, and what happens when it is omitted. Configuration comes from CLI
flags with sensible built-in defaults; **only API keys come from the
environment**.

### What each command is for

- **`agent_mbpp` / `agent_swebench`** - the two **agents**, the top-level
  programs. Each solves **one task** of its benchmark from start to finish
  (run the Thought → Code → Observation loop against an LLM) and writes the
  result - a function for MBPP, a git patch for SWE-bench - plus full metrics
  to `solution.json`. This is what the exam runs, once per task.
- **`sandbox`** - a standalone tool to **run Python inside the isolated
  sandbox, with no LLM**. It is how you exercise the sandbox directly: check
  the security policies (blocked imports/builtins/paths, no network, memory
  and time limits), call tools through an MCP server, or just experiment.
  This is what the sandbox exam drives.
- **`mcp_tools_mbpp.py` / `mcp_tools_swebench.py`** - the **MCP tool servers**
  that expose the tools (MBPP: `run_tests`; SWE-bench: the 9 mandatory tools
  that act on the task's Docker container). The agents start them
  automatically on stdio; you only launch one by hand to test a tool on its
  own. They are sub-components, not something you normally run directly.

### `agent_mbpp` and `agent_swebench`

Launch with `uv run python -m agent_mbpp …` / `uv run python -m agent_swebench …`
(or the console scripts `uv run agent_mbpp …` / `uv run agent_swebench …`).
Both take the exact same flags.

| Flag | Required | Values | If omitted |
|------|----------|--------|------------|
| `--task-file PATH` | **yes** | path to the dumped task JSON | error, the agent stops |
| `--output PATH` | **yes** | path where `solution.json` is written | error, the agent stops |
| `--model-name STR` | no | any model id valid for the provider (e.g. `meta-llama/llama-3.3-70b-instruct`) | the built-in default in [providers.py](src/core/llm/providers.py) |
| `--provider-url URL` | no | base URL of a **known** provider (must match one in the list below) | the URL of `--provider` (default OpenRouter) |
| `--provider NAME` | no | `openrouter`, `groq`, `mistral`, `cerebras`, `together` | `openrouter`. Ignored when `--provider-url` is given |
| `--mcp-stdio "CMD"` | no | a command that starts an MCP server on stdio (e.g. `"python mcp_tools_mbpp.py"`) | our own tool server on stdio (`mcp_tools_mbpp.py` / `mcp_tools_swebench.py`) |
| `--mcp-server URL` | no | URL of an MCP server (streamable HTTP; SSE if the URL ends with `/sse`) | not used. **Takes priority over `--mcp-stdio`** when both are given |
| `--sandbox-config PATH` | no | path to a JSON [SandboxConfig](src/core/models.py) | built-in defaults: stdlib imports allowlist, dirs `/testbed` + `/tmp/agent`, 30 s, 512 MB |
| `--verbose` | no | flag, no value | off - only the final one-line summary is printed |

**API keys are not flags.** They are read from the environment (see below) and
are **required** - the run errors out if no key is found for the provider.

Only the hardcoded providers listed above are handled: an unknown `--provider`
or a `--provider-url` that matches none of them stops with a clear message
listing the known providers (add yours to `PROVIDERS` in
[providers.py](src/core/llm/providers.py)). Redundant flags never crash - when two
overlapping flags are given, one wins deterministically: `--provider-url` over
`--provider`, and `--mcp-server` over `--mcp-stdio`.

Difference between the two agents: `agent_swebench` also uses `temperature=0.5`
and a larger per-reply cap, and it points the tool server at the task's Docker
image. These are code constants, not flags.

Example:
```bash
uv run python -m agent_mbpp \
    --task-file cache/mbpp_task.json --output cache/mbpp_solution.json \
    --model-name "meta-llama/llama-3.3-70b-instruct" \
    --provider-url "https://openrouter.ai/api/v1"

uv run python -m agent_swebench \
    --task-file cache/swebench_task.json --output cache/swebench_solution.json \
    --model-name "meta-llama/llama-3.3-70b-instruct" \
    --provider-url "https://openrouter.ai/api/v1"
```

### `sandbox`

Launch with `uv run sandbox [config] [flags]`.

| Argument / flag | Required | Values | If omitted |
|-----------------|----------|--------|------------|
| `config` (positional) | no | path to a JSON [SandboxConfig](src/core/models.py) | built-in defaults |
| `--mcp-stdio "CMD"` | no | MCP server command on stdio | **no MCP server** - only `final_answer` is available, no tools |
| `--mcp-server URL` | no | MCP server URL (HTTP) | no MCP server. Takes priority over `--mcp-stdio` |
| `--code "CODE"` | no | Python code to run | read from `--file`, else from stdin |
| `--file PATH` | no | path to a Python file to run | read from `--code`, else from stdin |

The sandbox always runs in `python:3.11-slim` (a code constant, not a flag).

**Where the code comes from**, in priority order: `--file` → `--code` → **stdin**
(piped input runs as a single program; an interactive terminal opens a small
REPL). With no `config` and no MCP flag, `uv run sandbox` alone is a bare
interactive sandbox with default limits and no tools.

Example:
```bash
uv run sandbox                                        # interactive REPL
echo "print(40 + 2)" | uv run sandbox                 # run a piped program
uv run sandbox sandbox.example.json                   # with a custom config
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" # with tools connected
```

### MCP tool servers (usually started for you)

`mcp_tools_mbpp.py` and `mcp_tools_swebench.py` normally run **on stdio, started
automatically by the agent**; you rarely launch them by hand. They take **no
flags**. The SWE-bench server is configured through environment variables (the
agent sets `SWEBENCH_TASK_FILE` for you):

| Variable | Required | Meaning | If omitted |
|----------|----------|---------|------------|
| `SWEBENCH_TASK_FILE` | one of the two | path to a dumped task.json (Docker image + eval script) | - |
| `SWEBENCH_IMAGE` | one of the two | Docker image to run | falls back to the image in the task file |
| `SWEBENCH_CONTAINER` | no | name/id of an already-running container to reuse | a fresh container is created and removed at exit |
| `SWEBENCH_EVAL_TIMEOUT` | no | seconds allowed for `run_tests` | `400` |

Example (rarely needed - the agent starts these for you):
```bash
uv run python mcp_tools_mbpp.py            # MBPP server, waits on stdio
SWEBENCH_TASK_FILE=cache/swebench_task.json uv run python mcp_tools_swebench.py
```

### Environment variables

The `.env` holds **only API keys** - the model and provider are chosen on the
CLI, not through the environment.

| Variable | Purpose | Notes |
|----------|---------|-------|
| `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `TOGETHER_API_KEY` | provider API keys | comma-separated to give several keys (rotated on rate limits) |
| `LLM_API_KEY`, `API_KEY` | generic key fallback | tried after the provider-specific names above |

## System architecture

```
             ┌──────────────────────── agent process (host) ──────────────────────┐
             │                                                                    │
   task ──►  │  Orchestrator ──► LLM API (multi-provider, key rotation)           │
             │      │  ▲            (Thought → Code → Observation loop)           │
             │      ▼  │ observation                                              │
             │  CodeExtractor  (python / XML / hermes / ReAct → Python)           │
             │      │                                                             │
             │      ▼ code                                                        │
             │   Sandbox ──stdin/stdout──►  sandbox container (python:3.11-slim)  │
             │      │                          runs LLM code under security       │
             │      │  tool_call                policies + final_answer()         │
             │      ▼                                                             │
             │   MCP client ──stdio/HTTP──►  MCP tool server (mcp_tools_*.py)     │
             └────────────────────────────────────────────│───────────────────────┘
                                                          │ docker exec (SWE-bench)
                                                          ▼
                                            SWE-bench container (/testbed repo)
```

- **Orchestrator** ([core/agent/orchestrator.py](src/core/agent/orchestrator.py))
  drives the loop, enforces the iteration/token/time limits, and records
  per-step metrics.
- **CodeExtractor** ([core/agent/code_extractor.py](src/core/agent/code_extractor.py))
  turns any supported model output format into Python before execution, so the
  sandbox stays format-agnostic.
- **Sandbox** ([core/sandbox/sandbox.py](src/core/sandbox/sandbox.py) +
  [core/sandbox/sandbox_server.py](src/core/sandbox/sandbox_server.py)) is the
  execution boundary.
- **MCP client / server** ([core/mcp/mcp_client.py](src/core/mcp/mcp_client.py),
  [mcp_tools_mbpp.py](mcp_tools_mbpp.py),
  [mcp_tools_swebench.py](mcp_tools_swebench.py)) expose the tools.

## Agent loop

Each iteration:

1. Call the LLM with the running conversation (system prompt + history).
2. Extract the code block from the response (a `stop` sequence, `<end_code>`,
   keeps the model from hallucinating the observation).
3. Execute the code in the sandbox.
4. Feed the observation back. The sandbox always gives **explicit feedback**:
   no code found, a format was auto-converted, output was truncated, a timeout
   hit, or an error was raised - the model is never left guessing.
5. Stop when the code calls `final_answer(...)`, or when a limit is reached.

Limits are per-benchmark class attributes on the orchestrator subclasses
([orchestrator.py](src/core/agent/orchestrator.py)) and token counts are cumulative
across the whole task.

## Sandbox design

The sandbox runs untrusted, LLM-generated Python **in a separate Docker
container**, so a runaway or malicious program cannot touch the host. The same
model is used for both benchmarks - only the MCP tools differ.

Two independent security domains (as the subject frames it):

- **The sandbox** restricts what the LLM *code* can do. Enforced in
  [sandbox_server.py](src/core/sandbox/sandbox_server.py) with the standard library
  only (no `RestrictedPython`):
  - **Import allowlist** - a custom `__import__` blocks anything outside
    `authorized_imports`.
  - **Restricted builtins** - `eval`, `exec`, `compile`, `input`, ... are
    removed from the execution namespace.
  - **Path restriction** - `open` is limited to `allowed_directories`.
  - **No network / memory limit / timeout** - enforced by Docker
    (`--network none`, `--memory`) and by a host-side execution timeout.
  - `KeyboardInterrupt` / `SystemExit` are propagated to the agent loop for a
    clean shutdown instead of being swallowed.
- **MCP tools** act *outside* the sandbox (reading files in Docker, running
  tests), so their actions are not subject to the sandbox policies or timeout.

Limits are configurable via a Pydantic model and JSON files
([SandboxConfig in models.py](src/core/models.py),
[sandbox.example.json](sandbox.example.json)). `final_answer()` is always
present in the namespace - it is provided by the sandbox, not by any MCP
server.

## Tool implementation

Tools are exposed by an **MCP server** and discovered dynamically: the sandbox
manual fed to the LLM is generated from each server's tool schemas, so a
different server automatically changes the advertised tools. Both **stdio** and
**streamable HTTP** transports are supported.

Mandatory SWE-bench tools ([mcp_tools_swebench.py](mcp_tools_swebench.py)):
`read_file`, `edit_file`, `list_files`, `search_code`,
`search_function_or_class_definition_in_code`, `find_references`, `run_tests`,
`get_patch`, `run_command`.

**SWE-bench bridge (approach b).** The repository lives at `/testbed` inside
the task's own Docker image. The tool server owns that container's lifecycle
(configured through `SWEBENCH_TASK_FILE`, created lazily, removed at exit) and
every tool runs via `docker exec` into it. The sandbox container never sees
`/testbed`, so all repository access necessarily goes through the tools -
exactly the boundary the subject describes.

For MBPP, `run_tests(code, tests)` runs the candidate against the public tests
in an isolated subprocess.

## Benchmark results

The model comparison (≥5 models over ≥3 SWE-bench tasks), provider reliability,
intermediary exploration metrics, and an ablation study are in
[BENCHMARK_REPORT.md](BENCHMARK_REPORT.md), backed by the `solution.json` files
that produced them.

## Resources

- [Model Context Protocol](https://modelcontextprotocol.io/) - tool server /
  client specification.
- [MBPP dataset](https://github.com/google-research/google-research/tree/master/mbpp).
- [SWE-bench](https://www.swebench.org/) and SWE-bench Verified.
- The ReAct paper (*Reasoning + Acting*) and open-source "code agent" designs
  (e.g. the CodeAgent pattern) inspired the `Thought → Code → Observation`
  loop.

**Use of AI.** AI assistance was used to draft boilerplate (argument parsing,
docstrings), to review the sandbox security policies against the subject's
requirements, and to help structure this documentation. Every architectural
decision - the two-container SWE-bench bridge, the security model, the MCP
wiring - was made and reviewed by the author, and the agent loop is our own
implementation (no agent-orchestration library is used).
