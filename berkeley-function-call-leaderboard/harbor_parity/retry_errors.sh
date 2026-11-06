#!/usr/bin/env bash
# Re-generate the entries of a run that failed with an inference error (infrastructure
# failure, e.g. a gateway error) or are missing, then re-score the whole run.
#
# Usage (from berkeley-function-call-leaderboard/):
#   harbor_parity/retry_errors.sh <run_name> [num_threads] [ids_file]
set -euo pipefail
cd "$(dirname "$0")/.."

RUN="${1:?run name}"
THREADS="${2:-32}"
IDS_FILE="${3:-harbor_parity/all_task_ids.json}"
MODEL="deepseek-v4.1-flash-FC"
CATEGORIES="simple_python simple_java simple_javascript multiple parallel parallel_multiple irrelevance live_simple live_multiple live_parallel live_parallel_multiple live_irrelevance live_relevance"
export BFCL_PROJECT_ROOT="$PWD"
RUN_DIR="harbor_parity/runs/$RUN"

python - "$RUN_DIR/summary.json" "$IDS_FILE" > test_case_ids_to_generate.json <<'PY'
import json, sys
summary = json.load(open(sys.argv[1]))
ids_by_cat = json.load(open(sys.argv[2]))
todo = set(summary["inference_errors"]) | set(summary["missing"])
print(json.dumps({c: [i for i in ids if i in todo] for c, ids in ids_by_cat.items()}))
PY

# --run-ids + --allow-overwrite replaces only these entries in the existing result files
bfcl generate --model "$MODEL" --run-ids --allow-overwrite --num-threads "$THREADS" \
  --result-dir "$RUN_DIR/result" >> "$RUN_DIR/generate.log" 2>&1

rm -rf "$RUN_DIR/score"
# shellcheck disable=SC2086
bfcl evaluate --model "$MODEL" --test-category $CATEGORIES \
  --result-dir "$RUN_DIR/result" --score-dir "$RUN_DIR/score" --partial-eval \
  > "$RUN_DIR/evaluate.log" 2>&1

python harbor_parity/collect.py --ids "$IDS_FILE" --run-dir "$RUN_DIR" --model "$MODEL" \
  --out "$RUN_DIR/summary.json"
