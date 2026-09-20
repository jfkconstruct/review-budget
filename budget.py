"""Stage 2: spend a fixed number of reviewer hours on the cases most likely to matter.

    python projects/review-budget/budget.py
    python projects/review-budget/budget.py --budget-hours 4 --replicates 2000

Stage 1 asked whether a model's probability means what it says. This asks the question a
buyer actually has: given that I can only afford to look at some of these cases myself,
which ones do I look at, and what does the choice buy me?

A queue of auto-decided cases carries harm: every case the machine got wrong costs
something if it ships unreviewed. A reviewer hour spent on a case that was already right,
or on a wrong case that was cheap, is an hour that averted nothing. So the policy question
is a ranking question, and the ranking that matters is expected harm, P(wrong) x cost, not
confidence alone and not a cutoff.

Expected harm is a product with a probability in it, which means this policy inherits
whatever the probability is worth. That is the argument stage 1 was building toward and
the reason this file runs all three bake-off arms over the same queue with the same costs:
the policy is identical, the numbers are not, and the difference is calibration converted
into reviewer hours.

Nothing here calls an API. It replays `runs/*.jsonl` from stage 1.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

REVIEW_MINUTES = 6.0  # one reviewer hour buys 10 reviews
COST_REGIMES = ("uniform", "lognormal", "adversarial")


# ---------------------------------------------------------------- the queue

def load(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r.get("p_yes") is not None]


def load_arms():
    """Every arm, restricted to the case ids all of them answered.

    The arms have to be compared over one queue. gpt-5-mini dropped two rows, so an
    unrestricted comparison would score the arms on different work."""
    arms = {p.stem: {r["id"]: r for r in load(p)} for p in sorted(RUNS.glob("*.jsonl"))}
    arms = {k: v for k, v in arms.items() if v}
    if not arms:
        raise SystemExit(f"no runs in {RUNS}")
    shared = sorted(set.intersection(*(set(v) for v in arms.values())))
    return arms, shared


def case_view(row):
    """What the router knows and what the world will charge for it.

    `p_wrong` is the model's own claim about this case. `wrong` is the fact, available
    only because BoolQ ships gold labels, and used only to score policies after the fact.
    A policy that reads `wrong` is the oracle and is labeled as such."""
    answer = row["p_yes"] >= 0.5
    confidence = max(row["p_yes"], 1 - row["p_yes"])
    return {"p_wrong": 1 - confidence, "wrong": answer != row["gold"]}


# ---------------------------------------------------------------- the costs

def costs_for(ids, arms, regime, seed=0):
    """Per-case cost of shipping a wrong answer. SYNTHETIC, and the shape is a claim.

    BoolQ rows have no dollar value, so any cost vector here is invented. Inventing one
    quietly would make the headline number a decision about the fixture rather than about
    the policy, so three shapes run and all three get reported:

      uniform     every error costs the same. Expected harm collapses to P(wrong) and
                  this regime exists to show what cost-awareness is worth when it is
                  worth nothing.
      lognormal   a heavy tail independent of difficulty, the usual real shape: a few
                  cases carry most of the exposure.
      adversarial the expensive cases are the ones the model feels surest about. This is
                  the regime that punishes confidence-only ranking, and it is the honest
                  stress case rather than the flattering one.

    The same cost vector is handed to every arm, so no arm can win on its costs. In
    `adversarial` the correlation is built from the arms' MEAN confidence, never one
    arm's own, for the same reason."""
    rng = random.Random(seed)
    base = {i: (1.0 if regime == "uniform" else rng.lognormvariate(0, 1)) for i in ids}
    if regime != "adversarial":
        return base
    shared_conf = {
        i: sum(max(a[i]["p_yes"], 1 - a[i]["p_yes"]) for a in arms.values()) / len(arms)
        for i in ids
    }
    # Confidence runs 0.5..1.0; the multiplier runs 1x..4x with the money at the top.
    return {i: base[i] * (1 + 6 * (shared_conf[i] - 0.5)) for i in ids}


# ---------------------------------------------------------------- the policies

