# Live refresh check (EmoP-5)

100 new ECtHR cases decided after v1.0, frozen before any model call, scored the
same way as a frozen 100-case v1.0 anchor, on 5.6-Sol and Opus-4.6, in the same
serving window.

The anchor reproduces the paper, with balanced accuracy 76.0 for 5.6-Sol (paper
75.5) and 63.8 for Opus-4.6 (paper 62.9), so the setup is sound.

New vs anchor, full record. 5.6-Sol 77.0 accuracy and 62.6 balanced vs 85.0 and
76.0. Opus-4.6 74.0 and 57.6 vs 76.0 and 63.8.

The 5.6-Sol drop is a real gap, not noise. The anchor minus new difference in
balanced accuracy is 13.3 points, with a bootstrap 95 percent interval of 1.7 to
25.0 that stays above zero. It sits almost entirely in no-violation recall, where
Sol gets 8 of 30 on the new cases against 16 of 30 on the anchor. Mixed judgments
drive part of it, since 12 of the 30 new no-violation targets come from judgments
that also find a violation elsewhere and Sol gets only 2 of those, though it also
misses most of the clean ones at 6 of 18. The same mixed versus pure split on the
anchor is still pending because the HUDOC website returns 404 right now. Opus-4.6
stays comparable across the two sets.

The right reading is that the refresh surfaces a weakness that the fixed set did
not, namely that 5.6-Sol is worse at recognising no violation on the newer cases,
which is consistent with the time drift the paper already reports.

Summaries change a similar share of judgments, 12 vs 10 for Sol and 16 vs 18 for
Opus. No-cue reversal stays around 0.9 to 1.0 on both sets. The researcher cue
drives Opus reversals to near zero on both, 0.00 new and 0.01 anchor, but it helps
5.6-Sol much less on the new cases, where Sol still reverses 0.93 against 0.48 on
the anchor (static arm).

Spend was about 51 dollars. post_v1_100 is the new cases, v1_anchor_100 is the
anchor, and v1_0_anchor_manifest.json records the seed and the selected ids.
run_eval.sbatch in each folder is the exact job.
