"""Lay the regenerated rows over paraphrase_texts.jsonl.gz.

    python quality_control/paraphrase/regen/merge_texts.py \
        data/processed/paraphrase_texts.jsonl.gz data/processed/paraphrase_texts_regen_cut.jsonl.gz \
        <merged.jsonl.gz> <subset.jsonl.gz>

The merged file is the full set with the cut targets replaced, for the number check.
The subset holds every target of the affected judgments, for the claim check, which
runs per judgment. Originals must match exactly; the script stops otherwise.
"""
import argparse
import gzip
import json
from pathlib import Path


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)


def key(row):
    return row["item_id"], row["article"], row["condition"]


def merge_texts(base, regen, merged, subset):
    """Validate the repair before writing two new files; preserve original text."""
    base, regen, merged, subset = map(Path, (base, regen, merged, subset))
    paths = (base, regen, merged, subset)
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("Input and output paths must all be distinct")
    for path in (merged, subset):
        if path.exists():
            raise FileExistsError(f"Output already exists: {path}")

    replacements = {}
    for row in rows(regen):
        identity = key(row)
        if identity in replacements:
            raise ValueError(f"Duplicate regenerated row: {identity}")
        replacements[identity] = row

    seen = set()
    replaced = 0
    for row in rows(base):
        identity = key(row)
        if identity in seen:
            raise ValueError(f"Duplicate base row: {identity}")
        seen.add(identity)
        if identity in replacements:
            changed = row["text"] != replacements[identity]["text"]
            if row["condition"] == "original" and changed:
                raise ValueError(f"Original text changed: {identity}")
            replaced += int(changed)
    unknown = replacements.keys() - seen
    if unknown:
        raise ValueError(f"Regenerated rows absent from base: {len(unknown)}")

    items = {identity[0] for identity in replacements}
    # Exclusive creation prevents accidentally overwriting any existing artifact.
    with merged.open("xb") as merged_file, subset.open("xb") as subset_file, \
            gzip.open(merged_file, "wt", encoding="utf-8", newline="\n") as full, \
            gzip.open(subset_file, "wt", encoding="utf-8", newline="\n") as affected:
        for row in rows(base):
            row = replacements.get(key(row), row)
            output = json.dumps(row, ensure_ascii=False) + "\n"
            full.write(output)
            # Claim checks cover all targets of each affected judgment.
            if row["item_id"] in items:
                affected.write(output)
    return replaced, len(items)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("regen", type=Path)
    parser.add_argument("merged", type=Path, help="New file for the full repaired set")
    parser.add_argument("subset", type=Path, help="New file for affected judgments")
    args = parser.parse_args()
    replaced, judgments = merge_texts(args.base, args.regen, args.merged, args.subset)
    print("replaced paraphrase rows:", replaced, "judgments in subset:", judgments)


if __name__ == "__main__":
    main()
