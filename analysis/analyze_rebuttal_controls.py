"""Audit the frozen rebuttal replay and summarize cases, not pseudo-replicates."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from syco_run import parse_score
sys.path.insert(0, str(ROOT / "analysis"))
from analyze_rebuttal_existing import cat, interval, write_json, write_csv


def read(path):
    with gzip.open(path, "rt", encoding="utf-8") as h:
        return [json.loads(line) for line in h]


def encoded(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def hierarchical(values):
    """Resample cases, then independent replicates within each case/condition."""
    n, conditions, repeats = values.shape
    rng = np.random.default_rng(20261107)
    cases = rng.integers(n, size=(5000, n))
    within = rng.integers(repeats, size=(5000, n, conditions, repeats))
    boot = np.take_along_axis(values[cases], within, axis=3).mean(axis=(1, 3)) * 100
    return values.mean(axis=(0, 2)) * 100, boot


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, default=ROOT / "data/experiments/rebuttal_20261107")
    ap.add_argument("--out", type=Path, default=ROOT / "analysis/rebuttal_20261107/new_controls")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.run / "manifest.json").read_text(encoding="utf-8"))
    manifest_hash = hashlib.sha256(encoded(manifest)).hexdigest()
    initial = {r["id"]: r for r in read(args.run / "initial_replay.jsonl.gz")}
    rows = read(args.run / "calls.jsonl.gz")
    calls = {r["call_id"]: r for r in rows}
    assert len(calls) == len(rows)
    jobs = {j["id"]: j for j in manifest["jobs"]}
    eligible_calls = {f"{j}|{t}" for j in jobs for t in (1, 2, 3)}
    assert set(calls) <= eligible_calls
    assert all(f"{j}|1" in calls for j in jobs), "Every planned trajectory must have been attempted"
    trajectory = {}
    observation = []
    checks = 0
    for job in jobs.values():
        start = initial[job["replay_id"]]
        assert parse_score(start["messages"][-1]["content"]) == start["initial_score"]
        messages = list(start["messages"])
        scores = []
        for t in (1, 2, 3):
            k = f"{job['id']}|{t}"
            messages.append({"role": "user", "content": job["challenges"][t-1]})
            if k not in calls:
                scores.extend([None] * (4-t))
                break
            r = calls[k]
            assert r["manifest_sha256"] == manifest_hash
            assert r["request"]["messages"] == messages
            assert r["request"]["model"] == start["model"]
            assert r["request"]["temperature"] == 1 and r["request"]["max_tokens"] == 1200
            assert not {"top_p", "reasoning", "reasoning_effort", "seed"}.intersection(r["request"])
            assert hashlib.sha256(encoded(r["request"])).hexdigest() == r["request_sha256"]
            choice = (r.get("response", {}).get("choices") or [{}])[0]
            content = choice.get("message", {}).get("content") or ""
            assert parse_score(content) == r["score"]
            assert r["initial_score"] == start["initial_score"]
            checks += 8
            scores.append(r["score"])
            messages.append({"role": "assistant", "content": content})
        identity = (start["model"], start["item_id"], start["article"], job["condition"], job["repetition"])
        complete = len(scores) == 3 and all(s is not None for s in scores)
        trajectory[identity] = {"scores": scores, "initial_score": start["initial_score"],
                                "label": start["label"], "complete": complete}
        observation.append({"model": start["model"], "item_id": start["item_id"], "article": start["article"],
            "condition": job["condition"], "repetition": job["repetition"], "complete": complete,
            "initial_score": start["initial_score"], "label": start["label"],
            **{f"turn_{t}": scores[t-1] for t in (1, 2, 3)}})
    assert len(trajectory) == len(jobs), "Duplicate trajectory identity"
    write_csv(args.out / "trajectories.csv", observation)
    all_keys = sorted({(r["item_id"], r["article"]) for r in initial.values()})
    assert len(all_keys) == manifest["sample_judgments"] == len({k[0] for k in all_keys})

    def get(model, k, cond, rep=0):
        return trajectory[(model, *k, cond, rep)]

    def reversal(row, t=3):
        return float(cat(row["scores"][t-1]) == -cat(row["initial_score"]))

    rates, contrasts, cohorts = [], [], []
    models = manifest["models"]
    for m in models:
        for c in manifest["conditions"]:
            complete_keys = [k for k in all_keys if get(m, k, c)["complete"]]
            for t in (1, 2, 3):
                vals = np.array([reversal(get(m, k, c), t) for k in complete_keys])
                missing = len(all_keys) - len(complete_keys)
                r = {"model": m, "condition": c, "repetition": 0, "turn": t,
                    "planned_n": len(all_keys), "complete_n": len(complete_keys), "missing_n": missing,
                    "reversed_n": int(vals.sum()),
                    "planned_lower_pct": 100 * vals.sum() / len(all_keys),
                    "planned_upper_pct": 100 * (vals.sum() + missing) / len(all_keys)}
                r.update({"reversal_pct" + ("" if f == "estimate" else "_" + f): v
                          for f, v in interval(vals * 100, complete_keys).items()})
                rates.append(r)
        for a, b in (("no_cue", "safety_researcher"), ("no_cue", "opinion_only"),
                     ("no_cue", "neutral_reassessment"), ("neutral_reassessment", "opinion_only"),
                     ("ai_researcher_neutral", "ai_researcher_evaluation")):
            keys = [k for k in all_keys if all(get(m, k, c)["complete"] for c in (a, b))]
            cohorts.extend({"model": m, "contrast": b + " minus " + a, "item_id": k[0], "article": k[1]} for k in keys)
            initial_correct = np.array([cat(get(m, k, a)["initial_score"]) ==
                (1 if get(m, k, a)["label"] == "violation" else -1) for k in keys])
            for t in (1, 2, 3):
                v0 = np.array([reversal(get(m, k, a), t) for k in keys])
                v1 = np.array([reversal(get(m, k, b), t) for k in keys])
                est = interval(100 * (v1 - v0), keys)
                contrasts.append({"model": m, "control": a, "treatment": b, "turn": t,
                    "planned_n": len(all_keys), "paired_n": len(keys), "control_reversed_n": int(v0.sum()),
                    "treatment_reversed_n": int(v1.sum()), "control_pct": float(100*v0.mean()),
                    "treatment_pct": float(100*v1.mean()), "delta_pct": est["estimate"], "lo": est["lo"], "hi": est["hi"],
                    "initial_correct_n": int(initial_correct.sum()),
                    "control_correct_reversed_n": int(v0[initial_correct].sum()),
                    "treatment_correct_reversed_n": int(v1[initial_correct].sum()),
                    "initial_wrong_n": int((~initial_correct).sum()),
                    "control_wrong_corrected_n": int(v0[~initial_correct].sum()),
                    "treatment_wrong_corrected_n": int(v1[~initial_correct].sum())})

    repetitions = []
    repetition_contrasts = []
    for m in models[:2]:
        R = manifest["repetitions_flagship_references"]
        pair = ("no_cue", "safety_researcher")
        keys = [k for k in all_keys if all(get(m, k, c, r)["complete"] for c in pair for r in range(R))]
        values = np.array([[[reversal(get(m, k, c, r)) for r in range(R)] for c in pair] for k in keys])
        means, boot = hierarchical(values)
        for ci, c in enumerate(pair):
            v = values[:, ci, :]
            repeat_rates = 100 * v.mean(axis=0)
            mixed = int(np.sum((v.sum(axis=1) > 0) & (v.sum(axis=1) < R)))
            judgments = np.array([[cat(get(m, k, c, r)["scores"][-1]) for r in range(R)] for k in keys])
            verdict_mixed = int(np.sum(judgments.max(axis=1) != judgments.min(axis=1)))
            repetitions.append({"model": m, "condition": c, "planned_cases": len(all_keys), "paired_cases": len(keys),
                "repetitions": R, "complete_trajectories_in_comparison": len(keys)*R,
                "reversed_n": int(v.sum()), "mean_reversal_pct": float(means[ci]),
                "lo": float(np.quantile(boot[:,ci], .025)), "hi": float(np.quantile(boot[:,ci], .975)),
                "repetition_rates_pct": json.dumps(repeat_rates.tolist()), "repetition_min_pct": float(repeat_rates.min()),
                "repetition_max_pct": float(repeat_rates.max()), "mixed_reversal_cases": mixed,
                "mixed_reversal_pct": mixed/len(keys)*100, "mixed_verdict_cases": verdict_mixed})
        delta = boot[:, 1] - boot[:, 0]
        repetition_contrasts.append({"model": m, "paired_cases": len(keys), "repetitions": R,
            "cue_delta_pct": float(means[1]-means[0]), "lo": float(np.quantile(delta,.025)), "hi": float(np.quantile(delta,.975))})
    write_csv(args.out / "condition_rates.csv", rates)
    write_csv(args.out / "paired_contrasts.csv", contrasts)
    write_csv(args.out / "paired_cohorts.csv", cohorts)
    write_csv(args.out / "repetition_variation.csv", repetitions)
    write_csv(args.out / "repetition_cue_contrasts.csv", repetition_contrasts)
    report = {"protocol": manifest["protocol"], "manifest_sha256": manifest_hash,
        "source_revision": manifest["source_revision"], "planned_judgments": len(all_keys),
        "planned_trajectories": len(jobs), "planned_max_calls": len(jobs)*3,
        "recorded_calls": len(rows), "complete_trajectories": sum(r["complete"] for r in trajectory.values()),
        "unparsed_calls": sum(r["score"] is None for r in rows), "http_errors": sum(r["http_status"] != 200 for r in rows),
        "reported_cost_usd": sum(r["charged_usd"] for r in rows if r["cost_basis"] == "reported_usage"),
        "conservative_charge_usd": sum(r["charged_usd"] for r in rows),
        "cost_bases": dict(Counter(r["cost_basis"] for r in rows)), "integrity_checks": checks,
        "first_request_utc": min(r["started_utc"] for r in rows), "last_request_utc": max(r["started_utc"] for r in rows),
        "returned_models": dict(Counter(r.get("response",{}).get("model","missing") for r in rows)),
        "providers": dict(Counter(r.get("response",{}).get("provider","unrecorded") for r in rows)),
        "reasoning_effort": "OpenRouter default; not set in requests", "temperature": 1.0,
        "max_tokens": 1200, "top_p": "OpenRouter default; not set in requests",
        "uncertainty": "Condition contrasts: paired source-judgment bootstrap, 2000 draws. Repeated references: 5000 hierarchical draws of cases then independent repetitions per condition.",
        "scope": "Static continuations conditional on fixed saved initial replies; separate collection window from the main experiment.",
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.run / "manifest.json", args.run / "initial_replay.jsonl.gz", args.run / "calls.jsonl.gz")}}
    write_json(args.out / "audit.json", report)
    print(json.dumps({k: report[k] for k in ("planned_trajectories", "complete_trajectories", "recorded_calls", "unparsed_calls", "reported_cost_usd", "integrity_checks")}))


if __name__ == "__main__":
    main()
