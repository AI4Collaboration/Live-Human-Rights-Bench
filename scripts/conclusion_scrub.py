"""Sentence-level scrubber for verdict-conclusion leakage in ECHR texts.

Stage-1 truncation (court_assessment_start / conclusory_pattern) misses
per-article conclusion sentences embedded in the Court's assessment, e.g.
"there has been no violation of Article 8 of the Convention." — a direct
gold-label leak. The 2026-07-03 audit measured own-article label leakage of
6.2% (livehrb-static-2k), 5.5% (livehrb-temporal-2k), 7.3% (echr-verdict-free)
and 2.8% (echr-ukr-verdict-free) before this scrub was applied to the
published data. This module makes the scrub a mandatory pipeline stage so
future live refreshes do not regress.

Usage:
    from conclusion_scrub import scrub_text, scrub_record, has_own_article_leak

    clean, n_dropped = scrub_text(text)
    record = scrub_record(record)          # dict with verdict_free_text etc.
    assert not has_own_article_leak(clean, article)
"""

from __future__ import annotations

import re

# Sentences matching any of these reveal the Court's own conclusion and must
# be dropped. Applied to ALL articles, not just the target one: multi-article
# cases share the same text across (case, article) pairs.
LEAK_SENT = re.compile(
    r"(there has (accordingly |therefore )?been (a|no) violation of)"
    r"|(there has (accordingly |therefore )?been (a|no) breach of)"
    r"|(court (therefore |accordingly )?(concludes|finds|holds|considers)"
    r" that there (has|have|had) been (a|no))"
    r"|(finds? (that there is|there has been) (a|no) violation)"
    r"|(does not find (a|any) (violation|breach))"
    r"|(no violation of article \d+[\w\s./()-]* has (therefore )?occurred)"
    r"|(unanimously,? that)"
    r"|(discloses? (a|no) (violation|breach) of article)",
    re.I,
)

# ECHR paragraphs are numbered ("60. Accordingly, ..."), so split on sentence
# enders followed by whitespace + optional paragraph number + capital/quote.
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=(?:\d{1,3}\.\s+)?[A-Z“\"(])")

SCRUB_MARKER = "+conclusion_scrub"


def scrub_text(text: str) -> tuple[str, int]:
    """Drop conclusion sentences. Returns (clean_text, n_sentences_dropped)."""
    kept, dropped = [], 0
    for sent in SENT_SPLIT.split(text):
        if LEAK_SENT.search(sent):
            dropped += 1
        else:
            kept.append(sent)
    return " ".join(kept), dropped


def has_own_article_leak(text: str, article) -> bool:
    """True if the text states the verdict for the given target article."""
    pattern = re.compile(
        r"there has (accordingly )?been (a|no) violation of Article\s+"
        + re.escape(str(article)) + r"\b",
        re.I,
    )
    return bool(pattern.search(text))


def scrub_record(rec: dict, text_key: str = "verdict_free_text") -> dict:
    """Scrub one dataset record in place-compatible copy; updates
    verdict_removal_method / verdict_free_length / retention_percentage."""
    rec = dict(rec)
    clean, dropped = scrub_text(rec[text_key])
    if dropped:
        rec[text_key] = clean
        method = rec.get("verdict_removal_method", "")
        if SCRUB_MARKER not in method:
            rec["verdict_removal_method"] = method + SCRUB_MARKER
        rec["verdict_free_length"] = len(clean)
        if rec.get("original_length"):
            rec["retention_percentage"] = round(
                len(clean) / rec["original_length"] * 100, 1
            )
    return rec


def scrub_records(records: list[dict], text_key: str = "verdict_free_text",
                  verbose: bool = True) -> list[dict]:
    """Scrub a list of records; asserts zero own-article leakage afterwards."""
    out = [scrub_record(r, text_key) for r in records]
    touched = sum(1 for orig, r in zip(records, out) if r[text_key] != orig[text_key])
    leaks = sum(
        1 for r in out
        if "article" in r and has_own_article_leak(r[text_key], r["article"])
    )
    if verbose:
        print(f"[conclusion_scrub] scrubbed {touched}/{len(out)} records, "
              f"own-article leaks after scrub: {leaks}")
    assert leaks == 0, f"conclusion scrub left {leaks} own-article leaks"
    return out


if __name__ == "__main__":
    # self-test
    leaky = (
        "57. The applicant complained under Article 8. "
        "58. The Court considers the complaint admissible. "
        "59. Accordingly, there has been no violation of Article 8 of the Convention. "
        "60. The applicant also relied on Article 13."
    )
    clean, dropped = scrub_text(leaky)
    assert dropped == 1, dropped
    assert "no violation of Article 8" not in clean
    assert "Article 13" in clean and "admissible" in clean
    assert has_own_article_leak(leaky, 8) and not has_own_article_leak(clean, 8)

    rec = scrub_record({
        "verdict_free_text": leaky, "article": "8",
        "verdict_removal_method": "court_assessment_start",
        "original_length": 1000,
    })
    assert rec["verdict_removal_method"].endswith(SCRUB_MARKER)
    assert rec["verdict_free_length"] == len(clean)

    kept_clean = "The applicant alleged a violation of Article 3. The facts are as follows."
    same, zero = scrub_text(kept_clean)
    assert zero == 0 and same == kept_clean

    print("conclusion_scrub self-test OK")
