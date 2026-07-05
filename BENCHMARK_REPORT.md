# Model Benchmark Report

Real runs produced by the agent on SWE-bench Verified. Every number below is
read from a committed `solution.json` (under `benchmarks/<model>/<task>.json`)
and every **Pass** is the official SWE-bench grade: the patch is applied in the
task's Docker image, the eval script is run, and resolution is decided by
`swebench`'s own `get_logs_eval` / `get_eval_tests_report` /
`get_resolution_status` (FULL resolution required). The per-task verdict is
stored next to each solution as `<task>.val.json`.

## 1. Setup

- **Benchmark:** SWE-bench Verified, `<15 min fix` difficulty (the moulinette
  `SEED_POOL`).
- **Tasks (3):**
  - `sympy__sympy-18189`
  - `sympy__sympy-13480`
  - `pydata__xarray-4629`
- **Models (5 distinct families, no reasoning models):** reasoning tokens count
  toward the output budget (subject VI.1), so the pool is deliberately
  non-reasoning. The free providers only cover three families (Meta Llama on
  Groq, Google Gemma on Cerebras, Mistral on Mistral); DeepSeek and Moonshot
  are reachable only through OpenRouter.

  | # | Model | Provider | Family | Cost |
  |---|-------|----------|--------|------|
  | 1 | `llama-3.3-70b-versatile` | Groq | Meta Llama | free |
  | 2 | `gemma-4-31b` | Cerebras | Google Gemma | free |
  | 3 | `devstral-medium-latest` | Mistral | Mistral | free |
  | 4 | `deepseek/deepseek-chat` | OpenRouter | DeepSeek | paid |
  | 5 | `moonshotai/kimi-k2` | OpenRouter | Moonshot | paid |

- **Limits (subject VI.1, enforced by the orchestrator):** 30 iterations,
  300k input tokens, 10k output tokens, 900 s per task.

## 2. Results table

One row per (model × task). Fields come straight from `solution.json`; **Pass**
is the independent SWE-bench grade.

| Model | Provider | Task | Pass | Iter | Input tok | Output tok | Time (s) |
|-------|----------|------|------|-----:|----------:|-----------:|---------:|
| llama-3.3-70b-versatile | Groq | sympy-18189 | ✗ (429) | — | — | — | — |
| llama-3.3-70b-versatile | Groq | sympy-13480 | ✗ (429) | — | — | — | — |
| llama-3.3-70b-versatile | Groq | xarray-4629 | ✅ | 4 | 10 195 | 434 | 34.3 |
| gemma-4-31b | Cerebras | sympy-18189 | ✅ | 15 | 88 414 | 1 860 | 156.8 |
| gemma-4-31b | Cerebras | sympy-13480 | ✅ | 9 | 26 284 | 1 333 | 121.2 |
| gemma-4-31b | Cerebras | xarray-4629 | ✅ | 11 | 52 840 | 1 672 | 152.5 |
| devstral-medium-latest | Mistral | sympy-18189 | ✗ (400) | — | — | — | — |
| devstral-medium-latest | Mistral | sympy-13480 | ✗ | 30 | 132 238 | 1 888 | 30.1 |
| devstral-medium-latest | Mistral | xarray-4629 | ✗ | 30 | 270 071 | 2 625 | 47.8 |
| deepseek/deepseek-chat | OpenRouter | sympy-18189 | ✅ | 4 | 12 709 | 290 | 15.9 |
| deepseek/deepseek-chat | OpenRouter | sympy-13480 | ✅ | 4 | 8 147 | 237 | 12.1 |
| deepseek/deepseek-chat | OpenRouter | xarray-4629 | ✅ | 8 | 25 422 | 1 539 | 45.0 |
| moonshotai/kimi-k2 | OpenRouter | sympy-18189 | ✗ | 30 | 115 833 | 1 388 | 76.9 |
| moonshotai/kimi-k2 | OpenRouter | sympy-13480 | ✅ | 13 | 51 106 | 981 | 53.0 |
| moonshotai/kimi-k2 | OpenRouter | xarray-4629 | ✗ (402) | — | — | — | — |

