# Archived MFT arm

**RELEASE BLOCKER: delete the entire `archive/mft/` directory before the formal release.**

This directory is historical material only. It is outside the active benchmark,
must not be imported by current experiments, and must not be cited as a result of
the current input release.

Reasons for archival:

- The arm uses the separate `echr_livehrb_static_2k.json` corpus, which is not
  included in this repository and was not checked by the current leak detector.
- Its eight-model roster is historical and does not match the current six-model
  roster.
- The committed CSV files contain 997 evaluated case-Article rows per model at
  five samples each. The unavailable generation artifact prevents verification
  of the previously stated 1,005-input count.

Archived contents:

- `experiments/`: generation and evaluation entry points
- `scripts/`: collision checks, analysis, refresh, and table generation
- `mft_prompts.py`: the dedicated doctrinal tests and generation prompt
- `data/experiments/mft/`: eight historical result CSV files

These files are retained only for traceability until the formal release cleanup.
They are not maintained as a runnable pipeline inside the archive.
