# Review assessment and improvements

Checked 19 September 2026 against the current v1.0 results and manuscript.
The review identifies useful controls for the role-cue result and conversational
sampling. Its suggestions vary in relevance; they are not all missing experiments.
The [merged API plan](NEXT_EXPERIMENTS.md) is summarized at the top of the README.
No API experiments or new human annotation were performed for this revision.

## Highest-value additions

| Issue | Assessment | Action |
| --- | --- | --- |
| AI researcher versus AI safety researcher | Directly tests the distinctive wording in the headline finding | First API batch, with concurrent no-cue and AI-safety references |
| Single conversation per condition | Existing judgment bootstrap measures variation across cases, not repeated conversations | Five static trajectories on 50 locked cases; adaptive replication is a separately budgeted next step |
| Neutral reassessment | Existing disagreement already supplies an opposing verdict | Add the planned neutral branch to the same static batch |
| Scoring-threshold sensitivity | Important and computable from saved scores | Completed [offline analysis](../analysis/threshold_sensitivity/REPORT.md), with frozen cohorts and explicit score-50 tie rules |
| Conversation protocol visibility | Settings exist in the appendix and runner, but readers must assemble them | Bring temperature and response budgets into the main setup; explain why fixed-input scoring averages responses while dialogue analysis tracks individual turns |
| Close multi-turn prior work | TRUTH DECAY is a direct antecedent | Add a precise citation; emphasize court-grounded evaluation, matched cue contrasts, correctness and persistence |

The recommended static API package costs **4,800 target responses**. It combines
four contemporaneous conditions on 100 cases and four additional repetitions
of the two headline references on a nested 50 cases. Adaptive replication adds
3,000 target responses and 3,000 challenger generations. Existing roles remain
references; generic researcher, judge and nationality stay in the merged plan.
Nationality is not crossed with professional roles.

## What the existing evidence already addresses

**Human validation is present, with a specific scope.** Appendix F reports
reasoning-to-fact paragraph-link validation: 120 assigned items, four returned
annotation sheets, and 65 genuine single-paragraph mappings after the documented
exclusions. Control-passing sheets confirm 88-96%, with pairwise agreement
0.89-1.00. This validates evidence links, not the separate claim-retention
judgments. Clarify that distinction rather than treating it as either no human
validation or complete calibration of the auxiliary judge. New intensive human
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
| Identity-only State Swap | Conditional API extension. The current claim explicitly combines identity and jurisdiction; US substitution is not interpreted as pure nationality bias. Contracting-state membership alone does not fix every legal assumption. |
| New text generator | Optional for a claim about robustness across generators. Shared inputs control the present comparisons; changing generators answers a separate generalization question. Excluding same-family evaluators is an offline diagnostic, not an independent-generator experiment. |
| Evaluation-awareness mechanism | Keep as a hypothesis. AI versus AI safety estimates wording sensitivity. A separate role-by-evaluation-framing experiment is available in the plan if a mechanism claim becomes central. |
| Tone, length and large role taxonomy | Static role comparisons already preserve the surrounding template and later turns. Retain requested roles; add one equal-word-count wording control only if needed. A large grid is unnecessary. |
| Mixed-effects regression | Optional, not automatically more precise. Matched contrasts and judgment-cluster bootstrap already target the reported effects. Random-effects assumptions should serve a new question, not replace a valid paired analysis for appearance. |
| Utility-weighted abstention | Do not choose arbitrary clinical/legal costs. Report correct, wrong, abstaining and failed outcomes and threshold sensitivity. Court outcomes alone do not establish whether incomplete inputs are answerable. |
| New retrieval or adversarial-training experiments | Outside the central pipeline and judgment-reliability evidence; no immediate experiment added. |

## Literature verification

All suggested works were checked against primary records. Two are the most
useful additions within the current Related Work structure:

- **TRUTH DECAY**, Liu et al. (2025), studies accuracy and answer changes under
  static and rationale-based repeated feedback. It prevents attributing novelty
  to multi-turn feedback alone. [arXiv record](https://arxiv.org/abs/2503.11656v1)
- **ECtHR-PCR**, Santosh T.Y.S.S., Haddad and Grabmair (LREC-COLING 2024), separates
  factual queries from judicial arguments in precedent retrieval. It supports
  the construction context without requiring a retrieval extension.
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
