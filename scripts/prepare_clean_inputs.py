"""Build a noncanonical source proposal, preserving all instance metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

from leak_audit.boundaries import repair
from leak_audit.factual_tables import extract

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "4a1ba1117a047dac7553ca2cfd3100a18171a841"
FIELD = "full_case_text_no_verdict"
# Reviewed exceptions: headings were lost in the old exported source.
REVIEWED_BOUNDARIES = {
    "001-219984": "43. The Court’s case-law has clarified",
    "001-231331": "JOINDER OF THE APPLICATIONS",
    "001-247913": "JOINDER OF THE APPLICATIONS",
}
RESTORE_FACTS = {"001-238072", "001-146047"}
REMOVE_INTRODUCTION = {"001-206511", "001-210689"}


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prepare(rows, recovered, cache):
    by, cleaned, provenance, unresolved = {}, {}, [], []
    for row in rows:
        by.setdefault(row["item_id"], row)
    for key, row in by.items():
        old = row[FIELD]
        # Restore the full document only for the eight broken TOC-only sources.
        toc_only = bool(re.search(r"TABLE OF CONTENTS", old, re.I)) and "In the case of" not in old
        restore = toc_only or key in RESTORE_FACTS
        working = recovered[key]["text"] if restore and key in recovered else old
        table_record = None
        try:
            if key in REVIEWED_BOUNDARIES:
                quote = REVIEWED_BOUNDARIES[key]
                if working.count(quote) != 1:
                    raise ValueError("Reviewed boundary no longer uniquely matches")
                offset = working.index(quote)
                working = working[:offset].rstrip()
            clean, spans = repair(working)
            if key in REMOVE_INTRODUCTION:
                intro = clean.index("INTRODUCTION")
                facts = clean.index("THE FACTS", intro)
                clean = clean[:intro] + clean[facts:]
            if len(clean) < 6000 and re.search(r"append(?:ed|ix).*?(?:table|list)|table.*?append", clean, re.I):
                html_path = cache / f"{key}.html"
                archive = cache.parent.parent / "hudoc_source_html.zip"
                if not html_path.exists() and not archive.exists():
                    unresolved.append({"item_id": key, "reason": "Factual appendix not yet retrieved"})
                else:
                    try:
                        if html_path.exists():
                            html = html_path.read_text(encoding="utf-8")
                        else:
                            with zipfile.ZipFile(archive) as saved:
                                html = saved.read(f"{key}.html").decode("utf-8")
                        details, included, excluded = extract(html, row["application_number"])
                        clean += "\n\nFACTUAL DETAILS FROM THE APPENDED TABLE\n" + details
                        table_record = {"included_columns": included, "omitted_columns": excluded,
                            "source_url": recovered[key]["source_url"], "facts_sha256": digest(details)}
                    except (ValueError, KeyError) as error:
                        unresolved.append({"item_id": key, "reason": str(error)})
        except ValueError as error:
            unresolved.append({"item_id": key, "reason": str(error)})
            clean, spans = old, []
        cleaned[key] = clean
        if old != clean:
            provenance.append({"item_id": key, "old_chars": len(old), "new_chars": len(clean),
                "old_sha256": digest(old), "new_sha256": digest(clean),
                "input_changed": old[:50000] != clean[:50000],
                "restored_from_hudoc": restore and key in recovered,
                "source_url": recovered[key]["source_url"] if restore and key in recovered else None,
                "introduction_removed": key in REMOVE_INTRODUCTION,
                "factual_appendix": table_record,
                "reviewed_boundary": REVIEWED_BOUNDARIES.get(key), "removed_spans": spans})
    proposed = [{**row, FIELD: cleaned[row["item_id"]]} for row in rows]
    assert len(proposed) == len(rows)
    for before, after in zip(rows, proposed):
        assert {k:v for k,v in before.items() if k != FIELD} == {k:v for k,v in after.items() if k != FIELD}
    return proposed, provenance, unresolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovered", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-commit", default=BASE_COMMIT,
                        help="Immutable pre-repair source revision, including after publication")
    args = parser.parse_args()
    rows = json.loads(subprocess.check_output(["git", "show", f"{args.base_commit}:data/processed/echr_unified.json"], cwd=ROOT))
    recovered = {}
    for path in args.recovered:
        recovered.update({r["item_id"]:r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())})
    proposed, changes, unresolved = prepare(rows, recovered, args.recovered[0].parent / ".cache" / "hudoc_html")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(proposed, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    appendix_ids = sorted({r["item_id"] for r in proposed
        if len(r[FIELD]) < 6000 and re.search(r"append(?:ed|ix).*?(?:table|list)|table.*?append", r[FIELD], re.I)})
    report = {"source_changes": len(changes), "model_inputs_changed": sum(c["input_changed"] for c in changes),
        "unresolved": unresolved, "appendix_recovery_ids": appendix_ids, "changes": changes}
    args.out.with_suffix(".provenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("changes", "appendix_recovery_ids")}, indent=2))
    print("Factual appendices:", sum(bool(c["factual_appendix"]) for c in changes))


if __name__ == "__main__":
    main()
