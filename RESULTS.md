# Stage 1 results: does the calibration claim survive a gold-labeled test?

Run 2026-09-19. 400 BoolQ validation rows, seed 0, base rate 64.0% yes. Raw output in
`runs/score-2026-09-19.txt`; per-row answers in `runs/*.jsonl`. Every number here is
printed by `score.py`, not typed by hand.

| arm | n | acc | ECE | Brier | AUROC | cov@95 | cov@99 | cost |
|---|---|---|---|---|---|---|---|---|
| `typesafe/jev-1.13` | 400 | **0.938** | **0.047** | **0.057** | **0.972** | **95.0%** | **29.5%** | $0.0069 |
| `openai/gpt-5-mini` | 398 | 0.920 | 0.062 | 0.075 | 0.946 | 35.9% | 0.0% | $0.2468 |
| `google/gemini-2.5-flash-lite` | 400 | 0.890 | 0.076 | 0.096 | 0.925 | 0.0% | 0.0% | $0.0115 |

Jev leads every column. The accuracy spread is small (0.938 vs 0.920) and is not the
finding. The coverage columns are.

## The finding

**Coverage is where the gap is, and coverage is the column that has a dollar value.**
Holding 95% precision on the auto-decided slice, Jev routes 95.0% of traffic without a
human. gpt-5-mini routes 35.9%. gemini-2.5-flash-lite routes nothing: at no threshold
between 0.50 and 1.00 does its confident slice hold 95% precision. Two models a single
accuracy point apart differ by 59 points of automatable volume, because one of them knows
which of its answers to doubt.

At 99% precision only Jev clears the bar at all, and only on 29.5% of traffic. That number
is the honest ceiling of this setup, and it belongs in the pitch as much as the 95% does.

Cost runs the same direction: 400 rows through Jev cost $0.0069 against $0.2468 for
gpt-5-mini, a 36x difference, on the arm with less than half the usable coverage.

## Jev's curve, read honestly

| band | n | predicted | observed | gap | 95% CI on observed | outside CI |
|---|---|---|---|---|---|---|
| 0.0-0.1 | 96 | 0.041 | 0.062 | +0.021 | [0.029, 0.130] | |
| 0.1-0.2 | 30 | 0.130 | 0.133 | +0.003 | [0.053, 0.297] | |
| 0.2-0.3 | 11 | 0.240 | 0.182 | -0.058 | [0.051, 0.477] | |
| 0.3-0.4 | 10 | 0.348 | 0.300 | -0.048 | [0.108, 0.603] | |
| 0.4-0.5 | 6 | 0.468 | 0.333 | -0.135 | [0.097, 0.700] | |
| 0.5-0.6 | 9 | 0.554 | 0.778 | +0.223 | [0.453, 0.937] | |
| 0.6-0.7 | 10 | 0.658 | 0.800 | +0.142 | [0.490, 0.943] | |
| 0.7-0.8 | 19 | 0.761 | 0.895 | +0.134 | [0.686, 0.971] | |
| 0.8-0.9 | 30 | 0.854 | 0.967 | +0.113 | [0.833, 0.994] | |
| 0.9-1.0 | 179 | 0.965 | **0.994** | +0.029 | [0.969, 0.999] | **yes** |

Exactly one band is distinguishable from its promise: the top one, where Jev says 0.965
and delivers 0.994. Every middle-band gap, including that +0.223, falls inside its own
interval on six to thirty rows. Those are thin bins, not miscalibration.

This matters for how the result gets stated. Before the interval column existed, the
obvious write-up was "Jev is miscalibrated in the middle, well calibrated at the edges."
That claim was an artifact of bin size. The surviving claim is narrower and more useful:
**Jev's only measurable deviation is under-confidence**, which costs coverage and never
costs precision. That is the safe direction for a router to err, and it is why the top
band can carry an auto-approve decision.

## The second finding, which was not the one we went looking for

**153 of 400 gemini rows reported the probability of their own answer instead of the
probability of yes**, despite a prompt that spells out the difference and gives a worked
example. gpt-5-mini did it 10 times in 398.

`bakeoff.py` detects the drift (a "no" carrying p >= 0.5 is unambiguous) and flips it, and
the flip is counted rather than hidden. Without that flip, gemini's numbers would be
garbage in a way that still looks like a working pipeline: every row parses, the JSON is
valid, the types are right, and 38% of the probabilities mean the opposite of what the
column header says.

This is a failure mode the decisions endpoint cannot have. A `noul` returns one number
whose referent is fixed by the API, so there is no question for the model to misread. Any
verbalized-confidence pipeline needs this check; most do not have it.

## Caveats, because they bound what this supports

- One task, one domain. BoolQ is short-passage reading comprehension. Nothing here
  transfers to contract clauses or moderation queues without re-measuring, and stage 2
  re-measures rather than assuming.
- Thresholds are per-backend and per-task. A 0.9 from Jev on BoolQ is not a 0.9 from Jev
  on anything else.
- Two gpt-5-mini rows failed after four retries and are excluded (n=398).
- The chat arms use verbalized confidence, not logprob extraction. Logprob mapping is the
  stronger baseline and is not tested here; that is the most likely way these numbers
  understate the chat arms.
- Single run, temperature 0, no seed control on the providers' side.

## What this licenses

Building stage 2 on Jev, with the band still fitted per task rather than inherited from
this table.
