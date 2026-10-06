#!/usr/bin/env python3
"""Claim-level check of the paraphrase arm: which source facts survive a rewrite?

    python quality_control/paraphrase/claim_coverage.py \
        --texts data/processed/paraphrase_texts.jsonl.gz \
        --model qwen/qwen3-235b-a22b --api-key-env OPENROUTER_API_KEY \
        --out data/experiments/paraphrase_claims

The number check beside this script cannot see a fact without a number or a name,
nor a fact whose parts survive in the wrong arrangement. This one extracts atomic
claims from the source and asks, claim by claim, whether each paraphrase still
states them. It follows experiments/atomic.py, the summary arm's instrument, with
three differences:

* Claims come from the same 50,000-character prefix the paraphraser rewrote, from
  up to 16 numbered paragraphs per judgment chosen at random. There is no
  relied-upon split: a paraphrase is meant to keep every fact.
* The verifier is told that a claim with its actors, objects, dates or figures
  rearranged is not supported. That is the failure a paraphrase can add.
* Two controls bound the verifier. The same claims are checked against the
  `original` text, which gives its false-negative rate. A sample of claims is
  rewritten with roles or attributes swapped and checked against `original`,
  which gives its rate of accepting a rearranged fact.

The extractor and verifier must not be the paraphraser, and the verifier never
sees the source. Every call is checkpointed, so an interrupted run resumes.
"""

import argparse
import collections
import gzip
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))

from atomic import (EXTRACT_TEMPLATE, number_claims, parse_claims,  # noqa: E402
                    parse_verdicts)

MAX_CHARS = 50000
LEVELS = ["light", "medium", "heavy"]
CONDITIONS = ["original"] + LEVELS
PARAPHRASER = "openai/gpt-5.6-sol"
ATTEMPTS = 4
MAX_TOKENS = 4000
BATCH = 40

VERIFY_TEMPLATE = """Below is the text of a court case, then a numbered list of factual claims.

TEXT:
{text}

CLAIMS:
{claims}

For each claim, decide whether the text states it or clearly implies it. Judge \
only against the text above. Do not use anything you know about the case: a claim \
that is true but absent from the text is NOT supported.

A claim is supported only if the text keeps the same relations: the same person or \
body does the same act, to the same object, with the same date, place, figure and \
outcome. If the text attributes the act to someone else, reverses who did what to \
whom, or attaches the date or figure to a different event, the claim is NOT \
supported, even when every word of it appears in the text.

Reply with ONLY a JSON array of objects, one per claim, in the same order, each \
{{"i": <claim number>, "supported": true or false}}. Return exactly {n} objects."""

SWAP_TEMPLATE = """Below is a numbered list of factual claims about a court case.

{claims}

Rewrite each claim so that it becomes false by rearranging its own parts: give the \
act to a different actor named in the claim or the case, reverse who did what to \
whom, or attach the date, place or figure to a different event. Keep the wording \
as close to the original as you can. Do not negate the claim and do not invent a \
new fact.

Reply with ONLY a JSON array of strings, one per claim, in the same order. Return \
exactly {n} strings."""

# Second look at each claim the original supports but a paraphrase does not: is the
# fact gone, or still there with its parts rearranged?
CLASSIFY_TEMPLATE = """Below is the text of a court case, then a numbered list of factual claims.

TEXT:
{text}

CLAIMS:
{claims}

For each claim, say how the text treats the fact it states. Judge only against the \
text above.

- "present": the text states this fact, with the same actor, act, object, date, \
place, figure and outcome.
- "altered": the text reports this event but changes one of those parts, for example \
another person does the act, the direction is reversed, or the date or figure differs \
or belongs to a different event.
- "absent": the text does not report this event at all.

Reply with ONLY a JSON array of objects, one per claim, in the same order, each \
{{"i": <claim number>, "label": "present" | "altered" | "absent"}}. Return exactly \
{n} objects."""
LABELS = ("present", "altered", "absent")


def as_array(reply):
    """Wrap a bare JSON object in brackets: asked about one claim, the model drops the array."""
    if not reply or reply.startswith("ERROR:"):
        return reply
    body = re.sub(r"^\s*```[a-z]*\s*|\s*```\s*$", "", reply.strip())
    return "[%s]" % body if body.startswith("{") and body.endswith("}") else body