def rank_keys(ids, cases, costs, policy):
    """A sort key per case, high first. Ties break on id so every policy is deterministic.

    Precomputed once because the bootstrap resamples the queue thousands of times and the
    keys do not change, only which cases are in the room."""
    if policy == "random":
        rng = random.Random(1234)
        return {i: rng.random() for i in ids}
    if policy == "threshold":
        # What a fixed cutoff actually does: it partitions, it does not rank. Everything
        # under the cutoff is equally flagged and gets worked in arrival order, which is
        # the whole weakness. Flagged cases sort above unflagged ones and nothing more.
        return {i: (1.0 if cases[i]["p_wrong"] > 0.10 else 0.0) for i in ids}
    if policy == "uncertainty":
        return {i: cases[i]["p_wrong"] for i in ids}
    if policy == "expected-harm":
        return {i: cases[i]["p_wrong"] * costs[i] for i in ids}
    if policy == "oracle":
        return {i: (costs[i] if cases[i]["wrong"] else 0.0) for i in ids}
    raise ValueError(policy)


POLICIES = ("random", "threshold", "uncertainty", "expected-harm", "oracle")


def cum_share(sample, keys, cases, costs):
    """Cumulative fraction of the queue's harm averted after 1, 2, ... k reviews.

    One sorted pass gives every budget at once, which is what makes it affordable to
    re-answer "what would this have cost the rival policy" inside every replicate."""
    total = sum(costs[i] for i in sample if cases[i]["wrong"])
    if total <= 0:
        return None
    order = sorted(sample, key=lambda i: (-keys[i], i))
    out, run = [], 0.0
    for i in order:
        if cases[i]["wrong"]:
            run += costs[i]
        out.append(run / total)
    return out


def first_k(curve, target):
    """Reviews the rival needs to reach `target` share, or None if it never does."""
    for k, share in enumerate(curve, 1):
        if share >= target - 1e-12:
            return k
    return None


def simulate(ids, arms, cases, regime, k, replicates, seed):
    """Run every policy over `replicates` redraws of the world.

    Two things are uncertain and both get resampled: WHICH cases landed in this queue
    (bootstrap with replacement) and WHAT the errors cost (a fresh cost vector per
    replicate). An earlier version fixed one cost draw and reported the number it
    produced; on that draw the random policy beat the fixed cutoff, which was a fact
    about the draw and not about either policy. Holding a fixture constant and calling
    the result a measurement is the stage 1 mistake in a new costume.

    The reviewer is assumed perfect: every wrong case they open gets corrected. That is
    an upper bound on what review buys, it is the same upper bound for all five policies,
    and a realistic reviewer accuracy would scale every row by roughly one factor without
    reordering them."""
    rng = random.Random(seed)
    n = len(ids)
    shares = {p: [] for p in POLICIES}
    needs = {p: [] for p in ("threshold", "uncertainty")}
    for r in range(replicates):
        costs = costs_for(ids, arms, regime, seed=seed + r)
        sample = [ids[rng.randrange(n)] for _ in range(n)]
        keys = {p: rank_keys(ids, cases, costs, p) for p in POLICIES}
        curves = {p: cum_share(sample, keys[p], cases, costs) for p in POLICIES}
        if curves["oracle"] is None:
            continue  # a resample with no errors in it has no harm to avert
        for p in POLICIES:
            shares[p].append(curves[p][k - 1])
        target = curves["expected-harm"][k - 1]
        for p in needs:
            needs[p].append(first_k(curves[p], target))
    return shares, needs


def summarize(values):
    v = sorted(values)
    if not v:
        return float("nan"), float("nan"), float("nan")
    lo = v[max(0, int(0.025 * len(v)))]
    hi = v[min(len(v) - 1, int(0.975 * len(v)))]
    return sum(v) / len(v), lo, hi


def paired(a, b):
    """Interval on the WITHIN-replicate difference a - b.

    The marginal ranges on two policies overlap almost completely here, because most of
    the spread is the queue and the cost draw, which both policies face identically. The
    comparison that means anything is therefore paired: subtract inside each replicate and
    interval the difference. Reading two overlapping marginal ranges as "no difference" is
    the same error as reading a thin bin's gap as miscalibration, run in reverse."""
    raw = [x - y for x, y in zip(a, b)]
    d = sorted(raw)
    lo = d[max(0, int(0.025 * len(d)))]
    hi = d[min(len(d) - 1, int(0.975 * len(d)))]
    # The magnitude of the difference rides on whether a single expensive error happened
    # to land in the replicate, so a lognormal tail keeps the mean interval straddling
    # zero however many replicates are run. The DIRECTION does not have that problem, and
    # on a paired design it is a sign test: in what share of replicates did the policy
    # win? A 50% win rate is the null. Reporting only the mean interval here would hide a
    # decision-grade result behind a statistic the fixture cannot resolve.
    #
    # Caveat that belongs next to the number, not in a footnote: the replicate count is
    # a knob, so this interval narrows as replicates are added without a single new
    # labeled case arriving. It describes the resampling distribution of THIS 398-case
    # queue and nothing wider. Read it as "the direction is stable under resampling",
    # never as "the direction is established in the population".
    decided = [x for x in raw if abs(x) > 1e-12]
    wins = sum(x > 0 for x in decided) / len(decided) if decided else float("nan")
    n = len(decided)
    half = 1.96 * (0.25 / n) ** 0.5 if n else float("nan")
    return sum(raw) / len(raw), lo, hi, wins, half, n


