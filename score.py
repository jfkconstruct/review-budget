"""Score every bake-off arm on the numbers a router actually needs.

    python projects/review-budget/score.py

Accuracy is the least interesting column here and is reported only so nobody mistakes a
calibration win for a capability win. The columns that decide whether a workflow can route
on a band are ECE and the coverage ones: if a model's 0.9 really means 0.9, you can hand
the confident slice to the machine and buy back human hours. If it does not, the band is
decoration.

No gating happens in this file. It fits nothing and it thresholds nothing; it reports.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BINS = 10


def load(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r.get("p_yes") is not None]


def brier(rows):
    return sum((r["p_yes"] - float(r["gold"])) ** 2 for r in rows) / len(rows)


def accuracy(rows):
    return sum(((r["p_yes"] >= 0.5) == r["gold"]) for r in rows) / len(rows)


def reliability(rows, bins=BINS):
    """Equal-width bins of predicted P(yes) against the observed rate of yes."""
    table = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        got = [r for r in rows if (lo <= r["p_yes"] < hi) or (b == bins - 1 and r["p_yes"] == 1.0)]
        if not got:
            continue
        table.append({
            "lo": lo, "hi": hi, "n": len(got),
            "predicted": sum(r["p_yes"] for r in got) / len(got),
            "observed": sum(float(r["gold"]) for r in got) / len(got),
        })
    return table


def wilson(k, n, z=1.96):
    """95% interval on the observed rate in a bin.

    The reliability table's middle bins hold a couple of dozen rows at most, so a +0.22
    gap there can be noise wearing a finding's clothes. Printing the interval next to the
    gap is the difference between a measurement and a claim."""
    if not n:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def ece(rows, bins=BINS):
    """Expected calibration error: the gap between promise and delivery, n-weighted."""
    return sum(b["n"] * abs(b["predicted"] - b["observed"]) for b in reliability(rows, bins)) / len(rows)


def auroc(rows):
    """Rank quality, independent of calibration. A model can rank well and still lie
    about its probabilities, which is exactly the case this bake-off has to separate."""
    pos = [r["p_yes"] for r in rows if r["gold"]]
    neg = [r["p_yes"] for r in rows if not r["gold"]]
    if not pos or not neg:
        return float("nan")
    ranked = sorted((p, i) for i, p in enumerate([*pos, *neg]))
    ranks, i = {}, 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
            j += 1
        shared = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[ranked[k][1]] = shared
        i = j + 1
    rank_sum = sum(ranks[i] for i in range(len(pos)))
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def coverage_at(rows, precision, side="both"):
    """The router question: what fraction can be auto-decided while holding `precision`?

    Sweeps the confidence margin and returns the widest band that still meets the bar on
    the auto-decided slice, so the number answers "how many humans do I buy back", not
    "how good is the model"."""
    best = (0.0, None)
    for step in range(50, 101):
        margin = step / 100
        auto = [r for r in rows if r["p_yes"] >= margin or r["p_yes"] <= 1 - margin]
        if not auto:
            continue
        correct = sum(((r["p_yes"] >= 0.5) == r["gold"]) for r in auto)
        if correct / len(auto) >= precision and len(auto) / len(rows) > best[0]:
            best = (len(auto) / len(rows), margin)
    return best


def main():
    paths = sorted(RUNS.glob("*.jsonl"))
    if not paths:
        raise SystemExit(f"no runs in {RUNS}")

    print(f"{'arm':<34} {'n':>4} {'acc':>6} {'ECE':>6} {'Brier':>6} {'AUROC':>6} "
          f"{'cov@95':>7} {'cov@99':>7} {'cost$':>8}")
    tables = {}
    for path in paths:
        rows = load(path)
        if not rows:
            continue
        cost = sum(float((r.get("usage") or {}).get("cost") or 0) for r in rows)
        c95, _ = coverage_at(rows, 0.95)
        c99, _ = coverage_at(rows, 0.99)
        print(f"{path.stem:<34} {len(rows):>4} {accuracy(rows):>6.3f} {ece(rows):>6.3f} "
              f"{brier(rows):>6.3f} {auroc(rows):>6.3f} {c95:>7.1%} {c99:>7.1%} {cost:>8.4f}")
        tables[path.stem] = reliability(rows)
        flips = sum(1 for r in rows if r.get("flipped"))
        if flips:
            print(f"{'':<34} note: {flips} rows reported P(their answer) and were flipped to P(yes)")

    for name, table in tables.items():
        print(f"\nreliability: {name}")
        print(f"  {'band':<12} {'n':>4} {'predicted':>10} {'observed':>9} {'gap':>7}  {'95% CI on observed':<20} sig")
        for b in table:
            gap = b["observed"] - b["predicted"]
            lo, hi = wilson(round(b["observed"] * b["n"]), b["n"])
            # A gap only counts as miscalibration if the predicted value falls OUTSIDE the
            # interval. Everything else is a thin bin.
            sig = "*" if not (lo <= b["predicted"] <= hi) else ""
            print(f"  {f'{b['lo']:.1f}-{b['hi']:.1f}':<12} {b['n']:>4} {b['predicted']:>10.3f} "
                  f"{b['observed']:>9.3f} {gap:>+7.3f}  [{lo:.3f}, {hi:.3f}]{'':<5} {sig}")


if __name__ == "__main__":
    main()
