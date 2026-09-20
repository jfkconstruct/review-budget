"""Judge bake-off: Jev's native calibrated probability vs a chat model's stated one.

    python projects/review-budget/bakeoff.py jev   --n 50
    python projects/review-budget/bakeoff.py chat  --n 50 --model <openrouter-id>
    python projects/review-budget/bakeoff.py score

The claim under test is the one the whole router rests on: that Jev's probability means
what it says. BoolQ carries gold labels, so this is a MEASUREMENT, not a demo. If Jev is
badly calibrated here, that is the finding and it ships as the finding.

Both arms answer the same yes/no question over the same passage and emit one probability
of yes. Nothing is gated on it; `score` fits the reliability curve afterwards.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The decisions endpoint is not chat/completions: decisions models do not appear in
# /api/v1/models and 400 on the chat surface, so the client is its own few lines here.
DECISIONS_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
DECISIONS_MODEL = "typesafe/jev-1.13"
API_KEY_ENV = "OPENROUTER_API_KEY"


class DecisionsError(RuntimeError):
    pass


def decisions_ask(state, questions, model=DECISIONS_MODEL, timeout=120, retries=3):
    """One decisions call. Retries a timeout, a 429, or a 5xx; a 400 is a malformed
    request and would be malformed again, so it raises at once."""
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise DecisionsError(f"{API_KEY_ENV} is not set")
    payload = json.dumps({"model": model, "state": state, "questions": questions}).encode("utf-8")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    last = None
    for attempt in range(retries):
        request = urllib.request.Request(DECISIONS_ENDPOINT, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            if exc.code < 500 and exc.code != 429:
                raise DecisionsError(f"decisions endpoint returned {exc.code}: {detail}") from exc
            last = DecisionsError(f"decisions endpoint returned {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = DecisionsError(f"decisions call failed: {exc}")
        if attempt < retries - 1:
            time.sleep(2.0 * (attempt + 1))
    raise last


DATA = HERE / "data" / "boolq-dev.jsonl"
RUNS = HERE / "runs"
CHAT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
QID = "answer"

CHAT_PROMPT = (
    "Answer the yes/no question using only the passage.\n"
    # Braces are doubled because this template goes through str.format: a single brace
    # here makes format read the JSON example as a field name and every row dies KeyError.
    "Reply with JSON only: {{\"answer\": \"yes\"|\"no\", \"probability\": <0.0-1.0>}}\n"
    "`probability` is your probability that the correct answer is YES, not your "
    "probability that you are right. Be calibrated: over many such answers, of the "
    "cases you call 0.7, about 70 percent should be yes.\n\n"
    "PASSAGE:\n{passage}\n\nQUESTION: {question}"
)


def rows(n):
    with DATA.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= n:
                return
            yield json.loads(line)


def ask_jev(row):
    """One noul per row. `noul` IS the probability of yes, so no decoding is needed."""
    body = decisions_ask(
        row["passage"],
        {QID: {"type": "noul", "instructions": row["question"] + "?"}},
    )
    answer = body["answers"][QID]
    return float(answer["noul"]), dict(body.get("usage") or {})


def ask_chat(row, model):
    key = os.environ[API_KEY_ENV]
    payload = json.dumps({
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": CHAT_PROMPT.format(
            passage=row["passage"], question=row["question"])}],
    }).encode("utf-8")
    request = urllib.request.Request(
        CHAT_ENDPOINT, data=payload, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    text = body["choices"][0]["message"]["content"]
    parsed = json.loads(text)
    p = float(parsed["probability"])
    # The prompt asks for P(yes) directly, but models drift into reporting P(their answer).
    # A "no" carrying p>=0.5 is that drift, and flipping it is the only reading that keeps
    # the two arms on one scale. Counted, because the count is itself a finding.
    flipped = str(parsed.get("answer", "")).strip().lower() == "no" and p >= 0.5
    if flipped:
        p = 1.0 - p
    return p, flipped, dict(body.get("usage") or {})


def attempt(arm, row, model, tries=4):
    """Per-row retry. A 400-row sequential sweep reliably meets a dropped connection, and
    RemoteDisconnected is an OSError that urllib does NOT wrap in URLError, so catching
    URLError alone silently ends the run early with a partial file that still looks fine."""
    last = None
    for i in range(tries):
        try:
            if arm == "jev":
                p, usage = ask_jev(row)
                return p, False, usage
            return ask_chat(row, model)
        except (KeyError, ValueError, OSError, DecisionsError) as exc:
            last = exc
            time.sleep(1.5 * (i + 1))
    raise last


def run(arm, n, model):
    RUNS.mkdir(exist_ok=True)
    out = RUNS / f"{arm}-{model.replace('/', '_') if model else DECISIONS_MODEL.replace('/', '_')}.jsonl"
    # Resume rather than restart: a partial file is the common case, and re-paying for
    # rows already answered is how a cheap sweep turns into an expensive one.
    done = set()
    if out.exists():
        done = {json.loads(line)["id"] for line in out.read_text(encoding="utf-8").splitlines() if line.strip()}
        print(f"resuming, {len(done)} rows already answered")
    flips = 0
    with out.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(rows(n), 1):
            if row["id"] in done:
                continue
            try:
                p, flipped, usage = attempt(arm, row, model)
            except (KeyError, ValueError, OSError, DecisionsError) as exc:
                print(f"  row {row['id']} failed: {exc}", file=sys.stderr)
                continue
            flips += flipped
            fh.write(json.dumps({"id": row["id"], "gold": row["gold"],
                                 "p_yes": round(p, 6), "flipped": flipped,
                                 "usage": usage}) + "\n")
            fh.flush()
            if i % 10 == 0:
                print(f"  {i} done", flush=True)
            time.sleep(0.05)
    print(f"wrote {out}" + (f"  (P(answer)->P(yes) flips: {flips})" if arm == "chat" else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=["jev", "chat"])
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--model", default=None, help="OpenRouter id for the chat arm")
    args = ap.parse_args()
    if args.arm == "chat" and not args.model:
        ap.error("--model is required for the chat arm")
    run(args.arm, args.n, args.model)


if __name__ == "__main__":
    main()
