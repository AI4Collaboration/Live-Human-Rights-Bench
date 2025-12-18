# Unified Experiment System Guide

## Overview

The unified experiment system allows you to run multiple bias experiments efficiently without duplicating code. Instead of running separate scripts for each condition, you define **replacement strategies** and **scenarios** in a config file, then run everything through a single unified script.

## Architecture

```
config/replacement_config.json  → Defines strategies & scenarios
         ↓
run_unified_experiment.py       → Runs experiments for scenarios
         ↓
data/experiments/               → Output: {scenario}_results.csv & _metrics.json
         ↓
analyze_experiments.py          → Generic analysis for any scenarios
```

---

## 1. Configuration File

**Location:** `config/replacement_config.json`

### Structure:

```json
{
  "strategies": {
    "strategy_name": {
      "description": "...",
      "replacements": {
        "[PLACEHOLDER]": "replacement text"
      },
      "complex_replacements": {
        "[PLACEHOLDER]": {
          "type": "contextual_pronoun",
          "subject": "he",
          "object": "him",
          "object_verbs": ["filmed", "saw", "met", ...]
        }
      }
    }
  },
  "scenarios": [
    {
      "name": "scenario_name",
      "description": "...",
      "keys": ["strategy1", "strategy2"]
    }
  ]
}
```

### Available Strategies:

**Applicant:**
- `applicant_generic` - "applicant", "the applicant's"
- `applicant_male` - "Bob", "his", "he/him"
- `applicant_female` - "Alice", "her", "she/her"

**Defendant:**
- `defendant_generic` - "the defendant state"
- `defendant_poland` - "Poland", "Polish"
- `defendant_hungary` - "Hungary", "Hungarian"
- `defendant_germany` - "Germany", "German"
- `defendant_france` - "France", "French"

### Pre-defined Scenarios:

```
generic_generic   → Generic applicant, generic defendant (baseline)
male_generic      → Bob, generic defendant
female_generic    → Alice, generic defendant
generic_poland    → Generic applicant, Poland
generic_hungary   → Generic applicant, Hungary
generic_germany   → Generic applicant, Germany
generic_france    → Generic applicant, France
male_poland       → Bob, Poland
female_germany    → Alice, Germany
... (easily add more!)
```

---

## 2. Running Experiments

### Run All Scenarios:

```bash
python run_unified_experiment.py
```

This runs ALL scenarios defined in `config/replacement_config.json`.

**⚠️ Smart Skipping:** By default, the system **skips scenarios that already have results**. This saves time and API costs!

### Run Specific Scenarios:

```bash
python run_unified_experiment.py --scenarios generic_generic male_generic female_generic
```

### Force Re-run (Ignore Existing Results):

```bash
python run_unified_experiment.py --force
```

Use `--force` to re-run experiments even if results already exist.

### Custom Options:

```bash
python run_unified_experiment.py \
    --config config/replacement_config.json \
    --scenarios male_generic female_generic \
    --input data/real_cases/echr_new/unanimous/balanced_sample_50_50_three_step_ner_updated_v2.json \
    --output-dir data/experiments \
    --model openai/gpt-4o \
    --temperature 0.0
```

### Output Files:

For each scenario, generates:
- `data/experiments/{scenario}_results.csv` - Detailed results per case
- `data/experiments/{scenario}_metrics.json` - Aggregate metrics

---

## 3. Analyzing Results

### Basic Analysis:

```bash
python analyze_experiments.py --scenarios generic_generic male_generic female_generic
```

### With Baseline Comparison:

```bash
python analyze_experiments.py \
    --scenarios generic_generic male_generic female_generic \
    --baseline generic_generic
```

### Custom Results Directory:

```bash
python analyze_experiments.py \
    --scenarios generic_poland generic_germany \
    --baseline generic_poland \
    --results-dir data/experiments/unified_test
```

### Output Includes:

1. **Summary Table:** Distance scores, ratings, confidence for all scenarios
2. **Detailed Metrics:** Per-scenario breakdown
3. **Pairwise Comparison:** Agreement, bias direction, outlier cases

---

## 4. Adding New Experiments

### Example: Add Russian and UK as defendants

**Step 1:** Add strategies to `config/replacement_config.json`:

```json
{
  "strategies": {
    ...
    "defendant_russia": {
      "description": "Russia as defendant state (Eastern Europe)",
      "replacements": {
        "The [DEFENDANT STATE]": "Russia",
        "the [DEFENDANT STATE]": "Russia",
        "[DEFENDANT STATE]": "Russia",
        "The [DEFENDANT STATE ADJ]": "Russian",
        "the [DEFENDANT STATE ADJ]": "Russian",
        "[DEFENDANT STATE ADJ]": "Russian"
      }
    },
    "defendant_uk": {
      "description": "United Kingdom as defendant state (Western Europe)",
      "replacements": {
        "The [DEFENDANT STATE]": "the United Kingdom",
        "the [DEFENDANT STATE]": "the United Kingdom",
        "[DEFENDANT STATE]": "the United Kingdom",
        "The [DEFENDANT STATE ADJ]": "British",
        "the [DEFENDANT STATE ADJ]": "British",
        "[DEFENDANT STATE ADJ]": "British"
      }
    }
  }
}
```

**Step 2:** Add scenarios:

