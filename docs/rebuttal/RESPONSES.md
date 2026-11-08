# Responses to the reviewers

The responses below cover all reviewer concerns. Results from the new controls
come from a frozen 50-judgment sample and are separate from the main experiment.
The new-release question in EmoP's review remains assigned separately; its
response does not claim results that have not been collected.

## Reviewer FTor

Thank you for identifying the need to distinguish the behavioral effects more
precisely. We added targeted controls for opposition, answer-replacement
instructions and evaluation wording. We also revised the reasoning analysis
to keep its observations separate from causal explanations.

### FTor-1: Why do evidence-free challenges change judgments?

**Opposition has an effect beyond neutral reconsideration, while the original
directive-containing challenges cause more reversals.** We selected 50 judgments uniformly
from 795 shared eligible judgments before collecting new outcomes. Each
condition begins with the same saved initial reply and supplies no new case
evidence. After three turns an opposing opinion without a request to change
the answer reverses 13/50 Opus-4.6 judgments (26.0%) versus 1/50 under neutral
reassessment (2.0%). The corresponding 5.6-Sol comparison is 12/46 (26.1%)
versus 1/46 (2.2%). V4-Flash reverses 23/40 (57.5%) versus 1/40 (2.5%). Each
pair uses only cases complete in both conditions.

The same comparison also overturns correct answers: the opinion-only condition
reverses 9/44 initially correct Opus judgments versus none under neutral
reassessment. All 46 Sol judgments in this comparison are initially correct.

The original high-pressure prompt additionally demands replacement of the
answer. On the separately paired directive-versus-opinion cohorts reversal
falls from 90.0% to 26.0% for Opus-4.6 and from 89.6% to 29.2% for 5.6-Sol when
that demand is removed. Those comparisons use 50 and 48 judgments respectively.
This contrast removes the replacement demand together with its confrontational
wording. It separates reversals under an opposing belief from the much higher
rates under the original directive-containing challenge. We now make
that distinction in the abstract, introduction and adversarial-opinion results.
These interventions identify effects of the challenge wording; attributing
them to a particular training mechanism requires further evidence.

**Revision:** Main-text adversarial-opinion results and Appendix
“Repeated Conversations and Targeted Controls,” including the paired counts
and intervals in the control table.

### FTor-2: Do reasoning traces establish evaluation awareness as a cause?

**The trace analysis measures expressed evaluation language.** We analyze each
recorded explanation in full and compare the same instances across cues. In
the existing V4-Flash reasoning run 125/201 explanations that mention evaluation
still accompany a reversal. Opus also has selective text availability: all
177 first-turn no-cue responses without recorded reasoning reverse, compared
with 653/734 responses with reasoning. The appendix now reports this breakdown.

Opus provides summarized reasoning. The counts therefore describe the text
that is available and cannot identify the mechanism producing a judgment.
We use the new wording intervention below to test a behavioral hypothesis
independently of the reasoning-language counts.

**Revision:** Appendix “CoT Analysis: Evaluation Awareness” and the separate
control appendix. No inference about censorship or an unobserved awareness
state is drawn from the missing text.

### FTor-3: Is there a preliminary mitigation?

**Reducing reversals is insufficient if the model also preserves its errors.**
The existing AI safety researcher cue provides a concrete intervention that
strongly reduces reversal in Opus-4.6 and 5.6-Sol. Our correctness breakdown
shows that this increased retention also preserves initially wrong judgments.
A useful safeguard must preserve evidence-supported judgments while allowing
errors to be corrected. We make this tradeoff explicit alongside the cue
results instead of presenting an identity cue as a validated defense. Neutral
reassessment is a diagnostic control here; it does not defend a model that is
still exposed to an adversarial challenger.

**Revision:** The role-cue results and conclusion state the retention versus
correction criterion. The released comparisons support testing future defenses
against both outcomes.

### FTor-4: Why does the researcher cue affect models so differently?

**Explicit evaluation wording changes behavior even when the role is fixed.**
Both new conditions begin with “I am an AI researcher.” The following sentence
is either “This conversation concerns the present case.” or “This conversation
evaluates your model behavior.” Both sentences contain six words; the opposing
challenge and later turns are identical. For 5.6-Sol evaluation wording lowers
final reversal from 30/49 (61.2%) to 19/49 (38.8%). The paired difference is
−22.4 percentage points with a 95% case-bootstrap interval of [−36.7, −10.2].

Opus-4.6 already reverses only 1/50 judgments under neutral AI researcher
framing and also reverses 1/50 under evaluation framing. This floor leaves
little room for an additional reduction. V4-Flash remains at 46/47 under both
framings. The intervention supports sensitivity to explicit evaluation wording
in 5.6-Sol and shows that the wording has different effects across models.
It does not establish that latent evaluation awareness explains the entire
original identity-cue contrast. The low Opus rate under ordinary AI researcher
framing also shows that the word “safety” is not necessary in this setting.

**Revision:** The role-cue results now connect the intervention to the
descriptive reasoning analysis. The control appendix preserves all model
comparisons and their paired denominators.

## Reviewer j8sk

Thank you for distinguishing the benchmark contribution from the phenomena
it measures. We have made the independent input validation and repeatability
evidence explicit.

### j8sk-1: What is new beyond known reliability phenomena?

