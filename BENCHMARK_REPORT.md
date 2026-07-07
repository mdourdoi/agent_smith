# Model Benchmark Report

## 1. Setup

- **Benchmark:** SWE-bench Verified, tasks from the moulinette `SEED_POOL`
  (`<15 min fix` difficulty - verified solvable, so a failure measures the
  model, not the task).
- **Tasks (3):** `sympy__sympy-18189`, `sympy__sympy-13480`,
  `pydata__xarray-4629` - two repos, three bug kinds (missing argument
  propagation, typo on an undefined name, attrs aliasing).
- **Models (5, distinct families, non-reasoning):** reasoning tokens count
  toward the output budget (subject VI.1), so the pool is deliberately
  non-reasoning. Every provider is free (free tier or trial credits).

  | # | Model | Provider | Family | Tier |
  |---|-------|----------|--------|------|
  | 1 | `llama-3.3-70b-versatile` | Groq | Meta Llama | free tier |
  | 2 | `gemma-4-31b` | Cerebras | Google Gemma | free tier |
  | 3 | `mistral-medium-latest` | Mistral | Mistral | free tier |
  | 4 | `deepseek/deepseek-chat` | OpenRouter | DeepSeek | free trial |
  | 5 | `moonshotai/kimi-k2` | OpenRouter | Moonshot | free trial |

- **Limits (subject VI.1):** 30 iterations, 300k input tokens, 10k output
  tokens, 900 s per task.
- **Pass** is the official SWE-bench grade: patch applied in the task's
  Docker image, eval script run, FULL resolution decided by `swebench`'s own
  grading functions. Backing files: `benchmarks/<model>/<task>.json`
  (solution) and `<task>.val.json` (verdict).

## 2. Results

| Model | Provider | Task | Pass | Iter | Input tok | Output tok | Time (s) |
|-------|----------|------|------|-----:|----------:|-----------:|---------:|
| llama-3.3-70b-versatile | Groq | sympy-18189 | ✗ (429) | - | - | - | - |
| llama-3.3-70b-versatile | Groq | sympy-13480 | ✗ (429) | - | - | - | - |
| llama-3.3-70b-versatile | Groq | xarray-4629 | ✅ | 4 | 10 195 | 434 | 34.3 |
| gemma-4-31b | Cerebras | sympy-18189 | ✅ | 15 | 88 414 | 1 860 | 156.8 |
| gemma-4-31b | Cerebras | sympy-13480 | ✅ | 9 | 26 284 | 1 333 | 121.2 |
| gemma-4-31b | Cerebras | xarray-4629 | ✅ | 11 | 52 840 | 1 672 | 152.5 |
| mistral-medium-latest | Mistral | sympy-18189 | ✗ (429) | - | - | - | - |
| mistral-medium-latest | Mistral | sympy-13480 | ✅ | 16 | 97 475 | 1 268 | 126.3 |
| mistral-medium-latest | Mistral | xarray-4629 | ✗ (429) | - | - | - | - |
| deepseek/deepseek-chat | OpenRouter | sympy-18189 | ✅ | 4 | 12 709 | 290 | 15.9 |
| deepseek/deepseek-chat | OpenRouter | sympy-13480 | ✅ | 4 | 8 147 | 237 | 12.1 |
| deepseek/deepseek-chat | OpenRouter | xarray-4629 | ✅ | 8 | 25 422 | 1 539 | 45.0 |
| moonshotai/kimi-k2 | OpenRouter | sympy-18189 | ✗ | 30 | 115 833 | 1 388 | 76.9 |
| moonshotai/kimi-k2 | OpenRouter | sympy-13480 | ✅ | 13 | 51 106 | 981 | 53.0 |
| moonshotai/kimi-k2 | OpenRouter | xarray-4629 | ✗ (402) | - | - | - | - |

`429` = provider rate limit killed the run before a solution was written;
`402` = the OpenRouter trial allowance ran out mid-benchmark. Provider/quota
outcomes, not model failures on the task.

| Model | Solved | Avg iter | Avg input tok | Avg time (s) |
|-------|:------:|---------:|--------------:|-------------:|
| deepseek/deepseek-chat | **3/3** | 5.3 | 15 426 | 24 |
| gemma-4-31b | **3/3** | 11.7 | 55 846 | 144 |
| mistral-medium-latest | 1/3 | 16.0 | 97 475 | 126 |
| moonshotai/kimi-k2 | 1/3 | 21.5 | 83 470 | 65 |
| llama-3.3-70b-versatile | 1/3 | 4.0 | 10 195 | 34 |

