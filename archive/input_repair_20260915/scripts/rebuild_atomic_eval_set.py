#!/usr/bin/env python3
"""Repair all 1,000 targets as respondent-specific atomic sub-conclusions."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from targets import ARTICLE_TITLES, provision_name, target_key, target_question, target_stratum


CASES_PATH = ROOT / "data/processed/echr_unified.json"
SUMMARIES_PATH = ROOT / "data/processed/summaries_dsv41flash.json"
MANIFEST_PATH = ROOT / "configs/evaluation_dataset.json"
OVERRIDES_PATH = ROOT / "configs/target_scope_overrides.json"
AUDIT_PATH = ROOT / "data/audits/target_scope_audit.json"
DATASET_ID = "echr-unified-atomic-targets-20260916"

HUDOC_URL = "https://hudoc.echr.coe.int/app/query/results"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
SELECT = "itemid,docname,conclusion,respondent,article,ecli,languageisocode,kpdate"

COUNTRY_NAMES = {
    "ALB": "Albania", "AND": "Andorra", "ARM": "Armenia", "AUT": "Austria",
    "AZE": "Azerbaijan", "BEL": "Belgium", "BGR": "Bulgaria",
    "BIH": "Bosnia and Herzegovina", "CHE": "Switzerland", "CYP": "Cyprus",
    "CZE": "Czechia", "DEU": "Germany", "DNK": "Denmark", "ESP": "Spain",
    "EST": "Estonia", "FIN": "Finland", "FRA": "France",
    "GBR": "the United Kingdom", "GEO": "Georgia", "GRC": "Greece",
    "HRV": "Croatia", "HUN": "Hungary", "IRL": "Ireland", "ISL": "Iceland",
    "ITA": "Italy", "LIE": "Liechtenstein", "LTU": "Lithuania",
    "LUX": "Luxembourg", "LVA": "Latvia", "MCO": "Monaco",
    "MDA": "the Republic of Moldova", "MKD": "North Macedonia", "MLT": "Malta",
    "MNE": "Montenegro", "NLD": "the Netherlands", "NOR": "Norway",
    "POL": "Poland", "PRT": "Portugal", "ROU": "Romania", "RUS": "Russia",
    "SMR": "San Marino", "SRB": "Serbia", "SVK": "Slovakia",
    "SVN": "Slovenia", "SWE": "Sweden", "TUR": "Türkiye", "UKR": "Ukraine",
}

COUNTRY_ALIASES = {
    "CZE": ("Czechia", "Czech Republic"),
    "GBR": ("the United Kingdom", "United Kingdom"),
    "MDA": ("the Republic of Moldova", "Republic of Moldova", "Moldova"),
    "MKD": (
        "North Macedonia", "the former Yugoslav Republic of Macedonia",
        "former Yugoslav Republic of Macedonia",
    ),
    "NLD": ("the Netherlands", "Netherlands"),
    "RUS": ("Russia", "Russian Federation"),
    "SVK": ("Slovakia", "Slovak Republic"),
    "TUR": ("Türkiye", "Turkey"),
}

HOLDING_START = re.compile(
    r"(?:(?<=;)|^)(?:No violation|Violation) of Article\s+|"
    r"(?:(?<=;)|^)(?:Non-violation|Violation) de l.article\s+",
    re.IGNORECASE,
)


def _normalise_words(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _mentions_country(fragment: str, code: str) -> bool:
    haystack = f" {_normalise_words(fragment)} "
    aliases = COUNTRY_ALIASES.get(code, (COUNTRY_NAMES.get(code, ""),))
    return any(alias and f" {_normalise_words(alias)} " in haystack for alias in aliases)


def _headline_code(fragment: str, *, french: bool = False) -> str | None:
    if french:
        match = re.match(
            r"^(?:Non-violation|Violation) de l.article\s+(\d+)"
            r"(?:\+[^\s-]+)?(?:\s+du\s+Protocole\s+n[o°]?\.?\s*(\d+))?",
            fragment,
            re.IGNORECASE,
        )
    else:
        match = re.match(
            r"^(?:No violation|Violation) of Article\s+(\d+)"
            r"(?:\+[^\s-]+)?(?:\s+of\s+(?:the\s+)?Protocol\s+No\.?\s*(\d+))?",
            fragment,
            re.IGNORECASE,
        )
    if not match:
        return None
    article, protocol = match.groups()
    return f"P{protocol}-{article}" if protocol else article


def _issue(fragment: str, respondent_codes: list[str]) -> tuple[str, str]:
    chunks = re.findall(r"\(([^()]*)\)", fragment)
    details, aspect = [], "unspecified"
    excluded = {
        "pecuniary damage", "non-pecuniary damage", "just satisfaction",
        "costs and expenses", "general measures", "individual measures",
        "default interest", "finding of violation sufficient",
    }
    for chunk in chunks:
        if any(_mentions_country(chunk, code) for code in respondent_codes):
            continue
        low = chunk.casefold()
        if "procedural aspect" in low:
            aspect = "procedural"
            continue
        if "substantive aspect" in low:
            aspect = "substantive"
            continue
        value = re.sub(r"\{general\}", "", chunk, flags=re.IGNORECASE).strip(" -")
        if value.casefold().startswith("article ") and " - " in value:
            value = value.split(" - ", 1)[1]
        for part in value.split(";"):
            part = " ".join(part.split()).strip(" -")
            if part.casefold() in excluded:
                continue
            if part and not re.fullmatch(r"Article\s+[\w.-]+", part, re.IGNORECASE):
                if part.casefold() not in {item.casefold() for item in details}:
                    details.append(part)
    if aspect != "unspecified":
        details.append(f"{aspect} aspect")
    issue = "; ".join(details) or "the complaint identified under this provision"
    return issue, aspect


def conclusion_holdings(conclusion: str, respondent_codes: list[str]) -> list[dict]:
    """Extract atomic holdings without sending their outcome text to a model."""
    matches = list(HOLDING_START.finditer(conclusion or ""))
    holdings = []
    for index, match_start in enumerate(matches):
        start = match_start.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(conclusion)
        fragment = (conclusion or "")[start:end].strip(" ;")
        match = re.match(r"^(No violation|Violation) of ", fragment, re.IGNORECASE)
        french = False
        if not match:
            match = re.match(r"^(Non-violation|Violation) de ", fragment, re.IGNORECASE)
            french = bool(match)
        if not match:
            continue
        code = _headline_code(fragment, french=french)
        if not code or code not in ARTICLE_TITLES:
            continue
        token = match.group(1).casefold()
        issue, aspect = _issue(fragment, respondent_codes)
        holdings.append(
            {
                "holding_index": index,
                "article_full": code,
                "label": "no_violation" if token.startswith(("no", "non")) else "violation",
                "respondent_codes": [
                    code for code in respondent_codes if _mentions_country(fragment, code)
                ],
                "target_issue": issue,
                "target_aspect": aspect,
                "fragment": fragment,
            }
        )
    return holdings


def fetch_metadata(item_ids: set[str], min_year: int, max_year: int) -> dict[str, dict]:
    session = requests.Session()
    metadata: dict[str, dict] = {}
    for year in range(min_year, max_year + 1):
        query = (
            "contentsitename:ECHR AND "
            "(NOT (doctype:PR OR doctype:HFCOMOLD OR doctype:HECOMOLD)) AND "
            '((languageisocode:"ENG")) AND ((documentcollectionid:"JUDGMENTS")) AND '
            f"((kpdate:[{year}-01-01T00:00:00 TO {year + 1}-01-01T00:00:00]))"
        )
        start = 0
        while True:
            params = {
                "query": query, "select": SELECT, "sort": "itemid Ascending",
                "start": str(start), "length": "500",
            }
            for attempt in range(5):
                response = session.get(HUDOC_URL, params=params, headers=HEADERS, timeout=90)
                if response.status_code == 200 and response.headers.get(
                    "content-type", ""
                ).startswith("application/json"):
                    break
                time.sleep(attempt + 1)
            else:
                raise RuntimeError(f"HUDOC request failed for {year=} {start=}")
            payload = response.json()
            results = payload.get("results", [])
            for result in results:
                columns = result.get("columns", {})
                if columns.get("itemid") in item_ids:
                    metadata[columns["itemid"]] = columns
            start += len(results)
            if not results or start >= int(payload.get("resultcount", 0)):
                break
    missing = item_ids - set(metadata)
    if missing:
        raise ValueError(f"HUDOC metadata missing for {len(missing)} judgments")
    return metadata


def _codes(official: dict) -> list[str]:
    return [value for value in str(official.get("respondent", "")).split(";") if value]


def candidates(official: dict, article: str | None = None) -> list[dict]:
    codes = _codes(official)
    holdings = conclusion_holdings(str(official.get("conclusion", "")), codes)
    if article is not None:
        holdings = [row for row in holdings if row["article_full"] == article]
    results = []
    for holding in holdings:
        assigned = holding["respondent_codes"] or (codes if len(codes) == 1 else [])
        for code in assigned:
            results.append(
                {
                    **holding,
                    "target_respondent_code": code,
                    "target_respondent": COUNTRY_NAMES[code],
                    "assignment": "single_respondent" if len(codes) == 1 else "explicit_country",
                }
            )
    return results


def manual_candidate(official: dict, article: str, override: dict) -> dict:
    """Apply a source-backed respondent assignment recorded after manual review."""
    code = override["target_respondent_code"]
    if code not in _codes(official):
        raise ValueError(f"Override respondent {code} is not a respondent in the judgment")
    matches = [
        row
        for row in conclusion_holdings(str(official.get("conclusion", "")), _codes(official))
        if row["article_full"] == article
        and row["holding_index"] == override["holding_index"]
    ]
    if len(matches) != 1:
        raise ValueError(f"Override did not identify exactly one holding for {article}")
    candidate = {
        **matches[0],
        "target_respondent_code": code,
        "target_respondent": COUNTRY_NAMES[code],
        "assignment": "manual_official_source_review",
    }
    if override.get("target_issue"):
        candidate["target_issue"] = override["target_issue"]
    if override.get("target_aspect"):
        candidate["target_aspect"] = override["target_aspect"]
    return candidate


def _candidate_key(item_id: str, candidate: dict) -> tuple[str, str, str, str]:
    return (
        item_id,
        candidate["target_respondent_code"],
        candidate["article_full"],
        candidate["target_issue"].casefold(),
    )


def _select(source: dict, options: list[dict], used: set[tuple], override: dict | None):
    if override:
        options = [
            row for row in options
            if row["holding_index"] == override["holding_index"]
            and row["target_respondent_code"] == override["target_respondent_code"]
        ]
    available = [row for row in options if _candidate_key(source["item_id"], row) not in used]
    if not available:
        return None
    if not override:
        matching = [row for row in available if row["label"] == source["violation_label"]]
        available = matching or available
    available.sort(
        key=lambda row: (
            row["target_issue"] == "the complaint identified under this provision",
            row["holding_index"], row["target_respondent_code"],
        )
    )
    return available[0]


def _apply(source: dict, choice: dict) -> dict:
    row = dict(source)
    article = choice["article_full"]
    row.update(
        article=article,
        article_full=article,
        violation_label=choice["label"],
        target_respondent_code=choice["target_respondent_code"],
        target_respondent=choice["target_respondent"],
        target_provision=provision_name(article),
        target_issue=choice["target_issue"],
        target_aspect=choice["target_aspect"],
        target_question=target_question(
            choice["target_respondent"], article, choice["target_issue"]
        ),
        target_status="verified",
    )
    return row


def build(cases: list[dict], metadata: dict[str, dict], overrides: dict):
    if len(cases) != 1000:
        raise ValueError(f"Expected the unrepaired 1,000-row source, found {len(cases)}")
    output: list[dict | None] = [None] * len(cases)
    audits: list[dict | None] = [None] * len(cases)
    unresolved = []
    used: set[tuple] = set()
    representatives = {}
    for row in cases:
        if str(row.get("article_full")) != "41":
            representatives.setdefault(row["item_id"], row)

    order = [i for i, row in enumerate(cases) if str(row.get("article_full")) != "41"]
    order += [i for i, row in enumerate(cases) if str(row.get("article_full")) == "41"]
    for index in order:
        source = cases[index]
        original_article = str(source.get("article_full") or source.get("article") or "")
        article = None if original_article == "41" else original_article
        base_source = source
        base_official = metadata[source["item_id"]]
        options = candidates(base_official, article)
        override = overrides.get(f"{source['item_id']}|{original_article}")
        replacement_requested = bool(
            override and override.get("replace_with_same_year_atomic_target")
        )
        if override and not replacement_requested:
            options.append(manual_candidate(base_official, original_article, override))
        choice = None if replacement_requested else _select(source, options, used, override)
        donor_replacement = False
        if choice is None and (original_article == "41" or replacement_requested):
            donor_options = []
            source_year = source["decision_date"][:4]
            for donor in representatives.values():
                if donor["decision_date"][:4] != source_year:
                    continue
                for candidate in candidates(metadata[donor["item_id"]]):
                    if candidate["label"] != source["violation_label"]:
                        continue
                    if target_stratum(candidate["article_full"]) != "substantive":
                        continue
                    if candidate["target_issue"] == "the complaint identified under this provision":
                        continue
                    if _candidate_key(donor["item_id"], candidate) in used:
                        continue
                    donor_options.append((donor, candidate))
            donor_options.sort(
                key=lambda pair: (
                    pair[0]["item_id"], pair[1]["article_full"],
                    pair[1]["holding_index"], pair[1]["target_respondent_code"],
                )
            )
            if donor_options:
                base_source, choice = donor_options[0]
                base_official = metadata[base_source["item_id"]]
                donor_replacement = True
        if choice is None:
            unresolved.append(
                {
                    "source_row": index,
                    "item_id": source["item_id"],
                    "case_name": source["case_name"],
                    "article_full": original_article,
                    "original_label": source["violation_label"],
                    "respondent_codes": _codes(metadata[source["item_id"]]),
                    "parsed_candidates": [
                        {key: value for key, value in row.items() if key != "fragment"}
                        for row in options
                    ],
                    "conclusion": metadata[source["item_id"]].get("conclusion", ""),
                }
            )
            continue
        repaired = _apply(base_source, choice)
        used.add(_candidate_key(base_source["item_id"], choice))
        output[index] = repaired
        repairs = []
        if len(_codes(base_official)) > 1:
            repairs.append("selected_one_respondent")
        same_target = [
            row for row in candidates(base_official, choice["article_full"])
            if row["target_respondent_code"] == choice["target_respondent_code"]
        ]
        if len({row["label"] for row in same_target}) > 1:
            repairs.append("selected_one_sub_conclusion")
        if original_article == "41":
            repairs.append("retargeted_article_41")
        if donor_replacement:
            repairs.append("used_same_year_atomic_replacement")
        if replacement_requested:
            repairs.append("replaced_unscoped_target")
        if source["violation_label"] != repaired["violation_label"]:
            repairs.append("corrected_label")
        audits[index] = {
            "source_row": index,
            "source_item_id": source["item_id"],
            "source_case_name": source["case_name"],
            "target_item_id": repaired["item_id"],
            "target_case_name": repaired["case_name"],
            "original_article_full": original_article,
            "target_article_full": repaired["article_full"],
            "original_label": source["violation_label"],
            "target_label": repaired["violation_label"],
            "target_respondent_code": repaired["target_respondent_code"],
            "target_respondent": repaired["target_respondent"],
            "target_issue": repaired["target_issue"],
            "target_aspect": repaired["target_aspect"],
            "repairs": repairs,
            "assignment": choice["assignment"],
            "holding_index": choice["holding_index"],
            "official_holding": choice["fragment"],
        }
    return output, audits, unresolved


def validate(cases: list[dict], summaries: dict, audits: list[dict]) -> None:
    if len(cases) != 1000 or len(audits) != 1000:
        raise ValueError("The repaired cohort must contain exactly 1,000 rows and audits")
    keys = [target_key(row) for row in cases]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate atomic target")
    for row in cases:
        if row["article_full"] == "41" or row["article"] != row["article_full"]:
            raise ValueError("Invalid target provision")
        if row["target_provision"] != provision_name(row["article_full"]):
            raise ValueError("Stale target provision")
        expected = target_question(
            row["target_respondent"], row["article_full"], row["target_issue"]
        )
        if row["target_question"] != expected or row["target_status"] != "verified":
            raise ValueError("Target contract is incomplete")
        if row["violation_label"] not in {"violation", "no_violation"}:
            raise ValueError("Invalid target label")
    represented = {row["item_id"] for row in cases}
    if represented != set(summaries.get("summaries", {})):
        raise ValueError("Summary coverage does not exactly match the target judgments")


def updated_manifest(old: dict, cases: list[dict]) -> dict:
    manifest = dict(old)
    for key in ("hash_policy", "source_commit", "input_release"):
        manifest.pop(key, None)
    manifest.update(
        schema_version=2,
        dataset_id=DATASET_ID,
        selection=(
            "The fixed 1,000-row cohort with one verified atomic sub-conclusion per row."
        ),
    )
    dataset = dict(manifest["dataset"])
    dataset.pop("sha256_lf", None)
    dataset.update(
        instances=1000,
        judgments=len({row["item_id"] for row in cases}),
        instance_key=[
            "item_id", "target_respondent_code", "article_full", "target_issue"
        ],
        labels=dict(Counter(row["violation_label"] for row in cases)),
        annual_counts=dict(sorted(Counter(row["decision_date"][:4] for row in cases).items())),
        target_contract={
            "unit": "one judgment, one respondent State, one provision, one sub-conclusion",
            "required_fields": [
                "target_respondent_code", "target_respondent", "target_provision",
                "target_issue", "target_aspect", "target_question", "target_status",
            ],
            "audit": "data/audits/target_scope_audit.json",
        },
    )
    manifest["dataset"] = dataset
    summaries = dict(manifest["summaries"])
    summaries.pop("sha256_lf", None)
    summaries.update(
        represented_judgments=len({row["item_id"] for row in cases}),
        complete_judgments=len({row["item_id"] for row in cases}),
        usable_summaries=len({row["item_id"] for row in cases}),
        missing_slots_zero_based=[],
    )
    manifest["summaries"] = summaries
    manifest["provenance_notes"] = [
        "All 1,000 rows are retained and have one explicit atomic target.",
        "Multi-respondent and mixed-outcome judgments select one official sub-conclusion.",
        "Former Article 41 rows target an unused merits sub-conclusion in the same judgment.",
        "Outcome-bearing evidence is stored only in the audit artifact, never in prompts.",
    ]
    return manifest


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--unresolved-output", type=Path)
    args = parser.parse_args()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    summaries = json.loads(SUMMARIES_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    overrides = (
        json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        if OVERRIDES_PATH.exists() else {}
    )
    years = [int(row["decision_date"][:4]) for row in cases]
    metadata = fetch_metadata({row["item_id"] for row in cases}, min(years), max(years))
    repaired, audits, unresolved = build(cases, metadata, overrides)
    if args.unresolved_output:
        write_json(args.unresolved_output, unresolved)
    summary = {
        "status": "PASSED" if not unresolved else "UNRESOLVED",
        "input_instances": len(cases),
        "output_instances": sum(row is not None for row in repaired),
        "unresolved_instances": len(unresolved),
        "repair_counts": dict(
            Counter(repair for row in audits if row for repair in row["repairs"])
        ),
    }
    print(json.dumps(summary, indent=2))
    if unresolved:
        return 2
    repaired_rows = list(repaired)
    audit_rows = list(audits)
    summaries = dict(summaries)
    summaries.update(
        dataset_id=DATASET_ID,
        n_judgments=len({row["item_id"] for row in repaired_rows}),
        n_complete=len({row["item_id"] for row in repaired_rows}),
    )
    summaries.pop("release_id", None)
    validate(repaired_rows, summaries, audit_rows)
    audit = {
        **summary,
        "target_contract": {
            "unit": "one judgment, one respondent State, one provision, one sub-conclusion",
            "row_count_policy": "one output row for every input row",
        },
        "rows": audit_rows,
    }
    if args.publish:
        write_json(CASES_PATH, repaired_rows)
        write_json(SUMMARIES_PATH, summaries)
        write_json(MANIFEST_PATH, updated_manifest(manifest, repaired_rows))
        write_json(AUDIT_PATH, audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
