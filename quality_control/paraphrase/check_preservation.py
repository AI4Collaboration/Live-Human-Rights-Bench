"""Deterministic fact-preservation check for the paraphrase arm.

Each paraphrase was produced from text[:50000] of the original record, chunked on
line breaks, so every comparison is against that same 50,000-character prefix.
No model calls: numbers, application numbers and proper names are extracted with
regular expressions from both sides and compared as multisets.

Usage (from the repository root):
    python quality_control/paraphrase/check_preservation.py \
        data/processed/paraphrase_texts.jsonl.gz quality_control/paraphrase
"""
import collections
import csv
import gzip
import json
import os
import re
import statistics
import sys
import unicodedata

MAX_CHARS = 50000
LEVELS = ["light", "medium", "heavy"]

WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
WORD_RE = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
MON = "(" + "|".join(MONTHS) + ")"
DATE_NUM_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
DATE_DMY_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + MON + r",?\s+(\d{4})\b", re.I)
DATE_MDY_RE = re.compile(r"\b" + MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)
APP_RE = re.compile(r"(?<![\d/.])\d{1,6}/\d{2}(?![\d/])")
# Paragraph numbers: "2007. 2. On ..." in the source, "\n\n2. On ..." in paraphrases.
PARA_RE = re.compile(r"(?:^|(?<=[.;:)\]”\"]\s)|(?<=\n))\s*\d{1,4}\.(?=\s+[A-Z“\"(\[])", re.M)
FOOT_RE = re.compile(r"\[\d{1,3}\]")
SEP_RE = re.compile(r"(?<=\d)[.,\u00a0\u202f\u2009](?=\d{3}\b)")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
CAP_RE = re.compile(r"\b[^\W\d_][\w'\-]{2,}\b")
MARKERS = re.compile(r"(?i)\b(here is|here's|rewritten text|i can't|i cannot|i'm sorry|as an ai)\b")
# Judgment boilerplate the paraphraser legitimately rewords ("Delivers the following judgment").
BOILERPLATE = set("Delivers Having Court Section State States Rules Rule Act Everyone Every This "
                  "First Others Protection Rights Fundamental Procedure General Foreign".split())
# Above this, one chunk's paraphrase can exceed the generator's 4,000-token output cap.
OVERSIZED_CHUNK = 12000
# Reported for reference only: o200k_base approximates the generator's tokenizer, and
# capped outputs measure 3,700-3,960 tokens, overlapping complete ones.
try:
    import tiktoken
    ENC = tiktoken.get_encoding("o200k_base")
except Exception:  # optional: the output_tokens_o200k column is left empty without it
    ENC = None
SENTENCE_END = set(".!?…”\"')]:;»")
VERDICT = re.compile(r"(?i)\b(violation|violated|breach(?:ed)?|no violation)\b")


# Sources without line breaks glue words to numbers: "STRASBOURG17 October 2019",
# "5 June 2013under Rule 81", "in October 2002.13. On ...", "Ukraine 198333. Article ...".
GLUED_WORD_RE = re.compile(r"(?<=\d)(?!(?:st|nd|rd|th)\b)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)")
GLUED_PARA_RE = re.compile(r"\b((?:18|19|20)\d\d)\.?\d{1,3}\.(?=\s+[A-Z“\"(\[])")


def norm(text):
    # Glued paragraph numbers first, while "EUR 200,000." still has its separator.
    text = GLUED_PARA_RE.sub(r"\1. ", text)
    text = SEP_RE.sub("", text)  # before NFKC, which turns no-break spaces into plain ones
    text = unicodedata.normalize("NFKC", text)
    return GLUED_WORD_RE.sub(" ", text)


def dates(text):
    """Pull dates out as canonical Y-M-D tokens, whatever format each side uses."""
    found = collections.Counter()

    def take(y, m, d):
        if 1 <= m <= 12 and 1 <= d <= 31:
            found[f"{int(y)}-{m:02d}-{d:02d}"] += 1
            return " "
        return None

    text = DATE_NUM_RE.sub(lambda g: take(g[3], int(g[2]), int(g[1])) or g[0], text)
    text = DATE_DMY_RE.sub(lambda g: take(g[3], MONTHS[g[2].lower()], int(g[1])) or g[0], text)
    text = DATE_MDY_RE.sub(lambda g: take(g[3], MONTHS[g[1].lower()], int(g[2])) or g[0], text)
    return found, text


