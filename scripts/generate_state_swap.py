#!/usr/bin/env python3
"""
LSYC-43: state-swap counterfactual set for LiveHumanRightsBench (experiment 6).

Anonymize-then-fill (Arian-confirmed 2026-07-20):
  1. Bedrock Haiku DETECTS respondent-state identity spans (short JSON output; the
     model never rewrites the text, so facts cannot drift).
  2. Code templates the body deterministically ([DEFENDANT STATE] / [DEFENDANT
     STATE ADJ]) and fills 4 arms per case: control_original, control_neutral
     (Iceland), probe_ukraine, probe_russia.
Base pool: echr-livehrb-static-2k, group==regular, substantive article_full,
single-respondent CoE states only. Legally-material-applicant-nationality cases
are dropped, not swapped. Output: overthelex/echr-livehrb-stateswap (separate
dataset, not a group in static-2k).
"""
import argparse, json, os, re, sys, time, threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import boto3
from datasets import load_dataset

MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"

SUBSTANTIVE = {"1","2","3","4","5","6","7","8","9","10","11","12","13","14","18",
               "P1-1","P1-2","P1-3","P4-2","P4-3","P4-4","P6-1","P7-1","P7-2","P7-3","P7-4","P12-1"}

# CoE respondent states -> (display name, adjective/demonym). Only single-respondent
# cases whose respondent is a key here enter the swap set; multi-state / malformed
# respondents are dropped.
COUNTRY = {
    "ALBANIA": ("Albania", "Albanian"), "ANDORRA": ("Andorra", "Andorran"),
    "ARMENIA": ("Armenia", "Armenian"), "AUSTRIA": ("Austria", "Austrian"),
    "AZERBAIJAN": ("Azerbaijan", "Azerbaijani"), "BELGIUM": ("Belgium", "Belgian"),
    "BOSNIA AND HERZEGOVINA": ("Bosnia and Herzegovina", "Bosnian"),
    "BULGARIA": ("Bulgaria", "Bulgarian"), "CROATIA": ("Croatia", "Croatian"),
    "CYPRUS": ("Cyprus", "Cypriot"), "CZECH REPUBLIC": ("the Czech Republic", "Czech"),
    "DENMARK": ("Denmark", "Danish"), "ESTONIA": ("Estonia", "Estonian"),
    "FINLAND": ("Finland", "Finnish"), "FRANCE": ("France", "French"),
    "GEORGIA": ("Georgia", "Georgian"), "GERMANY": ("Germany", "German"),
    "GREECE": ("Greece", "Greek"), "HUNGARY": ("Hungary", "Hungarian"),
    "ICELAND": ("Iceland", "Icelandic"), "IRELAND": ("Ireland", "Irish"),
    "ITALY": ("Italy", "Italian"), "LATVIA": ("Latvia", "Latvian"),
    "LIECHTENSTEIN": ("Liechtenstein", "Liechtenstein"),
    "LITHUANIA": ("Lithuania", "Lithuanian"), "LUXEMBOURG": ("Luxembourg", "Luxembourgish"),
    "MALTA": ("Malta", "Maltese"), "MOLDOVA": ("the Republic of Moldova", "Moldovan"),
    "REPUBLIC OF MOLDOVA": ("the Republic of Moldova", "Moldovan"),
    "MONTENEGRO": ("Montenegro", "Montenegrin"), "NETHERLANDS": ("the Netherlands", "Dutch"),
    "NORTH MACEDONIA": ("North Macedonia", "Macedonian"), "NORWAY": ("Norway", "Norwegian"),
    "POLAND": ("Poland", "Polish"), "PORTUGAL": ("Portugal", "Portuguese"),
    "ROMANIA": ("Romania", "Romanian"), "RUSSIA": ("Russia", "Russian"),
    "SAN MARINO": ("San Marino", "Sammarinese"), "SERBIA": ("Serbia", "Serbian"),
    "SLOVAKIA": ("Slovakia", "Slovak"), "SLOVENIA": ("Slovenia", "Slovenian"),
    "SPAIN": ("Spain", "Spanish"), "SWEDEN": ("Sweden", "Swedish"),
    "SWITZERLAND": ("Switzerland", "Swiss"), "TURKEY": ("Turkey", "Turkish"),
    "TÜRKİYE": ("Turkey", "Turkish"), "UNITED KINGDOM": ("the United Kingdom", "British"),
}

ARMS = [
    ("control_original", None),      # filled with the real respondent
    ("control_neutral", "ICELAND"),
    ("probe_ukraine", "UKRAINE"),
    ("probe_russia", "RUSSIA"),
]
COUNTRY["UKRAINE"] = ("Ukraine", "Ukrainian")

