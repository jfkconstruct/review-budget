"""Pull a BoolQ validation sample from the HF datasets-server (public, no auth).

    python projects/review-budget/fetch_boolq.py --n 400 --seed 0

BoolQ is a yes/no reading-comprehension set with gold labels, so calibration is
measurable without any hand-labeling. That is the whole point of using it here:
the bake-off must not rest on labels we invented.
"""
from __future__ import annotations

import argparse
import json
import random
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "boolq-dev.jsonl"
URL = ("https://datasets-server.huggingface.co/rows?dataset=google%2Fboolq"
       "&config=default&split=validation&offset={offset}&length={length}")
PAGE = 100


def fetch(n):
    rows = []
    offset = 0
    while len(rows) < n:
        url = URL.format(offset=offset, length=min(PAGE, n - len(rows)))
        with urllib.request.urlopen(url, timeout=60) as resp:
            payload = json.load(resp)
        batch = payload.get("rows", [])
        if not batch:
            break
        rows.extend(r["row"] for r in batch)
        offset += len(batch)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = fetch(args.n)
    random.Random(args.seed).shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for i, row in enumerate(rows):
            fh.write(json.dumps({
                "id": f"boolq-{i:04d}",
                "question": row["question"],
                "passage": row["passage"],
                "gold": bool(row["answer"]),
            }) + "\n")
    yes = sum(1 for r in rows if r["answer"])
    print(f"wrote {len(rows)} rows to {OUT}  (base rate yes={yes / len(rows):.3f})")


if __name__ == "__main__":
    main()
