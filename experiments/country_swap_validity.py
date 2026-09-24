"""Deterministic context screening before Country Swap model calls."""
from __future__ import annotations

import hashlib
import json
import re

VERSION = "country-swap-context-v1"
RULES = {
    "environment": r"\b(?:lakes?|lakeshore|rivers?|fauna|wildlife|salmon|fishing|"
                   r"pollution|pollut(?:ed|ants|ing)|environmental|hazardous|toxic|contamin\w*)\b",
    "cross_border": r"\b(?:extradit\w*|deport\w*|expulsi\w*|expel\w*|asylum|"
                    r"refugee\w*|border\w*|pushbacks?|push-backs?|repatriat\w*)\b",
    "territorial": r"\b(?:Transnistr\w*|Nagorno|Karabakh|Abkhaz\w*|Osseti\w*|"
                   r"Crimea\w*|Donbas\w*|Cheche\w*|Northern Cyprus|occupied territor\w*|"
                   r"armed conflicts?|military occupation)\b",
}
DESTINATION_TERMS = {
    "US": ["United States", "USA", "U.S.", "American"],
    "UK": ["United Kingdom", "UK", "Britain", "British"],
    "Turkey": ["Türkiye", "Turkey", "Turkish"],
    "Russia": ["Russia", "Russian Federation", "Russian"],
    "Ukraine": ["Ukraine", "Ukrainian"],
}


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(cases, summaries, countries, destinations, swap):
    """Keep a common cohort across destinations; preserve all exclusions.

    Eligibility means passing these explicit checks. It is not certification
    that every remaining geographic or legal relationship is transferable.
    `swap` is a pure callback whose destination map covers `destinations`.
    """
    unknown = set(destinations)-set(DESTINATION_TERMS)
    if unknown:
        raise ValueError(f"No Country Swap context rules for destinations: {sorted(unknown)}")
    rows = []
    seen = set()
    for case in cases:
        key = (case["item_id"], case["article_full"])
        if key in seen:
            raise ValueError(f"Duplicate Country Swap target: {key}")
        seen.add(key)
        respondent = (case.get("target_respondent") or case.get("respondent") or "").strip()
        text = (summaries.get(key[0]) or [""])[0] or ""
        reasons, hits, hashes = [], {}, {}
        if not text:
            reasons.append("missing_summary")
        if respondent not in countries:
            reasons.append("unresolved_respondent")
        for name, pattern in RULES.items():
            found = sorted({m.group(0) for m in re.finditer(pattern,text,re.I)},key=str.casefold)
            if found:
                reasons.append(name)
                hits[name] = found
        if text and respondent in countries:
            for arm, (_, demonym) in sorted(destinations.items()):
                if countries[respondent][1] == demonym:
                    reasons.append(f"unchanged_respondent:{arm}")
                found = [t for t in DESTINATION_TERMS[arm]
                         if re.search(r"(?<!\w)"+re.escape(t)+r"(?!\w)",text,re.I)]
                if found and countries[respondent][1] != demonym:
                    reasons.append(f"destination_already_present:{arm}")
                    hits[f"destination_already_present:{arm}"] = found
                transformed = swap(text,respondent,arm)
                if transformed == text:
                    reasons.append(f"unchanged_text:{arm}")
                hashes[arm] = digest(transformed)
        rows.append(dict(item_id=key[0],article=key[1],respondent=respondent,
            eligible=not reasons,reasons=reasons,matched_terms=hits,
            original_sha256=digest(text),transformed_sha256=hashes))
    rows.sort(key=lambda r:(r["item_id"],r["article"]))
    return dict(version=VERSION,destinations=sorted(destinations),
        rules_sha256=digest(json.dumps([RULES,DESTINATION_TERMS],sort_keys=True)),
        targets=len(rows),eligible_targets=sum(r["eligible"] for r in rows),
        excluded_targets=sum(not r["eligible"] for r in rows),rows=rows)


def bind_manifest(path, manifest):
    """Do not mix checkpoints created under different context checks."""
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Country Swap context manifest changed; use a new output directory")
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
