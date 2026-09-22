"""Compare both State Swap follow-ups on one cohort without pooling runs."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
spec = importlib.util.spec_from_file_location("uk_analysis", OUT.parent/"stateswap_uk"/"analyze.py")
uk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uk)
h = uk.h
MODELS = h.MODELS
RUNS = {"turkey": ("b35f6ca1b97017175fab7d9862d29a057529ec2f", ["Turkey", "Russia", "Ukraine"]),
        "uk": (uk.REVISION, ["UK", "Russia", "Ukraine"])}


def main():
    cohorts = {}
    for run in RUNS:
        with (OUT.parent/f"stateswap_{run}"/"cohort.csv").open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        cohorts[run] = {(r["item_id"],r["article"]) for r in rows if r["common"]=="True"}
    common = sorted(set.intersection(*cohorts.values()))
    records = {}
    for run,(revision,arms) in RUNS.items():
        h.REVISION=revision
        for m in MODELS:
            directory=f"data/experiments/stateswap_summary_{run}/"+m.replace("/","_")
            for line in h.read(directory+"/stateswap_summary_results.jsonl").splitlines():
                r=json.loads(line)
                key=(r["item_id"],r["article"])
                assert (run,m,key,r["arm"]) not in records
                records[run,m,key,r["arm"]]=r
            assert all((run,m,k,a) in records for k in common for a in ["original"]+arms)
    labels=[(run,m,a) for run,(_,arms) in RUNS.items() for m in MODELS for a in arms]
    shifts=np.array([[records[run,m,k,a]["avg_rating"]-records[run,m,k,"original"]["avg_rating"]
                      for run,m,a in labels] for k in common])
    effects=uk.interval_rows(common,shifts,[dict(run=r,model=m,arm=a) for r,m,a in labels],18)
    source=[]
    for i,(run,m,a) in enumerate(labels):
        values=[]
        for k in common:
            before,after=(records[run,m,k,arm]["avg_rating"] for arm in ["original",a])
            p,q=h.category(before),h.category(after)
            values.append([after-before,abs(after-before),100*(p!=q),100*(p*q==-1),
                           100*(p!=0 and q==0),100*(p==0 and q!=0)])
        values=np.asarray(values,float)
        limits=np.quantile(h.bootstrap(common,values),[.025,.975],axis=0)
        row=dict(run=run,model=m,arm=a,n=len(common),judgments=len({k[0] for k in common}))
        for j,metric in enumerate(h.METRICS):
            row.update({metric:values[:,j].mean(),metric+"_lo":limits[0,j],metric+"_hi":limits[1,j]})
        row.update(likelihood_shift_family18_lo=effects[i]["adjusted_lo"],likelihood_shift_family18_hi=effects[i]["adjusted_hi"])
        source.append(row)
    h.OUT=OUT
    h.write_csv("source_data.csv",source)
    h.write_csv("cohort.csv",[dict(item_id=k[0],article=k[1]) for k in common])
    manifest=dict(source_revisions={r:v[0] for r,v in RUNS.items()},new_model_calls=0,
        models=MODELS,destinations=["UK","Turkey","Russia","Ukraine"],
        comparisons=len(labels),common_targets=len(common),common_judgments=len({k[0] for k in common}),
        aggregation="Each effect uses the original arm of its own run. Repeated destinations are displayed separately.",
        bootstrap=dict(seed=731,pointwise_draws=2000,family_draws=20000,cluster="judgment",estimand="target-weighted mean"),
        source_audits=["analysis/stateswap_turkey/manifest.json","analysis/stateswap_uk/manifest.json"])
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    report=["# Both State Swap follow-ups", "",
        "The figure retains all 18 model-by-destination estimates from both follow-ups. The repeated Russia and Ukraine conditions are displayed separately. Each difference uses the original arm collected in the same run.", "",
        f"The common cohort contains {len(common)} targets from {manifest['common_judgments']} judgments with an actual substitution in all four destination countries.", "",
        "| Run | Model | Destination | Shift [95% CI] | Judgment change (%) | Strict reversal (%) |",
        "| --- | --- | --- | ---: | ---: | ---: |"]
    for r in source:
        report.append(f"| {r['run']} | {r['model'].split('/')[1]} | {r['arm']} | {r['likelihood_shift']:+.2f} [{r['likelihood_shift_lo']:+.2f}, {r['likelihood_shift_hi']:+.2f}] | {r['judgment_change_pct']:.2f} | {r['reversal_pct']:.2f} |")
    report += ["", "The original US experiment retains its own cohort and source tables. No records or previously reported runs are deleted. Destination-specific analysis and the original follow-up cohorts remain in their respective source directories.", "",
               "Reproduce with `python analysis/stateswap_followups/analyze.py` after generating both follow-up audits.", ""]
    (OUT/"REPORT.md").write_text("\n".join(report),encoding="utf-8")
    print(json.dumps(manifest,indent=2))
    for r in source:
        print(r["run"],r["model"],r["arm"],round(r["likelihood_shift"],3),
              round(r["likelihood_shift_family18_lo"],3),round(r["likelihood_shift_family18_hi"],3))


if __name__ == "__main__":
    main()
