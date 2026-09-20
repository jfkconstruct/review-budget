# Stage 2: what does a reviewer hour buy?

Run 2026-09-19. Raw output in `runs/queue-2026-09-19.txt`, reproduced by
`python budget.py --replicates 2000`. No API calls: this replays stage 1's per-row
probabilities from `runs/*.jsonl`.

## The setup

398 auto-decided cases, the rows all three bake-off arms answered. A budget of **4
reviewer hours** at 6 minutes a case buys **40 reviews, 10% of the queue**. Every wrong
answer that ships unreviewed costs something. Five policies choose which 40 to open:

| policy | ranks by |
|---|---|
| `random` | nothing. The floor. |
| `threshold` | a fixed confidence cutoff, worked in arrival order. What most teams actually run. |
| `uncertainty` | P(wrong), highest first. Confidence-only triage. |
| `expected-harm` | P(wrong) x cost. The proposal. |
| `oracle` | the actual errors, most expensive first. The ceiling. |

**Costs are synthetic and the shape is a claim, so three shapes run.** `uniform` (flat),
`lognormal` (a heavy tail independent of difficulty), and `adversarial` (the expensive
cases are the ones the models feel surest about). The same cost vector goes to every arm.
The reviewer is assumed perfect, which is an upper bound applied equally to all five rows.

## The result

Harm averted, as a share of the harm sitting in the queue, at 40 reviews:

| arm | regime | threshold | uncertainty | expected-harm | oracle |
|---|---|---|---|---|---|
| `jev-1.13` | lognormal | 16.4% | 37.8% | **50.9%** | 100.0% |
| `jev-1.13` | adversarial | 15.6% | 32.3% | **46.3%** | 100.0% |
| `gemini-2.5-flash-lite` | lognormal | 14.0% | 17.6% | **42.5%** | 98.3% |
| `gpt-5-mini` | lognormal | 15.9% | 19.6% | **33.3%** | 99.9% |

On Jev's probabilities, four reviewer hours spent on expected harm avert half the harm in
the queue. The same four hours spent on a fixed cutoff avert a sixth of it. To reach what
expected-harm reached, the cutoff policy needs a median **82 reviews, 2.0x the budget, 8.2
hours instead of 4**.

The gap widens as the budget tightens rather than closing, which is the direction a
budget argument has to run: at **1 reviewer hour** (10 reviews) Jev's expected-harm queue
averts 23.4% of lognormal harm against the fixed cutoff's 1.0%.

**The line worth keeping: expected-harm catches FEWER errors and averts MORE harm.** On
Jev under lognormal costs it opens 6.6 wrong cases against uncertainty's 9.0, and still
comes out 13 points ahead. Counting errors caught is the wrong scoreboard, which is why a
review queue sorted by confidence leaves money on the table even when its hit rate looks
better.

## What the intervals actually license

The mean differences are large and every one of them straddles zero:

    jev, lognormal, expected-harm vs threshold:   +34.5% mean, 95% [-4.8%, +74.4%]
    jev, lognormal, expected-harm vs uncertainty: +13.2% mean, 95% [-17.7%, +59.0%]

That is not a failure of the policy, it is the shape of the cost distribution. Under a
lognormal tail a single expensive error can carry a third of the queue's harm, so whether
that case exists in a given resample swings the magnitude far more than the policy does.
More replicates will not fix it and neither will a bigger budget; only more labeled cases
would.

The **direction** does not have that problem, and on a paired design it is a sign test:

| comparison | won | 95% |
|---|---|---|
| jev, lognormal, vs `threshold` | 96% of 1996 resamples | [94%, 98%] |
| jev, lognormal, vs `uncertainty` | 69% of 1982 resamples | [67%, 71%] |
| jev, adversarial, vs `uncertainty` | 69% of 1993 resamples | [67%, 71%] |
| gpt-5-mini, lognormal, vs `uncertainty` | 69% of 1942 resamples | [67%, 71%] |

**Caveat that belongs beside the number rather than under it:** the replicate count is a
knob, so this interval narrows as replicates are added without one new labeled case
arriving. It describes the resampling distribution of this 398-case queue and nothing
wider. The honest claim is "the direction is stable under resampling", never "the
direction is established".

This is stage 1's lesson arriving a second time from the other side. There the mistake
available was reading a thin bin's gap as miscalibration. Here it was available in
reverse: reading two overlapping marginal ranges as "no difference" when the comparison is
paired and the difference is the thing being measured.

## Where calibration shows up in the money

Run the identical policy on three different probability sources and it stops being
identical:

| arm | expected-harm, lognormal | vs its own `uncertainty` baseline |
|---|---|---|
| `jev-1.13` | 50.9% | +13.2%, won 69% |
| `gemini-2.5-flash-lite` | 42.5% | +24.9%, won 96% |
| `gpt-5-mini` | 33.3% | +13.7%, won 69% |

Jev's queue averts the most harm per reviewer hour, which is stage 1's coverage gap showing
up as budget rather than as a column in a metrics table. The reading that survives: the
policy is a multiplication, one factor is a probability, and a probability you have not
measured makes the product a guess with a decimal point in it.

Note the honest wrinkle in that table. Cost-awareness helps gemini MORE in relative terms
than it helps Jev, and that is not a point for gemini: gemini's uncertainty ranking is so
weak that the cost term is carrying the sort almost alone. The absolute column is the one
that pays a reviewer.

## What this does not show

- **No dollar figure.** Costs are invented. Every number here is a share of a synthetic
  quantity, and the three regimes exist so the shape is visible rather than assumed.
- **A perfect reviewer.** Every policy is scored against the same optimistic assumption,
  so the ordering holds and the levels do not.
- **One task, one queue.** BoolQ. The bands are not transferable and nothing here gates.
- **Not a live system.** This is a simulation over recorded probabilities.

## Reproduce

```
python budget.py --replicates 2000
python budget.py --budget-hours 1 --replicates 2000   # does the gap survive a tighter budget
```