DETECT_SYSTEM = ("You are a precise text-annotation tool for European Court of Human "
    "Rights judgments. You never rewrite, summarize, or paraphrase text. You only "
    "identify exact substrings and return JSON.")

DETECT_USER = """The RESPONDENT STATE in this ECtHR case is: {respondent}.

Identify every substring in the TEXT that reveals the RESPONDENT STATE's identity, so it can be neutralized for a country-swap experiment. Cover:
- the respondent country name and its variants/abbreviations
- the demonym/adjective (e.g. "Croatian")
- respondent cities, regions, and place names
- respondent national courts, authorities, ministries, officials, agencies, and bodies

For each, output an object with:
- "find": the EXACT substring as it appears in the TEXT, verbatim and case-sensitive
- "replace": the neutralized replacement, using ONLY the tokens [DEFENDANT STATE] for the country name and [DEFENDANT STATE ADJ] for anything adjectival or place/organisation derived. Examples:
    "Croatia" -> "[DEFENDANT STATE]"
    "Croatian" -> "[DEFENDANT STATE ADJ]"
    "the Zagreb County Court" -> "the [DEFENDANT STATE ADJ] County Court"
    "Zagreb" -> "a [DEFENDANT STATE ADJ] city"

Also decide: is the APPLICANT's OWN nationality legally material to the outcome (expulsion, extradition, Article 3 refoulement, or Article 8 residence/family cases that turn on the applicant being a foreign national)? If yes, the case cannot be country-swapped.

Return ONLY minified JSON, no prose, no code fences:
{{"spans":[{{"find":"...","replace":"..."}}],"applicant_nationality_material":true|false}}

Rules: every "find" MUST appear verbatim in the TEXT. Do NOT include applicant names. Do NOT alter any other facts, dates, numbers, or legal reasoning. List each distinct string once.

TEXT:
{text}"""


