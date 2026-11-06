"""Per-task outcome and accuracy of one original-side parity run.

BFCL score files list only the failed entries (after a header line), so an entry
is correct when it was generated and is not in the score file's failure list.
Entries whose model result is an inference error ("Error during inference: ...")
are listed separately so that they can be re-generated as infrastructure failures.
"""

import argparse
import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
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
        generated = {r["id"]: r for r in results}
        failed = {s["id"] for s in scores[1:] if "id" in s}
        for test_id in ids:
            if test_id not in generated:
                missing.append(test_id)
                continue
            result = generated[test_id]["result"]
            if isinstance(result, str) and result.startswith("Error during inference"):
                inference_errors.append(test_id)
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
    print(json.dumps({k: v for k, v in summary.items() if k not in ("per_task",)}, indent=2))


if __name__ == "__main__":
    main()
