# Work to assign separately

## Priority 1: Evaluate a genuinely new release

**Reviewer:** EmoP. **Status:** not completed by the current rebuttal runs.
The current results use v1.0. Its latest decision date is 21 May 2026.

**Data owner.** Collect eligible English-language ECtHR judgments with decision
dates after 21 May 2026 and record the retrieval date and HUDOC identifiers.
Use the source-refresh script on a separately pinned candidate corpus. Do not
overwrite the canonical v1.0 targets or use a deprecated Hub release as a
finished evaluation set.

```bash
python scripts/hudoc_live_refresh.py \
  --dataset <pinned-candidate-corpus.json> \
  --since-override 2026-05-22 \
  --output <new-candidates.json>
```

This command retrieves and processes candidates. The optional `--full-pipeline`
also invokes model verification and requires its own spending allocation.
Neither mode replaces target resolution or source review.

Resolve respondent, provision and issue against the published judgment. Review
the actual model-visible facts and selected summary for outcome leakage.
Retain ECLI, application number, decision date, target audit and text hashes.
Remove overlap with v1.0 by judgment ID, ECLI and application number. Freeze
the new cohort and its selection rule before reading any model predictions.

**Evaluation owner.** A focused starting cohort is 50 distinct new judgments.
Use every eligible target if fewer than 50 pass review and report the achieved
coverage. Keep the original prompts, thresholds and input limits. Reproduce
the full-record/summary comparison and the no-cue/researcher three-turn
comparison for Opus-4.6 and 5.6-Sol. Add the three paraphrase strengths only
if claiming that the paraphrase finding generalizes to the new release.
Use the new batch's original responses as the shared starts for its cues.

Run a small frozen v1.0 anchor cohort during the same serving window. This
separates changes in the case population from changes in the served models.
Do not treat the current continuation-only repetition run as a fresh baseline
accuracy run. Preserve the returned provider/model names and all decoding
settings. Budget the batch before collection; it is outside the current $50 cap.

**Acceptance artifacts.** Deliver a new release manifest, non-overlap report,
target/source review records, generated-input hashes and raw model responses.
Provide accuracy, balanced accuracy, input-change rates and cue reversal rates
with their own denominators. Report class and provision distributions rather
than assuming they match v1.0. Update EmoP's reply only after these results exist.

## Priority 2: Recover unpublished evidence if already available

The claim-level summary-coverage checkpoints and historical adaptive challenge
messages remain useful release artifacts. Recover the actual saved records
and verify their hashes. This task requires no model calls. Do not regenerate
them and label the replacements as historical evidence.

## Not required for this rebuttal

- A new defense model or fine-tuning study. Existing cue results already show
  why retaining a judgment can also retain an error; a validated defense is a
  separate contribution.
- Full-cohort repetitions, adaptive repetitions or a temperature sweep.
- More professional/nationality roles or a standalone unframed AI researcher arm.
- Another full paraphrase audit by a new generator or evaluator. The independent
  verifier records and the input-only sensitivity analysis are already available.

No new result on post-v1.0 judgments should be claimed until Priority 1 is done.
