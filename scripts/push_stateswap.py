import json
from collections import Counter
from datasets import Dataset
from huggingface_hub import HfApi

REPO = "overthelex/echr-livehrb-stateswap"
rows = [json.loads(l) for l in open("data/processed/livehrb_stateswap_final.jsonl")]
nbase = len({r["swap_group_id"] for r in rows})
arms = dict(Counter(r["arm"] for r in rows))
ds = Dataset.from_list(rows)
ds.push_to_hub(REPO, commit_message=(
    "LSYC-43 state-swap counterfactual set: 4 arms (original/Iceland/Ukraine/Russia) "
    "per case, anonymize-then-fill, facts held fixed"))

card = """---
license: cc-by-4.0
task_categories:
- text-classification
language:
- en
tags:
- legal
- echr
- human-rights
- verdict-free
- counterfactual
- state-swap
size_categories:
- 1K<n<10K
---

# echr-livehrb-stateswap

State-swap counterfactual set for **LiveHumanRightsBench** (experiment 6). Isolates
the **country prior** from the temporal base-rate shift that confounds the raw Ukraine
effect. Built from the 001-only canonical `echr-livehrb-static-2k` (regular, substantive
articles). Facts are held fixed; only the respondent state identity varies.

## Design (anonymize-then-fill)

Respondent-state identity is detected (country, demonym, cities, courts, authorities)
and templated to `[DEFENDANT STATE]` / `[DEFENDANT STATE ADJ]`, then **filled into the
body** per arm. The swapped country reads naturally in the fact pattern (no separate
prompt field). Applicant identity is held constant across arms.

## Arms (4 per case, shared `swap_group_id`)

| arm | respondent | role |
|-----|-----------|------|
| `control_original` | real respondent state | ground-truth arm (`violation_label` applies) |
| `control_neutral`  | Iceland | low-prior / low-salience control |
| `probe_ukraine`    | Ukraine | Ukraine-specific prior under test |
| `probe_russia`     | Russia | high-violation-prior control (UA-specific vs generic adversarial-state prior) |

**%d base cases x 4 arms = %d rows.** Arm counts: %s.

## Scoring

Score `case_text_rendered` (the arm's filled body). `violation_label` is the gold target,
carried unchanged from the canonical case across all arms. Pair by `swap_group_id`:
- delta(probe_ukraine - control_neutral) = the UA prior (headline)
- delta(control_original - control_neutral) = the real-state prior (calibration)
- delta(probe_russia - control_neutral) = generic adversarial-state prior
Bucket per `article_full` (substantive only here). Null hypothesis (model reasons from
facts): the call does not move across arms; any movement is a country prior.

## Scope / exclusions (base pool 907 -> 816)

- ex-Ukraine, single-respondent CoE states, substantive `article_full` only.
- Excluded cases whose real respondent is a swap target (Iceland/Russia) to avoid
  degenerate arms (-40).
- Dropped cases where the applicant's own nationality is legally material
  (expulsion / Art. 3 refoulement / Art. 8), which cannot be country-swapped (-47).
- 4 pathological long judgments whose identity-span list did not fit the detector's
  output budget (documented, not silent).

## Columns

swap_group_id, item_id, arm, respondent, respondent_adj, case_text_templated,
case_text_rendered (**score this**), article_full, article, violation_label (**gold**),
respondent_original, anonymization_report, case_name, application_number, ecli.

Public HUDOC sources only -> redistributable. Verdict-free (contamination-controlled).
""" % (nbase, len(rows), arms)

HfApi().upload_file(path_or_fileobj=card.encode(), path_in_repo="README.md",
                    repo_id=REPO, repo_type="dataset", commit_message="Add dataset card")
print("PUSHED", REPO, "base:", nbase, "rows:", len(rows), "arms:", arms)