def numbers(text):
    """Return (application numbers, dates, salient numbers, all numbers) as Counters."""
    text = norm(text)
    found_dates, text = dates(text)
    apps = collections.Counter(APP_RE.findall(text))
    text = APP_RE.sub(" ", text)
    text = PARA_RE.sub(" ", text)
    text = FOOT_RE.sub(" ", text)
    text = WORD_RE.sub(lambda m: WORDS[m.group(1).lower()], text)
    allnum = collections.Counter(n.rstrip(".") for n in NUM_RE.findall(text))
    salient = collections.Counter({n: c for n, c in allnum.items()
                                   if len(n.replace(".", "")) >= 3 or "." in n})
    return apps, found_dates, salient, allnum


def proper_names(text):
    """Capitalised tokens never seen lower-case in the same text, sentence starts excluded."""
    text = unicodedata.normalize("NFKC", text)
    lower = {t.lower() for t in CAP_RE.findall(text) if t[0].islower()}
    out = collections.Counter()
    for m in CAP_RE.finditer(text):
        tok = m.group(0)
        if not tok[0].isupper() or tok.isupper() or tok.lower() in lower or tok in BOILERPLATE:
            continue
        before = text[max(0, m.start() - 3):m.start()]
        if not before.strip() or re.search(r"[.!?:]\s*$", before):
            continue
        out[tok] += 1
    return out


def chunks(text, size=3000):
    """Same split as experiments/paraphrase_run.py: on line breaks only."""
    parts, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) > size and cur:
            parts.append(cur)
            cur = ""
        cur += para + "\n"
    if cur.strip():
        parts.append(cur)
    return parts


def anchors(text):
    apps, found_dates, salient, _ = numbers(text)
    return set(apps) | set(found_dates) | set(salient)


def chunk_tails(parts):
    """Anchors found only in the last 30% of each oversized chunk.

    A chunk whose output hit the token cap loses its end, so these anchors go
    missing while the rest of the text keeps its own.
    """
    tails = []
    for i, c in enumerate(parts):
        if len(c) <= OVERSIZED_CHUNK:
            continue
        cut = int(len(c) * 0.7)
        rest = "".join(parts[:i]) + c[:cut] + "".join(parts[i + 1:])
        tails.append(anchors(c[cut:]) - anchors(rest))
    return tails


def recall(src, dst):
    total = sum(src.values())
    if not total:
        return None
    return sum(min(c, dst[k]) for k, c in src.items()) / total


def set_recall(src, dst):
    return None if not src else len(set(src) & set(dst)) / len(src)


