# How an update remains comparable

LiveHumanRightsBench releases are frozen snapshots produced by a refreshable
pipeline. The paper evaluates v1.0. A new model-result commit does not by itself
constitute a new dataset release.

## Source refresh, target construction and evaluation

1. **Retrieve candidates.** `scripts/hudoc_live_refresh.py` reads the latest
   decision date from an explicitly selected candidate corpus. It invokes
   `hudoc_scraper.py` with an overlap window and merges new judgment IDs.
   The optional full pipeline also invokes model-assisted verdict removal.
2. **Resolve and review targets.** Normalize dates, provisions and respondent
   countries. Resolve each outcome to its case, respondent, provision and issue.
   Review the model-visible source and summary. Candidate ingestion is automated;
   publication still requires these checks.
3. **Freeze a release.** Save the cohort, selection rule, input hashes and target
   audit in a new manifest. Retain the previous release unchanged. Derived
   paraphrase repairs also need a distinct input revision and matching scores.
4. **Apply the same evaluation contract.** Use the provision-specific question,
   original score thresholds and input limits. Record summaries, paraphrases,
   Country Swap exclusions and conversation starts before comparison. Preserve
   exact prompts, model/provider identifiers, settings and collection dates.
5. **Compare like with like.** Separate new-cohort findings from model-version
   changes by reevaluating a frozen anchor cohort in the same serving window.
   Report class/provision distributions and condition-specific denominators.

The released validator accepts a separately specified cohort manifest:

```bash
python scripts/validate_eval_dataset.py \
  --manifest <new-evaluation-manifest.json> --require-complete
```

It verifies unique target identities, dates, labels, exact summary coverage
and the target-scope audit. Text hashes and semantic source review are additional
release gates. A successful structural check is not a semantic validation.

## Existing-data verification

The [release-consistency report](../../analysis/rebuttal_20261107/existing/release_consistency.json)
recomputes the three v1.0 input hashes from committed bytes. All match the
frozen manifest. Reassembling the 943 pre-2026 targets with the 57 targets from
2026 exactly recovers v1.0 while preserving every earlier record. These sets
contain 892 and 55 distinct judgments respectively.

This is an offline chronological merge check of already released records.
It demonstrates the preservation invariant, not a live fetch or performance
on a new release. The [new-batch handoff](DELEGATED_TASKS.md) specifies the
remaining empirical test requested by EmoP.
