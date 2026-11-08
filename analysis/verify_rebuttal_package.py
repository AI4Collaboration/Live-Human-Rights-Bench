"""Check response coverage, evidence links and published control arithmetic offline."""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "analysis/rebuttal_20261107"


def rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def exists(path):
    if path.exists():
        return True
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    return subprocess.run(["git", "cat-file", "-e", "HEAD:" + relative], cwd=ROOT,
                          capture_output=True).returncode == 0


def main():
    tracker = rows(ROOT / "docs/rebuttal/review_tracker.csv")
    expected = {f"FTor-{i}" for i in range(1, 5)} | {f"j8sk-{i}" for i in range(1, 4)} | {f"EmoP-{i}" for i in range(1, 6)}
    assert len(tracker) == len(expected) and {r["id"] for r in tracker} == expected
    pending = [r["id"] for r in tracker if r["status"].startswith("delegated")]
    assert pending == ["EmoP-5"]
    response = (ROOT / "docs/rebuttal/RESPONSES.md").read_text(encoding="utf-8")
    assert all(r["id"] in response for r in tracker)
    links = 0
    for row in tracker:
        for field in ("response", "evidence"):
            assert exists(ROOT / "docs/rebuttal" / row[field].split("#")[0]), row
            links += 1
    for path in [ROOT / "README.md", BASE / "REPORT.md", *(ROOT / "docs/rebuttal").glob("*.md")]:
        text = path.read_text(encoding="utf-8")
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in link or link.startswith("#"):
                continue
            assert exists(path.parent / link.split("#")[0]), (path.name, link)
            links += 1
    arithmetic = 0
    contrasts = rows(BASE / "new_controls/paired_contrasts.csv")
    for row in contrasts:
        n = int(row["paired_n"])
        a, b = int(row["control_reversed_n"]), int(row["treatment_reversed_n"])
        for actual, target in ((float(row["control_pct"]), 100*a/n),
                               (float(row["treatment_pct"]), 100*b/n),
                               (float(row["delta_pct"]), 100*(b-a)/n)):
            assert abs(actual-target) < 1e-9
            arithmetic += 1
        assert int(row["initial_correct_n"]) + int(row["initial_wrong_n"]) == n
        assert int(row["control_correct_reversed_n"]) + int(row["control_wrong_corrected_n"]) == a
        assert int(row["treatment_correct_reversed_n"]) + int(row["treatment_wrong_corrected_n"]) == b
    repeats = rows(BASE / "new_controls/repetition_variation.csv")
    for row in repeats:
        n, r = int(row["paired_cases"]), int(row["repetitions"])
        assert abs(float(row["mean_reversal_pct"])-100*int(row["reversed_n"])/(n*r)) < 1e-9
        assert abs(float(row["mixed_reversal_pct"])-100*int(row["mixed_reversal_cases"])/n) < 1e-9
        arithmetic += 2
    audit = json.loads((BASE / "new_controls/audit.json").read_text(encoding="utf-8"))
    run = ROOT / "data/experiments/rebuttal_20261107"
    secret = re.compile(rb"sk-or-v1-[A-Za-z0-9]{24,}")
    for name, digest in audit["files"].items():
        path = run / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rb") as handle:
            for line in handle:
                assert not secret.search(line), f"Credential detected in {name}"
    tracked = [ROOT / "docs/rebuttal/RESPONSES.md", ROOT / "docs/rebuttal/review_tracker.csv",
               BASE / "REPORT.md", BASE / "new_controls/paired_contrasts.csv",
               BASE / "new_controls/repetition_variation.csv"]
    report = {"review_points": len(tracker), "unanswered_points": 0,
              "delegated_empirical_points": pending, "verified_local_links": links,
              "arithmetic_checks": arithmetic, "raw_artifact_hashes_match": True,
              "credential_scan_passed": True,
              "source_sha256_lf": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in tracked}}
    (BASE / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "source_sha256_lf"}))


if __name__ == "__main__":
    main()
