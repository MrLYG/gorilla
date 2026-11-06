"""Per-task outcome and accuracy of one original-side parity run.

BFCL score files start with a header line ({"accuracy", "correct_count",
"total_count"}) followed by one line per failed entry. An entry is correct when it
was scored and is not in the failure list. The collector stops with an error if a
category's result or score file is missing, or if the header counts do not match
the result file, so that a missing evaluation can never count as success.

Entries whose model result is an inference error ("Error during inference: ...")
are infrastructure failures: they are reported in `inference_errors`, left out of
`per_task` and of the accuracy, and should be re-generated (see README).
"""

import argparse
import json
import sys
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        sys.exit(f"missing file: {path}")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--model", default="deepseek-v4.1-flash-FC")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    ids_by_cat = json.loads(args.ids.read_text())
    model_dir = args.model.replace("/", "_")
    per_task: dict[str, int] = {}
    inference_errors: list[str] = []
    missing: list[str] = []
    for category, ids in ids_by_cat.items():
        if not ids:
            continue
        group = "live" if category.startswith("live_") else "non_live"
        results = load_jsonl(args.run_dir / "result" / model_dir / group / f"BFCL_v4_{category}_result.json")
        scores = load_jsonl(args.run_dir / "score" / model_dir / group / f"BFCL_v4_{category}_score.json")
        header = scores[0]
        if "total_count" not in header or "correct_count" not in header:
            sys.exit(f"{category}: score file has no header line")
        if header["total_count"] != len(results):
            sys.exit(f"{category}: scored {header['total_count']} entries but the result file has {len(results)}")
        failed = {s["id"] for s in scores[1:]}
        if header["correct_count"] != len(results) - len(failed):
            sys.exit(f"{category}: header correct_count does not match the failure list")
        generated = {r["id"]: r for r in results}
        for test_id in ids:
            if test_id not in generated:
                missing.append(test_id)
                continue
            result = generated[test_id]["result"]
            if isinstance(result, str) and result.startswith("Error during inference"):
                inference_errors.append(test_id)
                continue
            per_task[test_id] = 0 if test_id in failed else 1

    n = len(per_task)
    summary = {
        "model": args.model,
        "n_tasks": n,
        "n_correct": sum(per_task.values()),
        "accuracy": (sum(per_task.values()) / n) if n else None,
        "n_missing": len(missing),
        "missing": missing,
        "n_inference_errors": len(inference_errors),
        "inference_errors": inference_errors,
        "per_task": per_task,
    }
    args.out.write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "per_task"}, indent=2)[:2000])
    if missing or inference_errors:
        print("Incomplete run: re-generate the missing / errored entries before using this run.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
