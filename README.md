# Review Budget

Your reviewers have four hours. Which cases should they open?

Review Budget takes a queue of cases an AI has already decided, a fixed number of reviewer
hours, and shows which cases are worth a human's time. Pointed at the cases most likely to
be wrong and most expensive if they are, the same four hours prevent about three times the
damage they prevent under a fixed confidence cutoff.

**Try it in three steps:**

1. Download this repository (green **Code** button, **Download ZIP**) and unzip it.
2. Double-click `demo.html`. It opens in your browser, no install, nothing leaves your machine.
3. Drag the hours dial. Switch the model. Read the limits panel.

---

## What you are looking at

Two lists, side by side, built from the same reviewer hours.

The left list is what a fixed cutoff sends you: every case the model was less than a set
confidence on. The right list is ranked by expected harm: how likely the model is wrong,
times what that mistake would cost.

The lists barely overlap. Each one says how many of its cases were actually wrong and how
much of the queue's damage opening them prevents. That gap is the whole argument.

## Where this came from

A quote goes out on a commercial job. Behind it sit drawings, equipment schedules,
specifications, and three revisions of each. Someone is supposed to reread all of it before
the quote is sent, and nobody has the hours.

An AI can flag the places that do not line up. But a flag is only worth a reviewer's time if
the number behind it means something. A model that says "80% sure" and is right 60% of the
time sends your reviewer to the wrong cases and lets the expensive mistake through.

So before anything gets built on a model's confidence, this repository measures it.

## What it gives you

- **One ranked list per policy**, so a reviewer can start at the top and stop when the
  hours run out.
- **A scoreboard on each list**: how many cases were really wrong, how much damage
  opening them prevents.
- **A limits panel on the screen**, with the same weight as the results: the costs are
  synthetic, the reviewer is assumed perfect, the task is one benchmark, the direction is
  measured and the size is not.
- **A model switch**, so you can watch the list change when the probabilities are worse.

The human still decides which cases to open.

## What it will not do

- **Gate on an unmeasured number.** A threshold that sounds high is not a threshold that
  has been checked. Thresholds here are recorded, never enforced, until a curve is fitted
  on labeled rows.
- **Dress the benchmark up as your data.** The cases are 400 public yes/no questions with
  an answer key. The answer key is the only reason a number exists here; a demo on your
  own documents could not be checked.
- **Make the call.** It ranks. Someone accountable opens the case.

## The numbers, plainly

| question | answer | where |
|---|---|---|
| Does the model's confidence mean what it says? | One of three models does: it can auto-decide 95% of the queue at 95% precision. The other two manage 36% and 0%. | [RESULTS.md](RESULTS.md) |
| What do four reviewer hours buy? | Spent on expected harm, they prevent about half the queue's damage. Spent on a fixed cutoff, about a sixth. 2,000 resamples, and expected harm wins in 96% of them. | [QUEUE.md](QUEUE.md) |
| What does the screen show? | One labeled cost draw for the lists, the full 2,000-draw average for the counters, and why those are kept apart. | [DEMO-SPEC.md](DEMO-SPEC.md) |

Every figure was written from script output, never by hand, and one command reproduces it:

```
python budget.py --replicates 2000
```

## Reproduce from scratch

```
python fetch_boolq.py --n 400 --seed 0
python bakeoff.py jev  --n 400
python bakeoff.py chat --n 400 --model google/gemini-2.5-flash-lite
python bakeoff.py chat --n 400 --model openai/gpt-5-mini
python score.py
python budget.py --replicates 2000
python export_demo.py --replicates 2000 && python build_demo.py
```

The three model runs need `OPENROUTER_API_KEY` and cost $0.27 in total. Everything after
`score.py` replays the recorded runs and spends nothing.

## Files

| file | what it does |
|---|---|
| `demo.html` | the screen: hours dial, model switch, two lists, limits panel |
| `budget.py` | spends a reviewer budget five ways over recorded probabilities |
| `bakeoff.py` | asks each model the 400 questions and records its probability |
| `score.py` | calibration table and reliability bins; fits nothing, gates nothing |
| `fetch_boolq.py` | pulls the labeled sample |
| `export_demo.py`, `build_demo.py` | turn the numbers and the template into `demo.html` |

## License

MIT