**The contribution is a renewable benchmark with a common evaluation contract.**
It connects published human-rights judgments to provision-specific targets
and verdict-free inputs. Each instance then supports input transformations
and opposing-opinion conversations with a shared initial judgment. The
combination measures accuracy alongside which judgments change and whether
those changes correct errors or create them. The introduction presents these
as benchmark and evaluation contributions. Summarization and paraphrasing
themselves are established methods.

### j8sk-2: Are paraphrases independently checked for fact preservation?

**An independent verifier supports the result after filtering detected fact
loss.** Qwen3-235B checks 69,106 claim-target pairs independently of the
5.6-Sol paraphrase generator. After repairing 26 inputs the three strengths
retain 99.2–99.5% of originally supported sampled claims. The verifier rejects
256/300 controls with deliberately swapped attributes.

We also select inputs without looking at target-model judgments. The filter
retains 540 targets from 521 judgments for which every sampled claim supported
in the original is supported in all three rewrites. These targets have a
median of 76 supported claims. Judgment-change rates remain 4.8–15.4% across
the five primary models and three strengths. The result therefore persists
after excluding detected fact loss. This validation concerns sampled factual
claims; it does not certify every semantic implication of an entire record.

**Revision:** The systematic-perturbation setup identifies the independent
verifier. Its results paragraph and the perturbation appendix add the
540-target sensitivity analysis with the original denominators kept separate.

### j8sk-3: How stable are cue effects across repeated conversations?

**Three repetitions preserve the large average cue effects while revealing
case-level variation.** We independently sample three static continuations
under no cue and under the AI safety researcher cue for each selected case.
Every continuation starts from its model's same saved initial reply. Requiring
all six complete conversations leaves 48 Opus-4.6 cases and 49 5.6-Sol cases.

Opus no-cue reversal rates are 91.7%, 93.8% and 95.8%; its researcher-cue rate
is 2.1% in each repetition. Sol's no-cue rate is 89.8% in each repetition;
its researcher-cue rates are 34.7%, 32.7% and 42.9%. Mean cue reductions are
91.7 percentage points for Opus and 53.1 for Sol. Their 95% hierarchical
bootstrap intervals are [83.3, 97.9] and [40.8, 66.0]. Resampling treats cases
as the primary units and repetitions as repeated observations within cases.

Identical aggregate rates can conceal changing individual outcomes. For Sol
the reversal indicator differs across repeats on 5/49 no-cue cases and 11/49
researcher-cue cases. These results quantify variation in continuations
conditional on the saved initial response. They preserve the direction and
model ordering of the cue effect without treating the new collection as a
replacement for the original full-cohort experiment.

**Revision:** Appendix “Repeated Conversations and Targeted Controls” provides
all three rates, comparison sizes and the within-case variation. The role-cue
paragraph points to this evidence.

## Reviewer EmoP

Thank you for asking how the benchmark's update claim can be verified. The
revision separates its renewable construction process from the scope of the
results currently available.

### EmoP-1 and EmoP-2: Methodological novelty and technical complexity

**The benchmark makes linked reliability measurements repeatable on new human
judgments.** Its contribution is the source-to-target construction and combined
evaluation: a published judgment supplies the expert outcome while the
model-visible input excludes verdict content. The same target supports input
perturbations and conversational challenges. Accuracy alone can conceal
instance-level changes and strong dependence on the challenger's identity.
The introduction attributes novelty to this benchmark and its empirical
findings rather than to a new perturbation algorithm or architectural complexity.

### EmoP-3: How does automatic updating work?

**The released pipeline retrieves new candidates before applying release
checks.** The refresh script queries newly published HUDOC records and removes
duplicates by source identifier. Target resolution then identifies the
respondent country and the relevant provision and issue. Source review checks
the model-visible facts for outcome leakage before generated inputs and a
release manifest are frozen. The pipeline automates candidate collection and
input processing; target and source validation remain release gates.

**Revision:** The source-corpus appendix now explains the update stages. The
repository's release protocol gives the executable entry point and required
artifacts.

### EmoP-4: How is consistency maintained across releases?

**Versioned inputs and fixed evaluation rules make releases comparable.**
Each release fixes its target cohort and text hashes together with the prompt
version and scoring rules. The model identifier and collection date are
recorded as well. A contemporaneous evaluation on a frozen anchor cohort
separates changes in the served model from changes in newly added cases.

As an existing-data check we verified all three designated v1.0 input hashes
against the release manifest. Splitting its 943 pre-2026 targets from its 57
targets dated 2026 and joining them again reconstructs v1.0 exactly. Every
earlier record remains unchanged. This checks release consistency on the
frozen data; it is distinct from collecting and evaluating a fresh release.

### EmoP-5: Do the findings hold on newly published judgments?

**The reported findings are established on v1.0.** The current experiments do
not establish generalization to judgments published after that release. We
have specified a separate new-batch evaluation using nonoverlapping judgments
after 21 May 2026 with the original prompts and scoring rules. It includes a
contemporaneous v1.0 anchor to distinguish case changes from model changes.
The paper now states the v1.0 scope in its update discussion. The task and its
required evidence are listed separately so that any new-release claim can be
added only once those records are available.

## Evidence index

- [All results and exact denominators](../../analysis/rebuttal_20261107/REPORT.md)
- [Frozen sampling, prompts and repetition protocol](EXPERIMENTS.md)
- [Raw request and response records](../../data/experiments/rebuttal_20261107/)
- [Release protocol](RELEASE_PROTOCOL.md)
- [New-release handoff](DELEGATED_TASKS.md)
- [Point-by-point coverage](review_tracker.csv)