def parse_labels(reply, n):
    """`n` labels from a classification reply, or None if any is missing or unknown."""
    reply = as_array(reply)
    if not reply or reply.startswith("ERROR:"):
        return None
    body = reply
    lo, hi = body.find("["), body.rfind("]")
    if lo == -1 or hi <= lo:
        return None
    try:
        items = json.loads(body[lo:hi + 1])
    except json.JSONDecodeError:
        return None
    by_index = {}
    for item in items:
        if isinstance(item, dict) and item.get("label") in LABELS:
            try:
                by_index[int(item.get("i"))] = item["label"]
            except (TypeError, ValueError):
                continue
    for base in (1, 0):
        if all(base + k in by_index for k in range(n)):
            return [by_index[base + k] for k in range(n)]
    return None


# Numbered paragraphs. Sources without line breaks glue the number to whatever came
# before: "... 2005.2. The", "PROCEDURE1. The", "26 December 201565. At".
PARA_RE = re.compile(r"(?:^|(?<=\n)|(?<=[.;:)\]”\"])|(?<=[A-Z]{2})|(?<=(?:19|20)\d\d))"
                     r"\s*(\d{1,3})\.\s+(?=[A-Z“\"(\[])")


def paragraphs(text):
    """Numbered paragraphs in reading order.

    Only a match that continues the sequence counts (the next number, or one past it
    when a marker is missing), which drops figures such as "2.5 sq. m".
    """
    text = text.replace(" ", " ")
    cuts, expect = [], None
    for m in PARA_RE.finditer(text):
        n = int(m.group(1))
        if (expect is None and n <= 3) or (expect is not None and n in (expect, expect + 1)):
            cuts.append((n, m.start()))
            expect = n + 1
    out = []
    for k, (n, start) in enumerate(cuts):
        end = cuts[k + 1][1] if k + 1 < len(cuts) else len(text)
        body = text[start:end].strip()
        if len(body) < 80:           # headings and stubs state nothing to check
            continue
        blocks = split_long(body)
        if len(blocks) == 1:
            out.append((str(n), body))
        else:                        # a missed marker merged paragraphs; keep units comparable
            out.extend(("%d.%d" % (n, j), b) for j, b in enumerate(blocks, 1))
    return out


def split_long(body, limit=4000, size=2500):
    """Cut an over-long paragraph into ~`size`-character blocks at sentence ends."""
    if len(body) <= limit:
        return [body]
    blocks, cur = [], ""
    for sentence in re.split(r"(?<=[.!?”])\s+(?=[A-Z“\"(])", body):
        if cur and len(cur) + len(sentence) > size:
            blocks.append(cur)
            cur = ""
        cur = (cur + " " + sentence).strip()
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:                 # tables and lists have no sentence ends at all
        while len(b) > limit:
            cut = b.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            out.append(b[:cut])
            b = b[cut:].strip()
        out.append(b)
    return out