def bedrock_detect(client, respondent, text, max_tokens=4000, retries=4):
    user = DETECT_USER.format(respondent=respondent, text=text)
    for att in range(retries):
        try:
            resp = client.converse(
                modelId=MODEL,
                system=[{"text": DETECT_SYSTEM}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
            )
            out = resp["output"]["message"]["content"][0]["text"].strip()
            out = re.sub(r"^```(?:json)?|```$", "", out.strip()).strip()
            return json.loads(out)
        except Exception as e:
            if att == retries - 1:
                print(f"  [detect FAIL] {respondent}: {type(e).__name__}: {str(e)[:100]}")
                return None
            time.sleep(1.5 * (att + 1))
    return None


# Bare short forms where the display name differs from the common in-text form.
SHORT_ALIASES = {
    "MOLDOVA": ["Moldova"], "REPUBLIC OF MOLDOVA": ["Moldova"],
    "CZECH REPUBLIC": ["Czechia"], "TURKEY": ["Türkiye", "Turkiye"],
    "TÜRKİYE": ["Turkey"], "BOSNIA AND HERZEGOVINA": ["Bosnia", "Herzegovina"],
    "NORTH MACEDONIA": ["Macedonia"],
}


def deterministic_backstop(text, resp_key):
    """Guarantee the known respondent country name + demonym never leak, whatever
    the LLM missed. Word-boundary, case-insensitive. Adjective first so it is not
    truncated by the shorter country name (e.g. Albanian vs Albania)."""
    name, adj = COUNTRY[resp_key]
    names = {name, name[4:] if name.lower().startswith("the ") else name,
             resp_key.title()}
    names |= set(SHORT_ALIASES.get(resp_key, []))
    n = 0
    for a in sorted({adj}, key=len, reverse=True):
        text, k = re.subn(r"\b" + re.escape(a) + r"\b", "[DEFENDANT STATE ADJ]",
                          text, flags=re.IGNORECASE)
        n += k
    for nm in sorted(names, key=len, reverse=True):
        if not nm or "AND" in nm.upper().split():
            # skip malformed title-cased multiword keys; real name handled above
            if nm != name:
                continue
        text, k = re.subn(r"\b" + re.escape(nm) + r"\b", "[DEFENDANT STATE]",
                          text, flags=re.IGNORECASE)
        n += k
    return text, n


def apply_template(text, spans, resp_key):
    """Deterministic replace of LLM-detected spans (longest find first), then a
    deterministic backstop over the known country name/demonym. Returns
    (templated_text, n_applied, n_missed, n_backstop)."""
    applied = missed = 0
    for sp in sorted(spans, key=lambda s: len(s.get("find", "")), reverse=True):
        f, r = sp.get("find", ""), sp.get("replace", "")
        if not f:
            continue
        if f in text:
            text = text.replace(f, r)
            applied += 1
        else:
            missed += 1
    text, n_back = deterministic_backstop(text, resp_key)
    return text, applied, missed, n_back


def fill(templated, name, adj):
    return (templated.replace("[DEFENDANT STATE ADJ]", adj)
                     .replace("[DEFENDANT STATE]", name))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap N base items (0=all)")
    ap.add_argument("--out", default="data/processed/livehrb_stateswap.jsonl")
    ap.add_argument("--repo", default="overthelex/echr-livehrb-stateswap")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--resume", default=None,
                    help="existing jsonl: skip base cases already covered, process only the rest")
    ap.add_argument("--max-tokens", type=int, default=4000)
    a = ap.parse_args()

    ds = load_dataset("overthelex/echr-livehrb-static-2k", split="train")
    pool = [r for r in ds if r["group"] == "regular"
            and r["article_full"] in SUBSTANTIVE
            and r["respondent"] in COUNTRY]
    dropped_resp = sum(1 for r in ds if r["group"] == "regular"
                       and r["article_full"] in SUBSTANTIVE
                       and r["respondent"] not in COUNTRY)
    if a.limit:
        pool = pool[:a.limit]
    if a.resume:
        covered = {json.loads(l)["swap_group_id"]
                   for l in open(a.resume)}
        before = len(pool)
        pool = [r for r in pool if (r["item_id"] + "|" + r["article_full"]) not in covered]
        print(f"resume: {before} base, {len(covered)} groups covered, "
              f"processing {len(pool)} remaining")
    print(f"base pool: {len(pool)} single-respondent substantive ex-UA "
          f"(+{dropped_resp} multi/again-state respondents dropped)")

    client = boto3.client("bedrock-runtime", region_name=REGION)
    stats = Counter()
    lock = threading.Lock()
    done = [0]

    def process(r):
        det = bedrock_detect(client, r["respondent"], r["verdict_free_text"],
                             max_tokens=a.max_tokens)
        with lock:
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  {done[0]}/{len(pool)} kept={stats['kept']} "
                      f"drop_nat={stats['dropped_nationality_material']} "
                      f"nocue={stats['no_state_cue_found']} fail={stats['detect_fail']}")
        if det is None:
            with lock: stats["detect_fail"] += 1
            return None
        if det.get("applicant_nationality_material"):
            with lock: stats["dropped_nationality_material"] += 1
            return None
        spans = det.get("spans", [])
        templated, applied, missed, n_back = apply_template(
            r["verdict_free_text"], spans, r["respondent"])
        if applied == 0 and n_back == 0:
            with lock: stats["no_state_cue_found"] += 1
            return None
        gid = r["item_id"] + "|" + r["article_full"]
        group = []
        for arm, swap_resp in ARMS:
            key = r["respondent"] if swap_resp is None else swap_resp
            name, adj = COUNTRY[key]
            group.append({
                "swap_group_id": gid, "item_id": r["item_id"], "arm": arm,
                "respondent": name, "respondent_adj": adj,
                "case_text_templated": templated,
                "case_text_rendered": fill(templated, name, adj),
                "article_full": r["article_full"], "article": r["article"],
                "violation_label": r["violation_label"],
                "respondent_original": r["respondent"],
                "anonymization_report": json.dumps(
                    {"n_spans_applied": applied, "n_spans_missed": missed,
                     "n_backstop": n_back, "model": MODEL,
                     "method": "detect-then-fill-v1"}),
                "case_name": r["case_name"],
                "application_number": r["application_number"], "ecli": r["ecli"],
            })
        with lock: stats["kept"] += 1
        return group

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(process, pool))
    rows = [row for grp in results if grp for row in grp]
    with open(a.out, "w") as fout:
        for row in rows:
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nDONE base kept={stats['kept']} rows={len(rows)} ({stats['kept']}x4) "
          f"| dropped: nat={stats['dropped_nationality_material']} "
          f"nocue={stats['no_state_cue_found']} fail={stats['detect_fail']}")
    print(f"wrote {a.out}")

    if a.push:
        from datasets import Dataset
        Dataset.from_list(rows).push_to_hub(a.repo, commit_message=(
            "LSYC-43 state-swap counterfactual set: 4 arms (original/Iceland/"
            "Ukraine/Russia) per case, anonymize-then-fill, facts held fixed"))
        print("PUSHED", a.repo)


if __name__ == "__main__":
    main()