Codes in the Pass column mark runs that never produced a patch: `429` =
provider rate-limited the request (no solution written), `400` = the provider
rejected the conversation, `402` = the OpenRouter test credit ran out
mid-benchmark. These are provider/quota outcomes, not model failures on the
task — see §3 and §6.

### Per-model summary

| Model | Family | Provider | Solved | Avg iter | Avg input tok | Avg time (s) |
|-------|--------|----------|:------:|---------:|--------------:|-------------:|
| deepseek/deepseek-chat | DeepSeek | OpenRouter | **3/3** | 5.3 | 15 426 | 24 |
| gemma-4-31b | Google Gemma | Cerebras | **3/3** | 11.7 | 55 846 | 144 |
| moonshotai/kimi-k2 | Moonshot | OpenRouter | 1/3 | 21.5 | 83 470 | 65 |
| llama-3.3-70b-versatile | Meta Llama | Groq | 1/3 | 4.0 | 10 195 | 34 |
| devstral-medium-latest | Mistral | Mistral | 0/3 | 30.0 | 201 154 | 39 |

(Averages are over runs that produced a solution.)

## 3. Provider reliability

Aggregated over the runs above. `request_time_ms` and `retries` are recorded
per step in each `solution.json`; "retries" is the number of transient
failures (429/5xx) the client rode out with exponential backoff before a call
succeeded.

| Model / provider | Avg resp / request | Client retries | Runs completed | Notes |
|------------------|-------------------:|---------------:|:--------------:|-------|
| deepseek/deepseek-chat / OpenRouter | 3.9 s | 0 | 3/3 | most reliable API of the pool |
| gemma-4-31b / Cerebras | 12.3 s | 84 | 3/3 | free tier rate-limits hard but the backoff recovers → still 3/3 |
| moonshotai/kimi-k2 / OpenRouter | 3.2 s | 0 | 2/3 | 3rd run blocked when the OpenRouter test credit hit 402 |
| llama-3.3-70b-versatile / Groq | 8.2 s | 7 | 1/3 | free-tier tokens-per-minute too low for SWE context → 429 on 2/3 |
| devstral-medium-latest / Mistral | 1.0 s | 0 | 2/3 | fast API, but the model breaks the protocol (see §6) |

The single clearest reliability finding: **large SWE contexts (30k–270k input
tokens) do not fit Groq's free tokens-per-minute budget** — the same model that
solved the small `xarray` task was rate-limited to death on the two `sympy`
tasks. Cerebras also rate-limits (84 backoff retries) but its window resets fast
enough that every run still finished.

## 4. Intermediary metrics (2)

Measured by walking the `steps` array of each `solution.json`:

- **Exploration efficiency — first-touch step:** the first iteration whose
  sandbox code reads or edits a file that ends up in the final patch. Lower is
  better (the agent zeroes in on the right file sooner).
- **Explore→act transition — first-edit step:** the first iteration that calls
  `edit_file`. It shows how much the agent looks around before it starts fixing.

| Model | Task | First-touch | First-edit | # edits |
|-------|------|:-----------:|:----------:|:-------:|
| deepseek/deepseek-chat | sympy-18189 | 1 | 2 | 1 |
| deepseek/deepseek-chat | sympy-13480 | 1 | 2 | 1 |
| deepseek/deepseek-chat | xarray-4629 | 6 | 6 | 1 |
| gemma-4-31b | sympy-18189 | 10 | 11 | 1 |
| gemma-4-31b | sympy-13480 | 4 | 5 | 2 |
| gemma-4-31b | xarray-4629 | 5 | 9 | 1 |
| kimi-k2 | sympy-13480 | 1 | 2 | 1 |
| llama-3.3-70b-versatile | xarray-4629 | 1 | 2 | 1 |
| devstral-medium-latest | sympy-13480 | — | — | 0 |
| devstral-medium-latest | xarray-4629 | — | 28 | 1 |

Reading: **deepseek is the most surgical** — it lands on the right file at step 1
and edits at step 2 on both sympy tasks, with a single edit each. **devstral
never really acts** — zero edits on one task, a lone edit at step 28 (out of 30)
on the other: it spends the whole budget failing to emit a valid code block
rather than fixing anything.

## 5. Ablation study