```json
{
  "scenarios": [
    ...
    {
      "name": "generic_russia",
      "description": "Generic applicant, Russia defendant",
      "keys": ["applicant_generic", "defendant_russia"]
    },
    {
      "name": "generic_uk",
      "description": "Generic applicant, UK defendant",
      "keys": ["applicant_generic", "defendant_uk"]
    }
  ]
}
```

**Step 3:** Run experiments:

```bash
python run_unified_experiment.py --scenarios generic_russia generic_uk
```

**Step 4:** Analyze:

```bash
python analyze_experiments.py \
    --scenarios generic_generic generic_russia generic_uk \
    --baseline generic_generic
```

---

## 5. Advanced: Combining Multiple Dimensions

You can combine ANY applicant strategy with ANY defendant strategy!

### Example: Gender + Country Experiments

Test if bias varies by country for male vs female applicants:

```json
{
  "scenarios": [
    {"name": "male_poland", "keys": ["applicant_male", "defendant_poland"]},
    {"name": "female_poland", "keys": ["applicant_female", "defendant_poland"]},
    {"name": "male_germany", "keys": ["applicant_male", "defendant_germany"]},
    {"name": "female_germany", "keys": ["applicant_female", "defendant_germany"]}
  ]
}
```

```bash
python run_unified_experiment.py --scenarios male_poland female_poland male_germany female_germany

python analyze_experiments.py \
    --scenarios male_poland female_poland male_germany female_germany \
    --baseline male_poland
```

---

## 6. Conflict Detection

The system automatically **errors if strategies conflict**:

**Example - This will ERROR:**

```json
{
  "name": "conflicting_scenario",
  "keys": ["applicant_male", "applicant_female"]
}
```

**Error:**
```
ValueError: Conflict detected: placeholder '[APPLICANT NAME]' is defined in both
'applicant_male' and 'applicant_female'. Each placeholder can only be replaced by one strategy.
```

**Fix:** Each scenario should have ONE applicant strategy and ONE defendant strategy.

---

## 7. Compared to Old System

### Old System (DEPRECATED):
```bash
python run_simple_violation_experiment.py --input ... --output ...
python run_male_applicant_experiment.py --input ... --output ...
python run_female_applicant_experiment.py --input ... --output ...
python run_defendant_state_experiment.py --condition poland --input ... --output ...
python run_defendant_state_experiment.py --condition germany --input ... --output ...
# ... run 10+ separate scripts
```

### New Unified System:
```bash
# Define once in config
python run_unified_experiment.py
# Runs all scenarios automatically!
```

**Benefits:**
- ✅ Load cases only ONCE (faster)
- ✅ No code duplication
- ✅ Easy to add new experiments (just edit config)
- ✅ Single analysis script for everything
- ✅ Guaranteed consistency across experiments

---

## 8. File Naming Convention

All output files follow the pattern: `{scenario_name}_*`

**Scenario:** `male_germany`
**Output:**
- `male_germany_results.csv`
- `male_germany_metrics.json`

This makes it easy to:
- Track which files belong to which experiment
- Run analysis on arbitrary scenario combinations
- Avoid filename conflicts

---

## 9. Example Workflows

### Gender Bias Analysis:

```bash
# Run experiments
python run_unified_experiment.py --scenarios generic_generic male_generic female_generic

# Analyze
python analyze_experiments.py \
    --scenarios generic_generic male_generic female_generic \
    --baseline generic_generic
```

### Country Bias Analysis:

```bash
# Run experiments
python run_unified_experiment.py \
    --scenarios generic_generic generic_poland generic_hungary generic_germany generic_france

# Analyze
python analyze_experiments.py \
    --scenarios generic_generic generic_poland generic_hungary generic_germany generic_france \
    --baseline generic_generic
```

### Combined Gender + Country Analysis:

```bash
# Run experiments for all combinations
python run_unified_experiment.py \
    --scenarios male_poland male_germany female_poland female_germany

# Compare male vs female for Poland
python analyze_experiments.py \
    --scenarios male_poland female_poland \
    --baseline male_poland

# Compare male vs female for Germany
python analyze_experiments.py \
    --scenarios male_germany female_germany \
    --baseline male_germany

# Compare Poland vs Germany for males
python analyze_experiments.py \
    --scenarios male_poland male_germany \
    --baseline male_poland
```

---

## 10. Tips & Best Practices

1. **Always include a baseline scenario** (e.g., `generic_generic`) for comparison
2. **Use descriptive scenario names** following `{applicant}_{defendant}` pattern
3. **Test with a subset first** using `--scenarios` to verify replacements work correctly
4. **Check conflict errors** - they prevent subtle bugs
5. **Keep config file in version control** to track experiment definitions
6. **Output to separate directories** for different experiment batches if needed

---

## Quick Reference

```bash
# List available scenarios (check config file):
cat config/replacement_config.json | jq '.scenarios[].name'

# Run all scenarios:
python run_unified_experiment.py

# Run specific scenarios:
python run_unified_experiment.py --scenarios scenario1 scenario2

# Analyze results:
python analyze_experiments.py --scenarios scenario1 scenario2 --baseline scenario1

# Run + analyze in one go:
python run_unified_experiment.py --scenarios generic_generic male_generic female_generic && \
python analyze_experiments.py --scenarios generic_generic male_generic female_generic --baseline generic_generic
```
