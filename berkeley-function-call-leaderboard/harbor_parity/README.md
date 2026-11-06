# Harbor parity setup for BFCL single-turn (`bfcl-autoadapter`)

This branch (`harbor-parity`) adds what is needed to run the original BFCL harness for the
parity experiment of the Harbor adapter `bfcl-autoadapter`. It is based on upstream commit
`6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`. **No prompt, data, inference or scoring code is
changed.**

## Changes to the original repository

| File | Change | Affects scores? |
|---|---|---|
| `bfcl_eval/constants/model_config.py` | Adds the model entry `deepseek-v4.1-flash-FC`: API model `deepseek-v4.1-flash`, handler `OpenAICompletionsHandler` (the generic OpenAI chat-completions handler, which reads `OPENAI_API_KEY` and `OPENAI_BASE_URL`), `is_fc_model=True` (function-calling mode), `underscore_to_dot=True` (as for other FC models whose tool names cannot contain `.`). | No (new model entry only) |
| `bfcl_eval/constants/supported_models.py` | Lists the new model key. | No |
| `harbor_parity/run_parity.sh` | Runs `bfcl generate --run-ids` and `bfcl evaluate --partial-eval` for one run, then `collect.py`. | No |
| `harbor_parity/retry_errors.sh` | Re-generates only the entries that hit an inference (API) error, then re-scores. | No |
| `harbor_parity/collect.py` | Reads the result and score files and writes per-task outcomes and the accuracy over the task IDs (micro average). Fails if a score file is missing or inconsistent. | No |
| `harbor_parity/all_task_ids.json` | The 3635 task IDs of the Harbor dataset (all 13 single-turn categories, minus 6 entries that no answer can pass, see below). | — |
| `harbor_parity/sanity_task_ids.json` | 10 task IDs (one per large category, seed 20261106) for the sanity check. | — |

Excluded entries (same on both sides; their ground truth and function doc disagree, so the
unchanged checker fails every answer): `simple_java_36`, `simple_java_65`,
`live_simple_106-63-0`, `live_simple_112-68-0`, `live_multiple_862-181-3`,
`live_multiple_964-207-0`.

## Parity settings (identical on both sides)

- Model: `deepseek-v4.1-flash` through an OpenAI-compatible endpoint (`OPENAI_BASE_URL`), function-calling mode, `temperature=0.001` (the `bfcl generate` default), `store=False`, no `max_tokens`, no system prompt; tools = the hinted function docs converted with `convert_to_tool(..., OPENAI_COMPLETIONS)`.
- Retries: BFCL's backoff on `RateLimitError` only; other API errors are recorded as `Error during inference: ...` and re-generated as infrastructure failures (`retry_errors.sh`).
- Metric: accuracy over the 3635 tasks (fraction of tasks that BFCL's checker accepts).
- Harbor side: the adapter's `bfcl-fc-agent` (`bfcl_autoadapter.agents.bfcl_fc_agent:BfclFcAgent`), which sends the same request and decodes the response the same way.

## Reproduce

Setup, original side:

```bash
cd berkeley-function-call-leaderboard
python -m venv .venv && source .venv/bin/activate      # Python 3.11
pip install -e .
pip install soundfile          # imported by qwen-agent, not pulled in by `pip install -e .`
export OPENAI_API_KEY=...  OPENAI_BASE_URL=...          # endpoint serving deepseek-v4.1-flash
```

Setup, Harbor side (adapters repository root, Harbor 0.25.0):

```bash
(cd src/bfcl-autoadapter && uv run bfcl-autoadapter --output-dir ../../datasets/bfcl-autoadapter)
HARBOR='uvx --python 3.12 --from harbor[daytona]==0.25.0 --with ./src/bfcl-autoadapter harbor'
AGENT='-a bfcl_autoadapter.agents.bfcl_fc_agent:BfclFcAgent -m openai/deepseek-v4.1-flash'
ENV='-e daytona --ek auto_snapshot=true'
```

Run both sides at the same time, in this order:

```bash
# 1. Sanity check (10 tasks) on both sides
harbor_parity/run_parity.sh sanity 10 harbor_parity/sanity_task_ids.json
$HARBOR run -p datasets/bfcl-autoadapter $AGENT $ENV -n 10 --job-name harbor-sanity \
  $(python -c "import json;print(' '.join('-i bfcl-autoadapter__'+i.lower().replace('_','-') for v in json.load(open('harbor_parity/sanity_task_ids.json')).values() for i in v))")

# 2. One full run (3635 tasks) on both sides
harbor_parity/run_parity.sh run1 100
$HARBOR run -p datasets/bfcl-autoadapter $AGENT $ENV -n 100 --job-name harbor-run1

# 3. Runs 2 and 3 on both sides
harbor_parity/run_parity.sh run2 100 & harbor_parity/run_parity.sh run3 100
$HARBOR run -p datasets/bfcl-autoadapter $AGENT $ENV -n 50 --job-name harbor-run2 &
$HARBOR run -p datasets/bfcl-autoadapter $AGENT $ENV -n 50 --job-name harbor-run3

# Infrastructure failures only (never because of the score):
harbor_parity/retry_errors.sh run1 100                       # original side
$HARBOR job resume -p jobs/harbor-run1 -f <ExceptionType>    # Harbor side
```

Each original run writes `harbor_parity/runs/<run>/summary.json` (`accuracy`, `n_correct`, `n_tasks`, `per_task`). On the Harbor side the accuracy of a run is the job's mean reward. Report mean ± sample SEM over the 3 runs of each side and check that the run ranges overlap.

## Results

RESULTS_PENDING
