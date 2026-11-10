100 new ECtHR cases decided after v1.0, frozen before any model call, scored the
same way as a frozen 100-case v1.0 anchor, on 5.6-Sol and Opus-4.6, same serving window.
Anchor reproduces the paper, balanced accuracy 76.0 for 5.6-Sol (paper 75.5) and
63.8 for Opus-4.6 (paper 62.9).
New vs anchor, full record. 5.6-Sol 77.0 acc, 62.6 balanced vs 85.0, 76.0.
Opus-4.6 74.0, 57.6 vs 76.0, 63.8. Balanced-accuracy intervals overlap, so no
significant difficulty gap.
Summaries change a similar share of judgments, 12 vs 10 for Sol and 16 vs 18 for Opus.
No-cue reversal stays around 0.9 to 1.0 on both, and the researcher cue drives Opus
reversals to near zero on both, 0.00 new and 0.01 anchor.
 post_v1_100 is the new cases, v1_anchor_100 is the anchor,
and v1_0_anchor_manifest.json records the seed and selected ids. run_eval.sbatch in
each folder is the exact job.
