"""Independently recount published time-window estimates from the source scores."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/model_time_windows"


def rows(name):
    with (OUT/name).open(encoding="utf-8",newline="") as handle:
        return list(csv.DictReader(handle))


def prediction(value):
    if value is None:
        return "missing"
    return "violation" if value > 60 else "no_violation" if value < 40 else "abstention"


def main():
    manifest = json.loads((OUT/"manifest.json").read_text())
    revision = manifest["source_revision"]
    def blob(path):
        return subprocess.check_output(["git","-C",str(ROOT),"show",f"{revision}:{path}"])
    release = json.loads((ROOT/"configs/releases/v1.0.json").read_text())
    for entry in release["inputs"]:
        assert hashlib.sha256(blob(entry["path"])).hexdigest() == entry["sha256"]
    for path, info in manifest["outputs"].items():
        assert hashlib.sha256((OUT/path).read_bytes()).hexdigest() == info["sha256"]
    cases = json.loads(blob("data/processed/echr_unified.json"))
    canonical = {(r["item_id"],str(r["article_full"])):r for r in cases}
    assert len(canonical) == 1000 and len({k[0] for k in canonical}) == 947
    assert len({r["article_full"] for r in cases}) == release["provisions"]
    assert len({r["target_respondent_code"] for r in cases}) == release["respondent_states"]
    assert min(r["decision_date"] for r in cases) == release["decision_date_min"]
    assert max(r["decision_date"] for r in cases) == release["decision_date_max"]
    cohorts = {}
    for r in rows("cohorts.csv"):
        kk = sorted(k for k,c in canonical.items() if r["first_case"] <= c["decision_date"] <= r["last_case"])
        assert len(kk) == int(r["targets"])
        assert len({k[0] for k in kk}) == int(r["judgments"])
        assert sum(canonical[k]["violation_label"] == "violation" for k in kk) == int(r["violation"])
        assert sum(canonical[k]["violation_label"] == "no_violation" for k in kk) == int(r["no_violation"])
        assert hashlib.sha256(json.dumps(kk,separators=(",", ":")).encode()).hexdigest() == r["target_keys_sha256"]
        cohorts[r["cohort"]] = kk
    scores, source_rows = {}, {}
    for r in rows("result_inventory.csv"):
        if r["path"] not in source_rows:
            source_rows[r["path"]] = [json.loads(line) for line in blob(r["path"]).splitlines() if line]
        if r["family"] in ("full_record", "summary"):
            scores[r["model"],r["family"]] = {(x["item_id"],str(x["article_full"])):x["avg_rating"] for x in source_rows[r["path"]]}
    for r in rows("performance.csv"):
        kk = cohorts[r["cohort"]]; s = scores[r["model"],r["input"]]
        right = [k for k in kk if prediction(s[k]) == canonical[k]["violation_label"]]
        vc = sum(canonical[k]["violation_label"] == "violation" for k in right)
        nc = len(right)-vc
        assert (len(right),vc,nc) == (int(r["correct"]),int(r["correct_violation"]),int(r["correct_no_violation"]))
        expected = dict(accuracy_pct=100*len(right)/len(kk),
            balanced_accuracy_pct=50*(vc/int(r["violation"])+nc/int(r["no_violation"])),
            abstention_pct=100*sum(prediction(s[k]) == "abstention" for k in kk)/len(kk),
            missing_pct=100*sum(prediction(s[k]) == "missing" for k in kk)/len(kk))
        assert all(abs(float(r[name])-value)<1e-10 for name,value in expected.items())
    point = {(r["cohort"],r["model"],r["input"]):r for r in rows("performance.csv")}
    for r in rows("paired_model_differences.csv"):
        a=point[r["cohort"],r["reference_model"],r["input"]]
        b=point[r["cohort"],r["comparison_model"],r["input"]]
        assert abs(float(r["difference_pp"])-(float(b[r["metric"]+"_pct"])-float(a[r["metric"]+"_pct"])))<1e-10
    for r in rows("perturbation_changes.csv"):
        kk=cohorts[r["cohort"]]
        if r["family"] == "summary":
            a,b=scores[r["model"],"full_record"],scores[r["model"],"summary"]
        else:
            path=next(x["path"] for x in rows("result_inventory.csv") if x["model"]==r["model"] and x["family"]=="paraphrase")
            pp=source_rows[path]
            a={(x["item_id"],str(x["article"])):x["avg_rating"] for x in pp if x["arm"]=="original"}
            b={(x["item_id"],str(x["article"])):x["avg_rating"] for x in pp if x["arm"]==r["arm"]}
        valid=[k for k in kk if a[k] is not None and b[k] is not None]
        changed=sum(prediction(a[k])!=prediction(b[k]) for k in valid)
        assert len(valid)==int(r["valid_pairs"]) and changed==int(r["changed_n"])
        harmed=sum(prediction(a[k])==canonical[k]["violation_label"] and prediction(b[k]) not in ("abstention",canonical[k]["violation_label"]) for k in valid)
        assert harmed==int(r["correct_to_wrong_n"])
    validation=dict(status="passed",source_revision=revision,release_input_hashes_verified=3,
        cohort_counts_and_membership_verified=len(cohorts),performance_rows_independently_recounted=len(rows("performance.csv")),
        paired_model_point_differences_verified=len(rows("paired_model_differences.csv")),perturbation_rows_independently_recounted=len(rows("perturbation_changes.csv")),
        output_hashes_verified=len(manifest["outputs"]),no_api_calls=True)
    (OUT/"VALIDATION.json").write_text(json.dumps(validation,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(validation))


if __name__ == "__main__":
    main()