class Checkpoint:
    """Append-only JSONL keyed by `key`; safe across threads and restarts."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.done = {}
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                if line.strip():
                    row = json.loads(line)
                    self.done[row["key"]] = row

    def get(self, key):
        return self.done.get(key)

    def put(self, row):
        with self.lock:
            with open(self.path, "a", encoding="utf-8", newline="\n") as h:
                h.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.done[row["key"]] = row


class Client:
    def __init__(self, model, key, base_url):
        self.model = model
        self.client = OpenAI(api_key=key, base_url=base_url)
        self.usage = collections.Counter()
        self.lock = threading.Lock()

    def complete(self, prompt):
        limit = MAX_TOKENS
        for attempt in range(ATTEMPTS):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model, messages=[{"role": "user", "content": prompt}],
                    temperature=0, max_completion_tokens=limit)
                with self.lock:
                    if resp.usage:
                        self.usage["prompt"] += resp.usage.prompt_tokens or 0
                        self.usage["completion"] += resp.usage.completion_tokens or 0
                    self.usage["calls"] += 1
                content = (resp.choices[0].message.content or "").strip()
                if content:
                    return content
                limit *= 2
            except Exception as exc:                  # noqa: BLE001
                if attempt == ATTEMPTS - 1:
                    return "ERROR: %s" % exc
                time.sleep(min(2 ** attempt, 30) + random.uniform(0, 1))
        return "ERROR: empty after %d attempts" % ATTEMPTS


def extract(client, ckpt, item_id, source, per_judgment, max_claims):
    paras = paragraphs(source)
    rng = random.Random("paraphrase-claims|%s" % item_id)
    order = {number: k for k, (number, _) in enumerate(paras)}
    chosen = sorted(rng.sample(paras, min(per_judgment, len(paras))), key=lambda p: order[p[0]])
    claims = []
    for number, body in chosen:
        key = "extract|%s|%s" % (item_id, number)
        row = ckpt.get(key)
        if row is None:
            reply = client.complete(EXTRACT_TEMPLATE.format(paragraph=body, max_claims=max_claims))
            row = {"key": key, "item_id": item_id, "paragraph": number,
                   "position": round(source.find(body[:60]) / max(1, len(source)), 3),
                   "claims": parse_claims(reply)[:max_claims], "error": reply.startswith("ERROR:")}
            ckpt.put(row)
        for c in row["claims"]:
            claims.append({"claim": c, "paragraph": number, "position": row["position"]})
    return claims, len(paras)


def verify(client, ckpt, key_prefix, text, claims):
    """Support decisions for `claims` against `text`, or None for a failed batch."""
    out = []
    for start in range(0, len(claims), BATCH):
        chunk = claims[start:start + BATCH]
        key = "%s|%d" % (key_prefix, start)
        row = ckpt.get(key)
        if row is None or row["verdicts"] is None:
            verdicts = None
            for _ in range(2):        # a short or malformed array is retried, never padded
                reply = client.complete(VERIFY_TEMPLATE.format(
                    text=text, claims=number_claims(chunk), n=len(chunk)))
                verdicts = parse_verdicts(as_array(reply), len(chunk))
                if verdicts is not None:
                    break
            row = {"key": key, "verdicts": verdicts}
            ckpt.put(row)
        out.extend(row["verdicts"] if row["verdicts"] is not None else [None] * len(chunk))
    return out


def classify(client, ckpt, key_prefix, text, claims):
    out = []
    for start in range(0, len(claims), BATCH):
        chunk = claims[start:start + BATCH]
        key = "%s|%d" % (key_prefix, start)
        row = ckpt.get(key)
        if row is None or row["labels"] is None:
            labels = None
            for _ in range(2):
                reply = client.complete(CLASSIFY_TEMPLATE.format(
                    text=text, claims=number_claims(chunk), n=len(chunk)))
                labels = parse_labels(reply, len(chunk))
                if labels is not None:
                    break
            row = {"key": key, "labels": labels}
            ckpt.put(row)
        out.extend(row["labels"] if row["labels"] is not None else [None] * len(chunk))
    return out


def swap(client, ckpt, item_id, claims):
    key = "swap|%s" % item_id
    row = ckpt.get(key)
    if row is None or row["swapped"] is None:
        swapped = None
        for _ in range(2):            # a list of the wrong length is retried, never aligned by guess
            got = parse_claims(client.complete(SWAP_TEMPLATE.format(
                claims=number_claims(claims), n=len(claims))))
            if len(got) == len(claims):
                swapped = got
                break
        row = {"key": key, "swapped": swapped}
        ckpt.put(row)
    return row["swapped"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--texts", default="data/processed/paraphrase_texts.jsonl.gz")
    p.add_argument("--model", default="qwen/qwen3-235b-a22b")
    p.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    p.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, help="pilot on N judgments")
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--per-judgment", type=int, default=16, help="paragraphs per judgment")
    p.add_argument("--max-claims", type=int, default=6, help="claims per paragraph")
    p.add_argument("--swap-judgments", type=int, default=60, help="judgments in the swap control")
    p.add_argument("--swap-claims", type=int, default=5, help="claims per judgment in the swap control")
    a = p.parse_args()

    if a.model.split("/")[-1].startswith(PARAPHRASER.split("/")[-1]):
        sys.exit("The verifier must not be the paraphraser (%s)." % PARAPHRASER)
    key = os.environ.get(a.api_key_env)
    if not key:
        sys.exit("Set %s." % a.api_key_env)

    texts = collections.defaultdict(dict)
    for line in gzip.open(a.texts, "rt", encoding="utf-8"):
        r = json.loads(line)
        texts[(r["item_id"], r["article"])][r["condition"]] = r["text"]
    by_item = collections.defaultdict(list)
    for item_id, article in sorted(texts):
        by_item[item_id].append(article)
    items = sorted(by_item)
    if a.limit:
        items = random.Random("pilot").sample(items, min(a.limit, len(items)))

    os.makedirs(a.out, exist_ok=True)
    config = {"model": a.model, "per_judgment": a.per_judgment, "max_claims": a.max_claims,
              "batch": BATCH, "max_source_chars": MAX_CHARS, "texts": os.path.basename(a.texts),
              "protocol": "paraphrase-claims-v1"}
    cfg_path = os.path.join(a.out, "config.json")
    if os.path.exists(cfg_path) and json.load(open(cfg_path)) != config:
        sys.exit("%s was made with different settings; use a fresh --out." % a.out)
    json.dump(config, open(cfg_path, "w"), indent=2)

    client = Client(a.model, key, a.base_url)
    ckpt = Checkpoint(os.path.join(a.out, "calls.jsonl"))
    swap_items = set(random.Random("swap").sample(items, min(a.swap_judgments, len(items))))

    def one(item_id):
        articles = by_item[item_id]
        sources = {texts[(item_id, art)]["original"][:MAX_CHARS] for art in articles}
        if len(sources) != 1:
            raise ValueError("%s: targets disagree on the original text" % item_id)
        source = sources.pop()
        claims, n_paras = extract(client, ckpt, item_id, source, a.per_judgment, a.max_claims)
        rows = []
        if not claims:
            return rows, None, n_paras
        for art in articles:
            found = {}
            for cond in CONDITIONS:
                text = texts[(item_id, art)][cond][:MAX_CHARS] if cond == "original" else texts[(item_id, art)][cond]
                found[cond] = verify(client, ckpt, "verify|%s|%s|%s" % (item_id, art, cond), text, claims)
            for cond in CONDITIONS:
                labels = [None] * len(claims)
                if cond != "original":
                    lost = [k for k in range(len(claims))
                            if found["original"][k] and found[cond][k] is False]
                    if lost:
                        got = classify(client, ckpt, "classify|%s|%s|%s" % (item_id, art, cond),
                                       texts[(item_id, art)][cond], [claims[k] for k in lost])
                        for k, lab in zip(lost, got):
                            labels[k] = lab
                for c, v, lab in zip(claims, found[cond], labels):
                    rows.append({"item_id": item_id, "article": art, "condition": cond,
                                 "paragraph": c["paragraph"], "position": c["position"],
                                 "claim": c["claim"], "supported": v, "loss_label": lab})
        control = None
        if item_id in swap_items:
            pick = random.Random("swap|%s" % item_id).sample(claims, min(a.swap_claims, len(claims)))
            swapped = swap(client, ckpt, item_id, [c["claim"] for c in pick])
            if swapped:
                verdicts = verify(client, ckpt, "swapverify|%s" % item_id, source,
                                  [{"claim": s} for s in swapped])
                control = [{"item_id": item_id, "claim": c["claim"], "swapped": s, "supported": v}
                           for c, s, v in zip(pick, swapped, verdicts)]
        return rows, control, n_paras

    rows, controls, failures, no_paras = [], [], [], []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, i): i for i in items}
        for k, f in enumerate(as_completed(futs), 1):
            item_id = futs[f]
            try:
                r, c, n = f.result()
            except Exception as exc:                  # noqa: BLE001
                failures.append({"item_id": item_id, "error": str(exc)})
                continue
            if n == 0:
                no_paras.append(item_id)
            rows.extend(r)
            controls.extend(c or [])
            if k % 25 == 0 or k == len(items):
                print("%d/%d judgments, %d calls, %d+%d tokens" % (
                    k, len(items), client.usage["calls"], client.usage["prompt"],
                    client.usage["completion"]), flush=True)

    with open(os.path.join(a.out, "claims.jsonl"), "w", encoding="utf-8", newline="\n") as h:
        for r in rows:
            h.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(a.out, "swap_control.jsonl"), "w", encoding="utf-8", newline="\n") as h:
        for r in controls:
            h.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump({"judgments": len(items), "failures": failures, "no_numbered_paragraphs": no_paras,
               "usage_this_run": dict(client.usage)},
              open(os.path.join(a.out, "run.json"), "w"), indent=2)
    print("rows %d, swap controls %d, failures %d, judgments without numbered paragraphs %d" % (
        len(rows), len(controls), len(failures), len(no_paras)))


if __name__ == "__main__":
    main()
