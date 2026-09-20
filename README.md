# Review Budget

A router is a classifier you are allowed to trust with a decision. The difference is a
measured calibration curve, and this repo is about the measurement, not the classifier.

## The argument

Typed output is commodity: 391 of 447 models on OpenRouter do structured outputs. The
scarce property is a probability that means what it says. That is what lets a workflow
**route** (auto-approve above the band, human reads the band, reject below) instead of
merely **label**. A confidence number you have not measured cannot carry a decision, no
matter how confident it sounds, so the first artifact in this repo is a bake-off that
tries to falsify the calibration claim of the model the router is built on.

TypeSafe's Jev returns a native per-answer probability from OpenRouter's
`/api/alpha/decisions` endpoint. Chat models can be asked for a probability, or have one
read out of their logprobs. The question this repo answers with numbers: does the native
one actually track reality better, and by how much, on a task with gold labels?

## Stage 1: the judge bake-off

**Task.** BoolQ validation (Google, public, gold yes/no labels). 400 rows sampled with a
fixed seed. Gold labels mean calibration is measurable without inventing any labels of our
own, which is the point: a calibration study on labels the author produced is a circle.

**Arms.** All three answer the same question over the same passage and emit one
probability of yes.

| arm | how the probability is produced |
|---|---|
| `typesafe/jev-1.13` | native `noul`, the decisions endpoint's own probability |
| `openai/gpt-5-mini` | verbalized probability in structured JSON |
| `google/gemini-2.5-flash-lite` | verbalized probability in structured JSON |

`qwen/qwen3.7-flash` was the first baseline and was dropped: it is listed in
`/api/v1/models` but 404s on `chat/completions`. Same class of trap as Jev's, in the other
direction. The model list is not a routing table.

**Metrics.** Accuracy is reported only so a calibration win is not mistaken for a
capability win. The columns that decide whether a band is safe to route on:

- **ECE** (expected calibration error): the n-weighted gap between promise and delivery.
- **Brier**: accuracy and calibration in one number.
- **AUROC**: rank quality, independent of calibration. A model can rank well and still lie
  about its probabilities; this column separates those.
- **coverage@95 / @99**: the fraction of traffic that can be auto-decided while holding
  that precision on the auto-decided slice. This is the economic column, the one that says
  how many human reviews you buy back.

**Results.** See [RESULTS.md](RESULTS.md): Jev leads every column, and the 59-point coverage gap at equal-ish accuracy is the finding. Written from `score.py` output, never by hand.

## Stage 2: what does a reviewer hour buy?

The calibration result only matters if it converts into something a buyer counts. Stage 2
takes the same 398 cases, gives a reviewer a fixed budget of hours, and asks which cases
they should open. Ranking by expected harm, P(wrong) x cost, beats a fixed confidence
cutoff by 2x the budget on Jev's probabilities, and the same policy on a weaker arm's
probabilities buys less, which is the calibration argument stated in hours instead of ECE.

See [QUEUE.md](QUEUE.md). It replays `runs/*.jsonl` and spends nothing.

## What this repo will not do

Gate on an unmeasured number. The production classifier this grew out of runs its
0.8/0.5 bands **recorded but not gating** until a curve is fitted on labeled rows, and the
same rule binds here. A demo that quietly thresholds at 0.8 because 0.8 sounds high is the
exact failure the demo exists to teach against.

## Reproduce

```
python fetch_boolq.py --n 400 --seed 0
python bakeoff.py jev  --n 400
python bakeoff.py chat --n 400 --model google/gemini-2.5-flash-lite
python bakeoff.py chat --n 400 --model openai/gpt-5-mini
python score.py
```

Needs `OPENROUTER_API_KEY`. Total spend for the three arms was $0.265, nearly all of it gpt-5-mini. Runs are
resumable: a dropped connection leaves a partial file and re-running appends the rest.

## Files

| file | what it does |
|---|---|
| `fetch_boolq.py` | pulls the labeled sample from the HF datasets-server |
| `bakeoff.py` | runs one arm, one row at a time, appending JSONL |
| `score.py` | reports the table and the reliability bins; fits nothing, gates nothing |
| `budget.py` | stage 2: spends a reviewer budget five ways over the recorded probabilities |
