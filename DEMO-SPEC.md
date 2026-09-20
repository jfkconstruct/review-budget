# Stage 3: the demo screen

Opened 2026-09-19. Numbers come from `budget.py` and are already computed; this is a
rendering job, not a research job.

## Outcome canvas

- **OUTCOME:** a hiring manager or buyer understands in under 30 seconds that the same
  reviewer hours, pointed differently, prevent about three times the damage.
- **SUCCESS SIGNAL:** they drag the hours dial unprompted, then read the limits panel.
- **USER + CONTEXT:** applied-AI hiring manager or ops buyer, skimming on a laptop from a
  link in an application or a post, 60 seconds of attention, no setup, no login.
- **SUBPROBLEM 1 (decision: which cases do I open today?):** show two concrete lists side
  by side, not a chart of aggregates. The lists barely overlap and that is the argument.
- **SUBPROBLEM 2 (decision: do I believe this number?):** the limits panel is primary
  content, not a footnote. Synthetic costs, perfect reviewer, one task, direction measured
  and magnitude not.
- **SUBPROBLEM 3 (decision: does it depend on the model?):** an arm switcher (Jev /
  gpt-5-mini / gemini) that visibly rewrites the list, so calibration is watched rather
  than asserted.
- **CONSTRAINTS:** canned scenario is the front door, ruled 2026-09-19; upload is a second
  tab labeled unverified and is NOT built in this pass. Static page, no backend, numbers
  precomputed to JSON. Must work on a phone.
- **UNKNOWNS:** whether the scenario label (insurance claims) reads as honest given the
  underlying rows are BoolQ questions. Leaning toward labeling it plainly as a graded
  benchmark rather than dressing it as claims data.
- **DECISION:** build the canned two-column budget demo, Jev-first, limits panel on screen.
- **TEST:** a reader who has never seen the project can say what changed and what it does
  not prove, without asking a question.

## Ruled before the build

- **Front door is the canned scenario, not the upload box** (ruled 2026-09-19). On a
  stranger's documents there are no correct answers to compare against, so an upload
  demo outputs a confident-looking ranked list nobody can verify. That is the failure
  this project argues against, so leading with it would demonstrate the disease while
  selling the cure. The gold-labeled test is the only reason the 3x number exists.
- **The limits panel is the differentiator**, not the 3x. A candidate who volunteers the
  limits of his own number is rarer than one with a big number.
- Publishing guards bind: verify every claim before it goes on the screen, state
  assumptions and gaps on the screen itself.

## Style

Calm editorial: rule-based layout, colored status dots, clamp typography, no boxed
cards (the `aurelius-workflow` module, picked 2026-09-19). The two candidate lists are rule-separated sections rather than boxed cards,
and the limits panel gets the same visual weight as the counters, which this module's
flat hierarchy makes easy rather than fighting.

## Built 2026-09-19

`demo.template.html` (hand-authored) + `demo-data.json` (precomputed) joined by
`build_demo.py` into `demo.html`, one 92 KB file with no network calls, so it opens from
a `file://` path, a bucket, or a static host.

- `export_demo.py --replicates 2000` reuses budget.py's own functions, so the screen and
  the write-up cannot drift: every counter on the page reproduces QUEUE.md cell for cell
  (50.9 / 37.8 / 16.4 / 100.0, 82 reviews to match, 96% and 69% sign tests).
- **Scenario framing RULED, closing the UNKNOWN:** the queue is labeled plainly as a
  graded benchmark, never dressed as insurance claims. The hero says the answer key is
  the only reason a number exists here and that a demo on the reader's own documents
  could not be checked. Dressing benchmark rows as claims data would have been the
  unverifiable-ranked-list failure this project sells against, in the copy instead of
  the code.
- **Two numbers on one screen, kept apart.** The counters are the 2000-draw bootstrap.
  The two lists are ONE cost draw (seed 0), because an average of 2000 draws is not a
  list anyone can read; the page labels the draw as a draw, in the overlap line and
  again in the limits panel. Stage 2's wrong turn was reporting a single fixed draw AS
  the measurement, which is a different act from showing one and saying so.
- Each list carries its own scoreboard (`6 of these 40 were actually wrong, and opening
  them averts 48% of this draw's damage` against the cutoff's `4` and `17%`). Without it
  a reader sees eight rows mostly marked "answered right" and reads the policy as bad;
  with it the two columns are comparable at a glance, which is what SUBPROBLEM 1 needs.
- Third control beyond the spec's dial and arm switcher: **cost shape** (uniform /
  lognormal / adversarial). It is the honesty lever, not a garnish. Under `uniform` the
  page says expected harm and confidence-only are the same policy by construction rather
  than printing a fake gap.
- Verified: the static accessibility scan returns nothing; no console errors; no
  horizontal scroll at 390px; steppers disable at both bounds; arm switch visibly rewrites
  both lists. The static CSS-usage scan reports four items, all waived as runtime-only:
  `--dot-green`, `.lead-row .row-name/.row-num` and `.list-score strong` are applied by
  the render function, which a static parse cannot see. The two genuinely unused tokens
  it found were deleted.
- Reconciled in the same pass: QUEUE.md's one-hour sentence quoted a 500-replicate run
  while its tables were 2000. Now 23.4% / 1.0%, so one command reproduces the whole doc.

## Renamed 2026-09-19

- The project was `jev-router` until the packaging pass. A vendor's model name in the
  title reads as an ad and dates the work; the argument is about reviewer hours, so the
  name is Review Budget.
- The stage 2 script was `queue.py`, which shadowed the stdlib `queue` module for
  anything run from this directory (a playwright script run from here died on it). It
  is `budget.py` now.
