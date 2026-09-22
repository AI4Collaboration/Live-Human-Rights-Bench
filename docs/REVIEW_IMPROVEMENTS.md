# Review assessment and improvements

Status checked 21 September 2026 against the published results at GitHub
revision `340ef57` and manuscript revision `4a76cfe`.
The review identifies useful controls for the role-cue result and conversational
sampling. Its suggestions vary in relevance; they are not all missing experiments.
The [merged API plan](NEXT_EXPERIMENTS.md) is summarized at the top of the README.
The experiment scope below was updated on 22 September 2026.
No API experiments or new human annotation were performed for this revision.

## Highest-value additions

| Issue | Assessment | Action |
| --- | --- | --- |
| AI researcher versus AI safety researcher | Compares the distinctive wording in the headline finding | Collect the AI-researcher branch and reuse valid saved AI-safety references |
| Single conversation per condition | Existing judgment bootstrap measures variation across cases, not repeated conversations | Budget full-cohort reference repetitions separately after the core batch |
| Low-temperature continuation | The review raises a testable alternative explanation; the direction of a temperature effect has not been measured | Define coverage after the core results and preserve the saved initial replies |
| Neutral reassessment | Measures judgment revision without an opposing opinion | Use one no-pressure control and compare it with saved no-cue challenges |
| Explicit evaluation framing | Tests the response to evaluation-related wording with the AI researcher role held fixed | Compare two branches: neutral framing and evaluation framing |
| Scoring-threshold sensitivity | Important and computable from saved scores | Completed [offline analysis](../analysis/threshold_sensitivity/REPORT.md), with frozen cohorts and explicit score-50 tie rules |
| Continuous probability-score accuracy | Complements the threshold checks without assigning every uncertain score a full classification error | Completed [paired Brier-score analysis](../analysis/review_offline/REPORT.md) from saved scores; reported in Section 5 and Appendix C |
| Multiple comparisons | Simultaneous intervals distinguish family-level from pointwise support | Completed [five-family sensitivity analysis](../analysis/review_offline/REPORT.md), with effect sizes retained; Appendix C describes the procedure |
| Conversation protocol visibility | State the settings and distinguish averaged fixed-input scores from individual dialogue turns | Implemented in Section 5 and Appendices C/E: temperature, response budgets, challenge length and trajectory handling |
| Close multi-turn prior work | TRUTH DECAY and SYCON-Bench are direct antecedents | Included in Related Work; the comparison focuses on judgment correctness and persistence under input changes and adversarial opinions |

The first static batch uses GPT-5.6-sol and Claude Opus 4.6 alongside the
lower-performing DeepSeek V4 Flash. Their eligible saved initial replies
number 978 for GPT and 918 for Claude plus 926 for DeepSeek.
The AI-researcher and neutral-reassessment conditions cost **16,932 target replies**.
Two evaluation-framing conditions add **16,932** for a planned total
of **33,864**. No cue and AI safety researcher are completed reference conditions.
A separate five-trajectory reference study would cost **84,660** replies and
requires its own budget decision. Nationality-only cues and broader input extensions
are deferred to future work. AI researcher is the only new professional role
in the core plan. Nationality is not crossed with professional roles.

## Contribution and evidence priorities

Preserve the construction pipeline, systematic perturbations and adversarial
opinion as the three contributions. The connected result is that aggregate
accuracy hides offsetting corrections and errors, challenger identity changes
judgments on fixed case evidence, and early mistakes often persist. Lower
reversal alone can also preserve an initially wrong answer. These findings
should guide the additions; the review does not require a new mitigation paper.

Metadata shifts show sensitivity to respondent context. Summarization changes
available evidence. Neither experiment alone makes every judgment change an
error. The clearest evidence of harmful volatility comes from correctness
transitions and challenges that keep the case fixed. Keep that distinction in
the Results interpretation without adding a limitations paragraph to each result.

## Completed improvements without model calls

1. **Continuous scores.** Added paired Brier errors for summary, three paraphrase
   strengths, every dialogue turn and the shared-case cue comparison. Numeric
   abstentions remain included; tables identify missing paired scores. The
   original label is not reused as ground truth for jurisdiction-changing arms.
2. **Multiple comparisons.** Fixed five contrast families before computation,
   then obtained Bonferroni-adjusted judgment-cluster intervals from 20,000
   draws. Pointwise intervals remain labeled separately.
3. **Protocol visibility.** Added short static challenge examples, clarified
   three assembly generations versus four transport attempts, and documented
   failed trajectories and saved-message coverage. Expanded the existing
   source-review accounting without claiming a measured zero-leakage rate.
