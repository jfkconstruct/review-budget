"""Precompute everything the stage 3 demo screen renders. No API calls, no research.

    python projects/review-budget/export_demo.py --replicates 2000

Stage 2 answers the question in a terminal table. The demo answers it on a screen a
stranger can drag, so the screen needs two different things and they must not be confused
for each other:

  THE LISTS are one concrete cost draw (seed 0). A reader has to see actual cases to
  believe a ranking is a ranking, and a list averaged over 2000 draws is not a list. The
  page labels this draw as a draw. Stage 2's first wrong turn was reporting a single
  fixed draw AS the measurement; showing one and calling it one is the fix, not a repeat.

  THE NUMBERS under the lists are the bootstrap: fresh cases and fresh costs per
  replicate, exactly budget.py's simulate(), read off at every budget at once because
  cum_share already returns the whole curve.

Writes demo-data.json next to this file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from budget import (COST_REGIMES, POLICIES, REVIEW_MINUTES, case_view, costs_for,
                   cum_share, first_k, load_arms, median_k, paired, rank_keys, summarize)
import random

HERE = Path(__file__).resolve().parent
BUDGET_HOURS = [0.5, 1, 2, 3, 4, 6, 8, 10, 12]

ARM_LABELS = {
    "jev-typesafe_jev-1.13": "Jev 1.13",
    "chat-openai_gpt-5-mini": "gpt-5-mini",
    "chat-google_gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
}
ARM_ORDER = ["jev-typesafe_jev-1.13", "chat-openai_gpt-5-mini", "chat-google_gemini-2.5-flash-lite"]


def r4(x):
    # nan is not JSON, and a policy pair that is identical by construction (expected
    # harm IS uncertainty under flat costs) legitimately has nothing to report.
    if x is None:
        return None
    x = float(x)
    return None if x != x else round(x, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    arms, ids = load_arms()
    ks = [max(1, round(h * 60 / REVIEW_MINUTES)) for h in BUDGET_HOURS]

    questions = {}
    for line in (HERE / "data" / "boolq-dev.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            questions[row["id"]] = row["question"]

    out = {
        "meta": {
            "generated": "2026-09-19",
            "replicates": args.replicates,
            "review_minutes": REVIEW_MINUTES,
            "n_cases": len(ids),
            "budget_hours": BUDGET_HOURS,
            "budget_k": ks,
            "policies": list(POLICIES),
            "regimes": list(COST_REGIMES),
            "arm_order": [a for a in ARM_ORDER if a in arms],
            "arm_labels": {a: ARM_LABELS.get(a, a) for a in arms},
        },
        "ids": ids,
        "questions": [questions.get(i, i) for i in ids],
        "gold": [bool(next(iter(arms.values()))[i]["gold"]) for i in ids],
        # One labeled cost draw, seed 0: what the lists are built from.
        "costs_draw": {rg: [r4(costs_for(ids, arms, rg, seed=args.seed)[i]) for i in ids]
                       for rg in COST_REGIMES},
        "arms": {},
        "bootstrap": {},
    }

    for arm, rows in arms.items():
        cases = {i: case_view(rows[i]) for i in ids}
        out["arms"][arm] = {
            "p_wrong": [r4(cases[i]["p_wrong"]) for i in ids],
            "wrong": [bool(cases[i]["wrong"]) for i in ids],
            "n_wrong": sum(1 for i in ids if cases[i]["wrong"]),
        }
        out["bootstrap"][arm] = {}
        for regime in COST_REGIMES:
            rng = random.Random(args.seed)
            n = len(ids)
            shares = {p: {k: [] for k in ks} for p in POLICIES}
            caught = {p: {k: [] for k in ks} for p in POLICIES}
            needs = {rv: {k: [] for k in ks} for rv in ("threshold", "uncertainty")}
            for r in range(args.replicates):
                costs = costs_for(ids, arms, regime, seed=args.seed + r)
                sample = [ids[rng.randrange(n)] for _ in range(n)]
                keys = {p: rank_keys(ids, cases, costs, p) for p in POLICIES}
                curves = {p: cum_share(sample, keys[p], cases, costs) for p in POLICIES}
                if curves["oracle"] is None:
                    continue
                for p in POLICIES:
                    order = sorted(ids, key=lambda i: (-keys[p][i], i))
                    for k in ks:
                        shares[p][k].append(curves[p][k - 1])
                        caught[p][k].append(sum(1 for i in order[:k] if cases[i]["wrong"]))
                for k in ks:
                    target = curves["expected-harm"][k - 1]
                    for rv in needs:
                        needs[rv][k].append(first_k(curves[rv], target))
            block = {"policies": {}, "vs": {}}
            for p in POLICIES:
                mean = [summarize(shares[p][k]) for k in ks]
                block["policies"][p] = {
                    "share": [r4(m[0]) for m in mean],
                    "lo": [r4(m[1]) for m in mean],
                    "hi": [r4(m[2]) for m in mean],
                    "caught": [r4(sum(caught[p][k]) / len(caught[p][k])) for k in ks],
                }
            for rv in ("threshold", "uncertainty"):
                rows_ = [paired(shares["expected-harm"][k], shares[rv][k]) for k in ks]
                block["vs"][rv] = {
                    "mean": [r4(x[0]) for x in rows_],
                    "lo": [r4(x[1]) for x in rows_],
                    "hi": [r4(x[2]) for x in rows_],
                    "wins": [r4(x[3]) for x in rows_],
                    "half": [r4(x[4]) for x in rows_],
                    "n": [x[5] for x in rows_],
                    "need": [median_k(needs[rv][k], len(ids)) for k in ks],
                }
            out["bootstrap"][arm][regime] = block
        print(f"done {arm}")

    path = HERE / "demo-data.json"
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