def main(path, outdir):
    os.makedirs(outdir, exist_ok=True)
    rows = [json.loads(line) for line in gzip.open(path, "rt", encoding="utf-8")]
    by = collections.defaultdict(dict)
    for r in rows:
        by[(r["item_id"], r["article"])][r["condition"]] = r["text"]
    incomplete = [k for k, v in by.items() if set(v) != {"original", *LEVELS}]

    per_row = []
    examples = collections.defaultdict(list)
    for (item, art), arms in sorted(by.items()):
        if (item, art) in incomplete:
            continue
        src = arms["original"][:MAX_CHARS]
        s_apps, s_dates, s_sal, s_all = numbers(src)
        s_names = proper_names(src)
        s_verdict = len(VERDICT.findall(src))
        parts = chunks(src)
        max_chunk = max(len(c) for c in parts)
        tails = [t for t in chunk_tails(parts) if len(t) >= 3]
        for lvl in LEVELS:
            dst = arms[lvl]
            d_apps, d_dates, d_sal, d_all = numbers(dst)
            d_anchors = anchors(dst) if tails else set()
            tail_recall = min((len(t & d_anchors) / len(t) for t in tails), default=None)
            tokens = len(ENC.encode(dst)) if ENC and len(parts) == 1 else None
            d_names = proper_names(dst)
            lost = sorted(set(s_sal) - set(d_sal)) + sorted(set(s_dates) - set(d_dates))
            added = sorted(set(d_sal) - set(s_all)) + sorted(set(d_dates) - set(s_dates))
            row = {
                "item_id": item, "article": art, "condition": lvl,
                "len_ratio": round(len(dst) / max(1, len(src)), 4),
                "app_no_recall": set_recall(s_apps, d_apps),
                "date_recall": recall(s_dates, d_dates),
                "date_set_recall": set_recall(s_dates, d_dates),
                "salient_num_recall": recall(s_sal, d_sal),
                "salient_num_set_recall": set_recall(s_sal, d_sal),
                "all_num_recall": recall(s_all, d_all),
                "name_set_recall": set_recall(s_names, d_names),
                "salient_lost": " ".join(lost[:20]),
                "salient_added": " ".join(added[:20]),
                "n_salient_added": len(added),
                "verdict_terms_src": s_verdict,
                "verdict_terms_dst": len(VERDICT.findall(dst)),
                "preamble_or_refusal": bool(MARKERS.search(dst[:400]) or MARKERS.search(dst[-400:])),
                "truncated_source": len(arms["original"]) > MAX_CHARS,
                "max_input_chunk_chars": max_chunk,
                "n_input_chunks": len(parts),
                "chunk_tail_recall": None if tail_recall is None else round(tail_recall, 4),
                "output_tokens_o200k": tokens,
                "tail_lost": tail_recall is not None and tail_recall < 0.5,
                # One oversized chunk in, output stopping mid-sentence: cut at the cap. A source
                # cut mid-sentence at MAX_CHARS ends mid-sentence too, faithfully, so it is excluded.
                "end_cut": (len(parts) == 1 and max_chunk > OVERSIZED_CHUNK
                            and src.rstrip()[-1:] in SENTENCE_END
                            and dst.rstrip()[-1:] not in SENTENCE_END),
            }
            per_row.append(row)
            if lost and len(examples[lvl]) < 15:
                examples[lvl].append({"item_id": item, "article": art, "lost": lost[:10], "added": added[:10]})

    with open(os.path.join(outdir, "per_row.csv"), "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(per_row[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(per_row)

    def stats(vals):
        vals = [v for v in vals if v is not None]
        return {"n": len(vals), "mean": round(statistics.mean(vals), 4),
                "median": round(statistics.median(vals), 4),
                "share_perfect": round(sum(v >= 1.0 for v in vals) / len(vals), 4)}

    summary = {"input": os.path.basename(path), "rows": len(rows), "targets": len(by),
               "incomplete_targets": len(incomplete), "max_source_chars": MAX_CHARS, "by_condition": {}}
    for lvl in LEVELS:
        rs = [r for r in per_row if r["condition"] == lvl]
        summary["by_condition"][lvl] = {
            "len_ratio_median": round(statistics.median(r["len_ratio"] for r in rs), 4),
            "application_numbers": stats(r["app_no_recall"] for r in rs),
            "dates_distinct": stats(r["date_set_recall"] for r in rs),
            "salient_numbers": stats(r["salient_num_recall"] for r in rs),
            "salient_numbers_distinct": stats(r["salient_num_set_recall"] for r in rs),
            "all_numbers": stats(r["all_num_recall"] for r in rs),
            "proper_names_distinct": stats(r["name_set_recall"] for r in rs),
            "share_with_added_salient_number": round(sum(r["n_salient_added"] > 0 for r in rs) / len(rs), 4),
            "share_new_verdict_terms": round(sum(r["verdict_terms_dst"] > r["verdict_terms_src"] for r in rs) / len(rs), 4),
            "oversized_chunk_targets": sum(r["max_input_chunk_chars"] > OVERSIZED_CHUNK for r in rs),
            "tail_lost_targets": sum(r["tail_lost"] for r in rs),
            "end_cut_targets": sum(r["end_cut"] for r in rs),
            "truncated_targets": sum(r["tail_lost"] or r["end_cut"] for r in rs),
            "share_preamble_or_refusal": round(sum(r["preamble_or_refusal"] for r in rs) / len(rs), 4),
        }
    summary["examples_lost_salient"] = examples
    def targets(flag):
        return sorted({f"{r['item_id']}|{r['article']}" for r in per_row if r[flag]})

    summary["token_counts"] = "o200k_base" if ENC else "skipped (tiktoken not installed)"
    summary["tail_lost"] = targets("tail_lost")
    summary["end_cut"] = targets("end_cut")
    summary["truncated"] = sorted(set(summary["tail_lost"]) | set(summary["end_cut"]))
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summary.items() if k != "examples_lost_salient"}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