4. **Related-work structure.** The current paragraphs cover living benchmarks,
   systematic perturbation, and adversarial opinion and sycophancy. They include
   TRUTH DECAY, SYCON-Bench, ICE-Guard and EvalAwareBench. TriBench-Ko and ECtHR-PCR
   remain verified background references and are not cited in the current text.

The [completed analysis](../analysis/review_offline/REPORT.md) covers 32
systematic comparisons, 36 model-mode-turn comparisons, 38 family-adjusted
contrasts and the shared-case role effect. All twelve final conversational
Brier changes are positive (0.114-0.544), including after correction. Summary
and paraphrase changes are small and mixed in direction. Five of six US shifts
retain adjusted intervals below zero; Claude's interval includes zero. All
destination-order, pressure-interaction and shared-role-gap contrasts retain
their direction. The manuscript adds one compact appendix table and a short
main-text takeaway, without adding result figures. The
[protocol](../analysis/review_followup/OFFLINE_PROTOCOL.md) was fixed before
computation; [validation](../analysis/review_offline/validation.json) independently
recomputes all systematic and dialogue point estimates from the saved scores.

**Prompt availability has two parts.** The exact static templates and adaptive
generation specification are already public in the
[prompt pack](../configs/adversarial_opinion_prompts.json) and
[protocol](ADVERSARIAL_OPINION.md). The current runner saves the initial reply
and turn scores but does not save the generated adaptive messages or subsequent
raw target replies in each trajectory record. Publish original logs if retained
elsewhere; a newly generated dialogue cannot be presented as a historical one.
Full message logging is already a requirement of the next API batch.

**Turn-of-flip descriptors are complete.** The new
[source table](../analysis/review_offline/turn_descriptors.csv) reports first
reversal at turn 1, 2 or 3, no reversal, adjacent decisive switches and any
abstention for every model and mode. No reversal is not assigned a fictitious
fourth turn. First error and first reversal remain distinct for initially
incorrect answers. These descriptors complement the existing first-error,
recovery and persistence analyses; their definitions are in the appendix.

## Direct manuscript fixes completed

- Define extreme-score reversals as at most 10 to at least 90, or the reverse,
  without implying every score equals exactly 0 or 100.
- Define correctness denominators as matched conditions, consistent with the
  pooled tables and judgment-cluster intervals.
- Distinguish GPT-5.6-sol's exact paraphraser/evaluator overlap from the
  DeepSeek summarizer/evaluators' shared model family.
- State that the symmetric abstention band records indecision around the
  prompt's 50-point uncertainty anchor, and link the main accuracy result to
  the completed five-rule sensitivity analysis.
- Add the completed [evaluator-exclusion diagnostic](../analysis/generator_exclusion/REPORT.md)
  to Appendix D: summary accuracy still decreases for all four retained models,
  and paraphrase effects retain mixed signs after removing GPT-5.6-sol.
- Preserve the approved abstract, protected Section 3, chapter structure,
  conference template and result figures.

## What the existing evidence already addresses

**Human validation is present, with a specific scope.** Appendix F reports
reasoning-to-fact paragraph-link validation: 120 assigned items, four returned
annotation sheets, and 65 genuine single-paragraph mappings after the documented
exclusions. Control-passing sheets confirm 88-96%, with pairwise agreement
0.89-1.00. This validates evidence links, not the separate claim-retention
judgments. The manuscript now states that distinction explicitly. New intensive human
annotation is outside this plan.

**Source review is not absent.** The released audit includes source boundaries,
located outcome/reasoning spans, contextual adjudication and selected-summary
acceptance. An offline [binding check](../analysis/review_followup/input_evidence.json)
confirms that all 947 current model-visible source texts and all 947 selected
summaries match that review registry. The existing residual lexical check
examined 21 matches in 20 judgments and resolved those candidates; it is not a
measured zero-leakage rate. Reproduce the binding check with
`python analysis/audit_review_followup.py`.

**Training exposure is a separate question.** The existing
[earlier-model analysis](../analysis/model_time_windows/REPORT.md) already uses
documented cutoffs and before/after cohorts for GPT-4o mini and GPT-4.1 mini.
Different temporal cohorts do not identify the effect of memorization. The
source-review records concern answer-revealing input content. Neither should
be presented as proof that training contamination is absent. Further black-box
recall probes are not prioritized over the direct role and sampling controls.

**Several requested controls already exist.** The saved-score analysis compares
full-record/summary changes with equally sized within-input samples. It does
not replace repeated conversations. Five-role comparisons, correctness-stratified
cue effects, extreme-score reversals and failure timing are also already complete.
Lawyer, junior lawyer and senior lawyer should not be listed as missing roles.

## Suggestions to narrow or defer

