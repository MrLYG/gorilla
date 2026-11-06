#!/usr/bin/env bash
# Original-side parity run for the Harbor `bfcl-autoadapter` adapter.
#
# Usage (from berkeley-function-call-leaderboard/):
#   harbor_parity/run_parity.sh <run_name> [num_threads] [ids_file]
#
# Needs OPENAI_API_KEY and OPENAI_BASE_URL (OpenAI-compatible endpoint that serves
# `deepseek-v4.1-flash`). Generates responses for the task IDs in the ids file
# (default: harbor_parity/parity_task_ids.json), scores them with the unchanged
# BFCL evaluator, and writes harbor_parity/runs/<run_name>/summary.json.
set -euo pipefail
cd "$(dirname "$0")/.."

RUN="${1:?run name}"
THREADS="${2:-32}"
IDS_FILE="${3:-harbor_parity/parity_task_ids.json}"
MODEL="deepseek-v4.1-flash-FC"
CATEGORIES="simple_python simple_java simple_javascript multiple parallel parallel_multiple irrelevance live_simple live_multiple live_parallel live_parallel_multiple live_irrelevance live_relevance"

export BFCL_PROJECT_ROOT="$PWD"
RUN_DIR="harbor_parity/runs/$RUN"
mkdir -p "$RUN_DIR"

# `bfcl generate --run-ids` reads the IDs from <project root>/test_case_ids_to_generate.json
cp "$IDS_FILE" test_case_ids_to_generate.json

start=$(date +%s)
bfcl generate --model "$MODEL" --run-ids --num-threads "$THREADS" \
  --result-dir "$RUN_DIR/result" 2>&1 | tee "$RUN_DIR/generate.log" | grep -E "Error|❗" || true
end=$(date +%s)
echo "generation wall time: $((end - start)) s" | tee "$RUN_DIR/wall_time.txt"

# shellcheck disable=SC2086
bfcl evaluate --model "$MODEL" --test-category $CATEGORIES \
  --result-dir "$RUN_DIR/result" --score-dir "$RUN_DIR/score" --partial-eval \
  > "$RUN_DIR/evaluate.log" 2>&1

python harbor_parity/collect.py --ids "$IDS_FILE" --run-dir "$RUN_DIR" --model "$MODEL" \
  --out "$RUN_DIR/summary.json"