def median_k(values, ceiling):
    """Median reviews-to-match. A replicate where the rival never gets there counts as
    the whole queue, so the number is a floor on the real cost, not an optimistic one."""
    v = sorted(ceiling if x is None else x for x in values)
    return v[len(v) // 2] if v else None


# ---------------------------------------------------------------- report

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget-hours", type=float, default=4.0,
                    help=f"reviewer hours; one review takes {REVIEW_MINUTES:g} minutes")
    ap.add_argument("--replicates", type=int, default=500,
                    help="redraws of cases and costs behind every interval")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    arms, ids = load_arms()
    k = max(1, round(args.budget_hours * 60 / REVIEW_MINUTES))
    print(f"queue: {len(ids)} auto-decided cases shared by {len(arms)} arms")
    print(f"budget: {args.budget_hours:g} reviewer hours = {k} reviews "
          f"({k / len(ids):.0%} of the queue), {REVIEW_MINUTES:g} min each")
    print(f"costs: SYNTHETIC. {args.replicates} replicates, each one a fresh cost draw "
          f"over a fresh case bootstrap; ranges are 95% over replicates\n")

    for regime in COST_REGIMES:
        print(f"=== cost regime: {regime}")
        print(f"  {'arm':<34} {'policy':<14} {'harm averted':>12} {'95% range':>18} "
              f"{'errors caught':>14}")
        for arm, rows in arms.items():
            cases = {i: case_view(rows[i]) for i in ids}
            shares, needs = simulate(ids, arms, cases, regime, k, args.replicates, args.seed)
            caught = {p: [] for p in POLICIES}
            for r in range(args.replicates):
                costs = costs_for(ids, arms, regime, seed=args.seed + r)
                for p in POLICIES:
                    keys = rank_keys(ids, cases, costs, p)
                    order = sorted(ids, key=lambda i: (-keys[i], i))[:k]
                    caught[p].append(sum(1 for i in order if cases[i]["wrong"]))
            n_wrong = sum(1 for i in ids if cases[i]["wrong"])
            for policy in POLICIES:
                mean, lo, hi = summarize(shares[policy])
                hit = sum(caught[policy]) / len(caught[policy])
                print(f"  {arm:<34} {policy:<14} {mean:>11.1%} "
                      f"{f'[{lo:.1%}, {hi:.1%}]':>18} {f'{hit:.1f}/{n_wrong}':>14}")
            for rival in ("threshold", "uncertainty"):
                need = median_k(needs[rival], len(ids))
                mean, lo, hi, wins, half, n = paired(shares["expected-harm"], shares[rival])
                if not n:
                    # Under a flat cost vector expected harm IS P(wrong), so the two
                    # policies are the same policy. Saying so beats printing a nan.
                    print(f"  {'':<34} vs {rival:<12} identical by construction "
                          f"in this regime")
                    continue
                verdict = ("wins" if wins - half > 0.5 else
                           "loses" if wins + half < 0.5 else "coin flip")
                print(f"  {'':<34} vs {rival:<12} {mean:>+10.1%} mean "
                      f"{f'[{lo:+.1%}, {hi:+.1%}]':>18}   "
                      f"won {wins:.0%} of {n} resamples "
                      f"[{max(0, wins - half):.0%}, {min(1, wins + half):.0%}] -> {verdict}")
                print(f"  {'':<34}    to match it, {rival} needs a median {need} reviews "
                      f"({need / k:.1f}x the budget, {need * REVIEW_MINUTES / 60:.1f} h)")
            print()


if __name__ == "__main__":
    main()