| Suggestion | Decision and reason |
| --- | --- |
| Country substitutions with Convention applicability fixed | Future work with the Convention/provision framework explicitly fixed. The completed US substitution changes respondent identity and jurisdiction together. |
| New text generator | Removed from the API plan. Retain the completed evaluator-exclusion diagnostic with generated inputs fixed. |
| Tone, length and large role taxonomy | Static role comparisons already preserve the surrounding template and later turns. Retain requested roles; add one equal-word-count wording control only if needed. A large grid is unnecessary. |
| Mixed-effects regression | Optional, not automatically more precise. Matched contrasts and judgment-cluster bootstrap already target the reported effects. Random-effects assumptions should serve a new question, not replace a valid paired analysis for appearance. |
| Utility-weighted abstention | Do not choose arbitrary clinical/legal costs. Report correct, wrong, abstaining and failed outcomes and threshold sensitivity. Court outcomes alone do not establish whether incomplete inputs are answerable. |
| New retrieval or adversarial-training experiments | Outside the central pipeline and judgment-reliability evidence; no immediate experiment added. |
| Mitigation baseline | Optional follow-up, not a required new contribution. Any prompt-based defense must measure both correct-answer retention and correction of initial errors; fewer reversals alone would not demonstrate improvement. |
| Human-curated summary subset | Defer: it requires substantial new annotation. Existing source review, fact-link validation and evaluator exclusions address distinct parts of the evidence. |

## Literature verification

The latest review's named works were retrieved programmatically from arXiv or
the publisher. The [retrieval record](../analysis/review_followup/review_literature_20260920.json)
stores titles, authors, publication metadata, URLs, HTTP status and checksums.

| Work | Relevance and decision |
| --- | --- |
| [SYCON-Bench, Hong et al., Findings of EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.121/) | Added: direct multi-turn antecedent measuring first conformity and stance switches; our emphasis remains reference-outcome correctness and persistence on real cases. |
| [ICE-Guard, Basu and Chakraborty, 2026](https://arxiv.org/abs/2603.18530) | Added for demographic, authority and framing sensitivity; no mitigation pipeline is imported. |
| [TriBench-Ko, Lee et al., 2026](https://arxiv.org/abs/2605.03792) | Verified background on judicial workflow tasks; not cited in the current judgment-reliability narrative. |
| [Pressure-Tune, Zhang et al., 2025](https://arxiv.org/abs/2508.13743) | Fine-tuning on adversarial scientific-QA dialogues. Real but less central to this benchmark paper; a training experiment is not required. |
| [Relevance paraphrasing, Askari et al., 2025](https://arxiv.org/abs/2406.03993) | Studies robustness of summary generation to paraphrased source passages. Our outcome is downstream judgment under changed input, so the tasks should not be equated. |
| [Proper-score decomposition, Broecker](https://arxiv.org/abs/0806.0813) | Supports the distinction between probability-score error and calibration alone when designing the Brier analysis. |

The earlier review also identified these works:

- **TRUTH DECAY**, Liu et al. (2025), studies accuracy and answer changes under
  static and rationale-based repeated feedback. It prevents attributing novelty
  to multi-turn feedback alone. [arXiv record](https://arxiv.org/abs/2503.11656v1)
- **ECtHR-PCR**, Santosh T.Y.S.S., Haddad and Grabmair (LREC-COLING 2024), separates
  factual queries from judicial arguments in precedent retrieval. It is verified
  background and is not cited in the current manuscript.
  [Publisher record](https://aclanthology.org/2024.lrec-main.486/)

Other suggestions are real but should not be imported mechanically:

- Agarwal and Khanna's **CW-POR** evaluates single-turn competing arguments
  judged by an LLM. Its confidence definition is not the current violation-score
  scale. [Primary source](https://arxiv.org/abs/2504.00374)
- **ClinDet-Bench** requires determinability labels for incomplete cases; the
  present court-outcome labels do not provide them.
  [Primary source](https://arxiv.org/abs/2602.22771)
- Khanbayov et al.'s **One Perturbation Is Not Enough** derives identification
  from specific multiplicative transformations and response laws. Three
  heterogeneous legal-input interventions do not establish that formal design.
  [Primary source](https://arxiv.org/abs/2609.06190)
- **Noisy but Valid** needs calibration labels for the exact judge task. Main
  correctness here uses court labels and parsed scores; paragraph-link validation
  is not calibration of claim retention.
  [Primary source](https://arxiv.org/abs/2601.20913)

## Release work that needs no model calls

The original generated paraphrase inputs and auxiliary claim-level artifacts
remain pending publication, as recorded in the source inventory. Publish the
actual saved artifacts with hashes when available; generating replacements
would not reproduce the reported run. Keep this reproducibility work separate
from the API queue.
