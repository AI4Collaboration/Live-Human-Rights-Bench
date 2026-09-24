"""Audit country-substitution context and rescore saved outputs without API calls.

The lexical screen is an outcome-independent sensitivity analysis. Unflagged
texts have not been certified as geographically or legally transferable.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA_REV = "d282acc0e40e058617e66de26f072bafae9ff162"
RUNS = {
    "us": ("4b231e17e6dd65880e665c5fe298db3862ff5ade", "stateswap_summary",
           ["US", "Russia", "Ukraine"]),
    "turkey": ("b35f6ca1b97017175fab7d9862d29a057529ec2f", "stateswap_summary_turkey",
               ["Turkey", "Russia", "Ukraine"]),
    "uk": ("05b96bf53698e503f18f25bd44c3a66f47b67d20", "stateswap_summary_uk",
           ["UK", "Russia", "Ukraine"]),
}
MODELS = {
    "us": ["anthropic/claude-opus-4.6", "openai/gpt-5.6-sol",
           "deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash",
           "qwen/qwen3-235b-a22b", "qwen/qwen3-32b"],
    "followups": ["openai/gpt-4o-mini", "openai/gpt-4.1-mini", "openai/gpt-5.6-sol"],
}
# Fixed from the review concern and input inspection before looking at subset scores.
# Flags identify text to review, not confirmed errors. Overlapping categories are retained.
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
INPUTS = {}


def read(revision, path):
    raw = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{revision}:{path}"])
    normalized = raw.replace(b"\r\n", b"\n")
    INPUTS[f"{revision}:{path}"] = {
        "bytes": len(raw), "sha256_git_bytes": hashlib.sha256(raw).hexdigest(),
        "sha256_lf": hashlib.sha256(normalized).hexdigest(),
    }
    return normalized.decode("utf-8")


def pure_swap(revision):
    ns = {"re": re}
    tree = ast.parse(read(revision, "experiments/stateswap_summary_run.py"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"COUNTRIES", "TARGETS", "TARGET_SETS"}:
                    try:
                        ns[target.id] = ast.literal_eval(node.value)
                    except ValueError:
                        pass  # TARGETS = TARGET_SETS[...] is set explicitly below.
        elif isinstance(node, ast.FunctionDef) and node.name == "swap":
            exec(compile(ast.Module(body=[node], type_ignores=[]), "pure_swap", "exec"), ns)
    return ns


def matches(text, pattern):
    return sorted({m.group(0) for m in re.finditer(pattern, text, re.I)}, key=str.casefold)


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def bootstrap(keys, values, draws=20000):
    unique, inverse = np.unique([k[0] for k in keys], return_inverse=True)
    sums = np.zeros((len(unique), values.shape[1]))
    np.add.at(sums, inverse, values)
    counts = np.bincount(inverse)
    rng = np.random.default_rng(731)
    batches = []
    for start in range(0, draws, 256):
        idx = rng.integers(0, len(unique), (min(256, draws-start), len(unique)))
        batches.append(sums[idx].sum(axis=1) / counts[idx].sum(axis=1)[:, None])
    return np.concatenate(batches)


def category(score):
    return 1 if score > 60 else -1 if score < 40 else 0


def main():
    cases_path = "data/processed/echr_unified.json"
    summaries_path = "data/processed/summaries_dsv41flash.json"
    case_text = read(DATA_REV, cases_path)
    summary_text = read(DATA_REV, summaries_path)
    cases = json.loads(case_text)
    summaries = json.loads(summary_text)["summaries"]
    case_map = {(c["item_id"], c["article_full"]): c for c in cases}
    assert len(case_map) == 1000 and len(summaries) == 947
    ns = pure_swap(DATA_REV)
    countries = ns["COUNTRIES"]
    ns["TARGETS"] = {k: v for group in ns["TARGET_SETS"].values() for k, v in group.items()}
    flags = {}
    for key, c in sorted(case_map.items()):
        text = summaries[key[0]][0]
        respondent = c["target_respondent"]
        rule_hits = {name: matches(text, pattern) for name, pattern in RULES.items()}
        collisions = []
        for arm, terms in DESTINATION_TERMS.items():
            if countries[respondent][1] == ns["TARGETS"][arm][1]:
                continue
            if any(re.search(r"(?<!\w)"+re.escape(term)+r"(?!\w)", text, re.I) for term in terms):
                collisions.append(arm)
        flags[key] = dict(item_id=key[0], article=key[1], respondent=respondent,
                          **{name: "; ".join(hits) for name, hits in rule_hits.items()},
                          destination_already_present="; ".join(collisions),
                          us_screen_flagged=any(rule_hits.values()) or bool(set(collisions) & set(RUNS["us"][2])),
                          followup_screen_flagged=any(rule_hits.values()) or bool(set(collisions) & {"UK","Turkey","Russia","Ukraine"}),
                          summary_sha256=hashlib.sha256(text.encode()).hexdigest())

    records = {}
    for run, (rev, folder, arms) in RUNS.items():
        assert read(rev, cases_path) == case_text
        assert read(rev, summaries_path) == summary_text
        old = pure_swap(rev)
        assert old["COUNTRIES"] == countries
        if "TARGET_SETS" in old:
            old["TARGETS"] = old["TARGET_SETS"][run]
        assert all(old["swap"](summaries[k[0]][0], c["target_respondent"], a) ==
                   ns["swap"](summaries[k[0]][0], c["target_respondent"], a)
                   for k, c in case_map.items() for a in arms)
        for model in MODELS["us" if run == "us" else "followups"]:
            path = f"data/experiments/{folder}/{model.replace('/', '_')}/stateswap_summary_results.jsonl"
            rows = [json.loads(line) for line in read(rev, path).splitlines() if line.strip()]
            assert len(rows) == 4000
            for row in rows:
                key, arm = (row["item_id"], row["article"]), row["arm"]
                assert key in case_map and arm in ["original"]+arms
                assert row["avg_rating"] is not None
                index = run, model, key, arm
                assert index not in records
                records[index] = row["avg_rating"]

    def changed(key, arm):
        c = case_map[key]
        return (countries[c["target_respondent"]][1] != ns["TARGETS"][arm][1]
                and ns["swap"](summaries[key[0]][0], c["target_respondent"], arm) != summaries[key[0]][0])

    common_us = sorted(k for k in case_map if all(changed(k, arm) for arm in RUNS["us"][2]))
    common_followups = sorted(k for k in case_map if all(changed(k, arm) for arm in ["Turkey", "UK", "Russia", "Ukraine"]))
    assert len(common_us) == 800
    assert len(common_followups) == 768
    recorded = list(csv.DictReader(io.StringIO(read(DATA_REV, "analysis/stateswap_followups/cohort.csv"))))
    assert set(common_followups) == {(r["item_id"], r["article"]) for r in recorded}
    for k in flags:
        flags[k]["original_us_cohort"] = k in common_us
        flags[k]["followup_cohort"] = k in common_followups
    write_csv("input_flags.csv", list(flags.values()))

    effects, cohorts = [], {}
    for group, keys, flag_field, runs in [
        ("us", common_us, "us_screen_flagged", ["us"]),
        ("followups", common_followups, "followup_screen_flagged", ["turkey", "uk"]),
    ]:
        labels = [(run, m, a) for run in runs for m in MODELS[group] for a in RUNS[run][2]]
        kept = [k for k in keys if not flags[k][flag_field]]
        cohorts[group] = {
            "full_targets": len(keys), "full_judgments": len({k[0] for k in keys}),
            "flagged_targets": len(keys)-len(kept), "remaining_targets": len(kept),
            "remaining_judgments": len({k[0] for k in kept}),
            "flagged_by_rule": {name: sum(bool(flags[k][name]) for k in keys) for name in RULES},
            "destination_already_present_targets": sum(bool(set(flags[k]["destination_already_present"].split("; ")) &
                {a for r in runs for a in RUNS[r][2]}) for k in keys),
        }
        for scope, subset in [("full", keys), ("screen_remaining", kept)]:
            before = np.array([[records[r,m,k,"original"] for r,m,a in labels] for k in subset])
            after = np.array([[records[r,m,k,a] for r,m,a in labels] for k in subset])
            shifts = after-before
            samples = bootstrap(subset, shifts)
            pointwise = np.quantile(samples[:2000], [.025, .975], axis=0)
            adjusted = np.quantile(samples, [.05/(2*len(labels)), 1-.05/(2*len(labels))], axis=0)
            bcat = np.where(before>60,1,np.where(before<40,-1,0))
            acat = np.where(after>60,1,np.where(after<40,-1,0))
            for j, (run, model, arm) in enumerate(labels):
                effects.append(dict(group=group, scope=scope, run=run, model=model, arm=arm,
                    n=len(subset), judgments=len({k[0] for k in subset}),
                    likelihood_shift=shifts[:,j].mean(), lo=pointwise[0,j], hi=pointwise[1,j],
                    family18_lo=adjusted[0,j], family18_hi=adjusted[1,j],
                    judgment_change_pct=100*np.mean(bcat[:,j]!=acat[:,j]),
                    reversal_pct=100*np.mean(bcat[:,j]*acat[:,j]==-1)))
    # Reproduce every published follow-up point estimate before reporting subsets.
    published = list(csv.DictReader(io.StringIO(read(DATA_REV, "analysis/stateswap_followups/source_data.csv"))))
    for p in published:
        r = next(r for r in effects if r["group"]=="followups" and r["scope"]=="full"
                 and (r["run"],r["model"],r["arm"]) == (p["run"],p["model"],p["arm"]))
        for field in ["likelihood_shift", "judgment_change_pct", "reversal_pct"]:
            assert abs(r[field]-float(p[field])) < 1e-10
    write_csv("sensitivity.csv", effects)

    examples = []
    for item_id, arm, start, stop, issue in [
        ("001-240242", "Turkey", "concerns the alleged", "May 2019", "Origin and destination of a cross-border pushback become the same country."),
        ("001-108607", "Russia", "were arrested in Russia", "extradited to Moldova", "Extradition from Russia to Moldova becomes extradition from Russia to Russia."),
        ("001-174413", "UK", "It found the land was part", "legally impossible.", "Ohrid lakeshore and the local statutory setting remain after the respondent is changed to the UK."),
    ]:
        c = next(c for c in cases if c["item_id"]==item_id)
        text = summaries[item_id][0]
        i = text.index(start)
        j = text.index(stop, i)+len(stop)
        excerpt = text[i:j]
        transformed = ns["swap"](text,c["target_respondent"],arm)
        transformed_excerpt = ns["swap"](excerpt,c["target_respondent"],arm)
        assert transformed_excerpt in transformed
        examples.append(dict(item_id=item_id, case_name=c["case_name"].strip(),
            article=c["article_full"], respondent=c["target_respondent"], destination=arm,
            in_followup_cohort=(item_id,c["article_full"]) in common_followups,
            original_excerpt=excerpt, substituted_excerpt=transformed_excerpt,
            issue=issue, source_url=f"https://hudoc.echr.coe.int/eng?i={item_id}",
            original_sha256=hashlib.sha256(text.encode()).hexdigest(),
            substituted_sha256=hashlib.sha256(transformed.encode()).hexdigest()))
    (OUT/"examples.json").write_text(json.dumps(examples,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest = dict(data_revision=DATA_REV, new_model_calls=0, input_targets=1000,
        input_judgments=947, selected_summary_version=0, summary_inputs_identical_across_runs=True,
        swap_reconstructed_for_all_targets_and_runs=True, followup_estimates_reproduced=18,
        nigeria_respondents=sum(c["target_respondent"]=="Nigeria" for c in cases),
        nigeria_mentioned_judgments=sum(bool(re.search(r"\bNigerian?\b",v[0],re.I)) for v in summaries.values()),
        rules=RULES, destination_terms=DESTINATION_TERMS, cohorts=cohorts,
        interpretation="Lexical flags select inputs for review. Neither flag prevalence nor the remaining subset estimates a validated invalid-input rate.",
        bootstrap=dict(cluster="judgment",seed=731,pointwise_draws=2000,family_draws=20000,
                       family_comparisons=18,estimand="target-weighted mean"), inputs=INPUTS)
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report = ["# Country Swap context audit", "",
        "## Finding", "",
        "Country substitution is not always a coherent counterfactual. The runner used for the published experiments replaced every respondent-country alias and demonym. It retained named locations, institutions, domestic law and cross-border relationships without a context check.", "",
        "The audit reconstructs the exact selected summaries and transformations for all 1,000 targets from 947 judgments. Inputs are identical across the original US run and both follow-ups. There are no Nigerian respondents, but five selected summaries mention Nigeria or Nigerian nationality as part of another respondent's case.", "",
        "## Verified examples", "",
    ]
    for e in examples:
        report += [f"### {e['case_name']} ({e['item_id']})", "",
                   f"- Destination: {e['destination']}. Included in the published 768-target follow-up cohort.",
                   f"- Original: {e['original_excerpt']}",
                   f"- Substituted: {e['substituted_excerpt']}", f"- Interpretation: {e['issue']}",
                   f"- [HUDOC source]({e['source_url']}). Exact input and transformed-text hashes are in `examples.json`.", ""]
    report += ["## Offline sensitivity analysis", "",
        "The screen was specified from the review concern and input inspection before examining subset scores. It flags environment-related terms, cross-border events, territorial conflicts and a destination already mentioned in the original summary. The same retained targets are used for every model and destination within each comparison family.", "",
        "These are review flags, not confirmed-invalid labels. A lake or an asylum claim does not by itself make a substitution impossible. Conversely, unflagged texts can still retain incompatible locations or institutions. The restricted comparison measures sensitivity to removing these identifiable contexts; it does not establish a clean country-identity effect.", "",
        "| Comparison | Full targets | Flagged targets | Remaining targets | Remaining judgments |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for name,c in cohorts.items():
        report.append(f"| {name} | {c['full_targets']} | {c['flagged_targets']} | {c['remaining_targets']} | {c['remaining_judgments']} |")
    followup_pairs = [(r, next(x for x in effects if x["scope"]=="full" and
        (x["run"],x["model"],x["arm"])==(r["run"],r["model"],r["arm"])))
        for r in effects if r["group"]=="followups" and r["scope"]=="screen_remaining"]
    same_direction = sum(np.sign(r["likelihood_shift"])==np.sign(x["likelihood_shift"])
                         for r,x in followup_pairs)
    uk_remaining = [r for r,x in followup_pairs if r["arm"]=="UK"]
    us_remaining = [r for r in effects if r["scope"]=="screen_remaining" and r["arm"]=="US"]
    assert same_direction==18 and all(r["family18_hi"]<0 for r in uk_remaining)
    assert len(us_remaining)==6 and all(r["likelihood_shift"]<0 for r in us_remaining)
    report += ["",
        "All 18 follow-up point estimates retain their original directions on the 574 remaining targets. UK substitution still lowers scores for all three models with intervals below zero after correction across 18 comparisons. Russia and Ukraine still raise both mini models' scores. GPT-5.6-sol retains negative Ukraine estimates, although their adjusted intervals include zero. The original US experiment also retains negative estimates in all six models on 606 remaining targets. This screen therefore preserves the main directional pattern while leaving the interpretation as contextual sensitivity.", "",
        "| Run | Model | Destination | Full shift | Remaining shift [95% CI] |",
               "| --- | --- | --- | ---: | ---: |"]
    for r in effects:
        if r["scope"]!="screen_remaining":
            continue
        original=next(x for x in effects if x["scope"]=="full" and (x["run"],x["model"],x["arm"])==(r["run"],r["model"],r["arm"]))
        report.append(f"| {r['run']} | {r['model'].split('/')[1]} | {r['arm']} | {original['likelihood_shift']:+.2f} | {r['likelihood_shift']:+.2f} [{r['lo']:+.2f}, {r['hi']:+.2f}] |")
    report += ["", "Shifts are percentage points relative to the original arm from the same run. Intervals resample judgments and retain the target-weighted mean. `sensitivity.csv` also provides Bonferroni-adjusted intervals across each family's 18 comparisons and categorical-change rates. Original inputs, outputs and published estimates remain intact.", "",
        "## Pipeline integration", "",
        "Report these experiments as contextual sensitivity to textual country substitution. Do not treat every transformed case as fact-preserving or give it the original case's reference verdict. The absence of an original-label accuracy calculation already avoids the second error; this audit addresses the distinct input-coherence issue.", "",
        "The Country Swap runner now applies this screen before model calls. It writes `context_manifest.json` with every target, its eligibility, exclusion reasons and input hashes. Use `--preflight-only` to inspect the manifest without an API key. `--validity-targets uk turkey` reproduces the 574-target shared follow-up cohort. New context-checked runs cannot resume older unscreened checkpoints. Historical inputs and scores remain unchanged.", "",
        "Reproduce offline with `python analysis/stateswap_context/audit.py`. No model API is imported or called. `input_flags.csv` retains every target and the exact flag terms; `manifest.json` pins all data and score inputs.", ""]
    (OUT/"REPORT.md").write_text("\n".join(report),encoding="utf-8")
    print(json.dumps({"cohorts":cohorts,"examples":len(examples),"new_model_calls":0},indent=2))


if __name__ == "__main__":
    main()