**Dimension: tool set.** Baseline = the full 9-tool SWE server. Variant =
the same server with `search_function_or_class_definition_in_code` removed
(8 tools). Because the tool manual in the system prompt is generated from
whatever the connected MCP server advertises, dropping the tool from the server
also drops it from the prompt automatically — no prompt edit needed. Same model
and task (`gemma-4-31b`, `sympy-18189`), run with `--mcp-stdio` pointing at each
server.

| Variant | Tools | Task | Pass | Iterations | Input tok |
|---------|:-----:|------|:----:|:----------:|----------:|
| baseline | 9 | sympy-18189 | ✅ | 15 | 88 414 |
| no `search_..._definition` | 8 | sympy-18189 | ✅ | 11 | 47 708 |

**What it shows:** removing the definition-search tool did not stop the agent —
it fell back to `search_code` / `list_files` and still resolved the task. The
tool is a convenience, not a requirement, at least for this instance. The
iteration difference (15 → 11) is within the run-to-run noise of `temperature =
0.5`, so it should not be read as "fewer tools is faster." The useful takeaway is
architectural: the agnostic prompt correctly re-described the smaller tool set
with zero code changes.

## 6. Conclusions

- **Selected model for the default pipeline: `gemma-4-31b` (Cerebras).** It
  resolves 3/3 on a **free** provider, so the default runs without spending any
  credit. `DEFAULT_MODEL` / `DEFAULT_PROVIDER` are set to it. Cost: ~2× the
  iterations, ~3.6× the input tokens and ~6× the wall time of the paid winner,
  and it leans on backoff to survive Cerebras' rate limits — but it stays
  comfortably inside the budgets.
- **Fastest model overall: `deepseek/deepseek-chat` (OpenRouter).** Also 3/3,
  and the most efficient of the whole pool: ~5 iterations, ~15k input tokens,
  ~24 s per task, most reliable API (0 retries), most directed exploration
  (first edit at step 2). It is the model to switch the default to when a paid
  OpenRouter budget is available — during this benchmark the OpenRouter test
  credit was exhausted (the 402 in §2), which is the practical reason the free
  `gemma-4-31b` is the default.
- **Disregarded — `devstral-medium-latest`:** 0/3. It does not follow the
  ```` ```python … ``` ````+`<end_code>` protocol on long runs — it emits code
  without a fenced block, never stops on the stop token, and eventually produces
  an empty assistant turn that Mistral's API rejects (HTTP 400). A coding model
  on paper, unusable through this agent's I/O contract.
- **Disregarded — `llama-3.3-70b-versatile` on Groq:** 1/3, purely a provider
  limit — Groq's free tokens-per-minute budget cannot hold a SWE context, so
  the two larger tasks 429'd before finishing. The model itself solved the
  small task in 4 iterations.
- **Disregarded — `moonshotai/kimi-k2`:** 1/3 among the runs that completed
  (verbose, hit the 30-iteration cap on `sympy-18189`). Its third task was cut
  off when the OpenRouter test credit hit 402, so treat its score as a partial
  measurement, not a clean 1/3.

**Bottom line:** with the right model the framework clears the target
comfortably — deepseek and gemma both resolve 3/3 of the sampled Verified tasks
under the token/iteration budgets. Model choice dominates the outcome far more
than task difficulty here, and for non-reasoning models the binding constraints
are (a) whether the model respects the code-block I/O contract and (b) whether
the provider's free-tier rate limit can carry a SWE-sized context.

---

### Reproducing

```
# 1. dump a task (moulinette venv)
python -m moulinette dump swebench --task_id sympy__sympy-18189 \
       --output benchmarks/tasks/sympy-18189.json

# 2. run one model on it
uv run agent_swebench --task-file benchmarks/tasks/sympy-18189.json \
       --output benchmarks/deepseek-chat/sympy-18189.json \
       --model-name deepseek/deepseek-chat --provider openrouter

# 3. grade the produced patch (official swebench resolution).
#    Run with the moulinette venv (it has the swebench library + docker).
<moulinette>/.venv/bin/python benchmarks/validate_swe.py \
       benchmarks/tasks/sympy-18189.json \
       benchmarks/deepseek-chat/sympy-18189.json
```

See `benchmarks/README.md` for the full layout and the exact commands used.