(Averages over runs that produced a solution.)

## 3. Provider reliability

`request_time_ms` and `retries` are recorded per step in each
`solution.json`; retries = transient failures (429/5xx) absorbed by the
client's backoff before a call succeeded.

| Model / provider | Avg resp / request | Retries | Availability |
|------------------|-------------------:|--------:|:------------:|
| deepseek/deepseek-chat / OpenRouter | 3.9 s | 0 | 3/3 |
| gemma-4-31b / Cerebras | 12.3 s | 84 | 3/3 |
| moonshotai/kimi-k2 / OpenRouter | 3.2 s | 0 | 2/3 |
| llama-3.3-70b-versatile / Groq | 8.2 s | 7 | 1/3 |
| mistral-medium-latest / Mistral | 7.6 s | 9 | 1/3 |

Main finding: large SWE contexts (30k-270k input tokens) do not fit Groq's
and Mistral's free tokens-per-minute windows - the same models solved the
small task and were rate-limited to death on the larger ones. Cerebras
rate-limits too (84 retries) but its window resets fast enough that every
run finished.

## 4. Intermediary metrics

Two measurements of exploration efficiency (subject option: step at which
the agent first reads/edits the file that appears in the final patch),
split into its read and write halves, measured by walking each
`solution.json` `steps` array:

- **First-touch**: first step whose code reads or edits a file in the final
  patch.
- **First-edit**: first step that calls `edit_file` (explore→act
  transition).

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
| mistral-medium-latest | sympy-13480 | 1 | 2 | 1 |

Reading: deepseek is the most surgical (right file at step 1, single edit
at step 2 on both sympy tasks); gemma explores more (first touch at step
4-10) but converges. Only runs that produced a patch appear.

## 5. Ablation study

**Dimension: tool set.** Baseline = the full 9-tool SWE server; variant =
the same server with `search_function_or_class_definition_in_code` removed
(8 tools). Same model and task, run with `--mcp-stdio` pointing at each
server. Backing file: `benchmarks/ablation/sympy-18189-reduced.json`.

| Variant | Tools | Task | Model | Pass | Iterations | Input tok |
|---------|:-----:|------|-------|:----:|:----------:|----------:|
| baseline | 9 | sympy-18189 | gemma-4-31b | ✅ | 15 | 88 414 |
| no `search_..._definition` | 8 | sympy-18189 | gemma-4-31b | ✅ | 11 | 47 708 |

The agent fell back to `search_code` / `list_files` and still resolved the
task: the definition-search tool is a convenience, not a requirement, for
this instance. The iteration difference (15 → 11) is within run-to-run
noise at `temperature=0.5` and should not be read as "fewer tools is
faster". The tool manual in the system prompt is generated from whatever
the connected server advertises, so removing the tool required zero code
change.

## 6. Conclusions

- **Selected for the default pipeline: `gemma-4-31b` (Cerebras)** - 3/3 on
  a pure free tier, so the default runs without touching trial credits.
  `DEFAULT_MODEL` / `DEFAULT_PROVIDER` point to it. Costs ~2x the
  iterations and ~6x the wall time of deepseek, but stays well inside every
  budget.
- **Fastest overall: `deepseek/deepseek-chat` (OpenRouter)** - 3/3, ~5
  iterations, ~15k input tokens, ~24 s per task, 0 retries, most directed
  exploration. The model to switch to while an OpenRouter trial allowance
  lasts; ours ran out during this benchmark (the 402), which is why the
  free-tier gemma is the default.
- **Disregarded - `mistral-medium-latest`:** codes fine (solved the small
  task riding out 9 rate-limit hits) but Mistral's free tier (25k
  tokens/minute) cannot carry the two larger SWE contexts. Its rows were
  produced after two model-agnostic harness fixes (a prompt clause stating
  the agent has no native tool-calling, and never sending an empty
  assistant turn), which are inert for the other models.
- **Disregarded - `llama-3.3-70b-versatile` (Groq):** solved the small task
  in 4 iterations; Groq's free tokens-per-minute budget 429'd the two
  larger ones. A provider ceiling, not a model failure.
- **Disregarded - `moonshotai/kimi-k2`:** verbose, hit the 30-iteration cap
  on sympy-18189; its third task died on the 402, so its 1/3 is a partial
  measurement.

Bottom line: model choice dominates the outcome. For non-reasoning models
the binding constraints are (a) whether the model respects the code-block
I/O contract and (b) whether the provider's free-tier rate limit can carry
a SWE-sized context. deepseek and gemma both clear 3/3 within every budget.
