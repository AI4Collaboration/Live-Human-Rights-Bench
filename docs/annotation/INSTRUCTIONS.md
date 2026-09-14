# Validating what the Court relied on

Each row of your sheet shows two paragraphs from the same judgment: `reasoning`, where the
Court explains its decision and points somewhere with a phrase like "see paragraph 18 above",
and `cited_fact`, the paragraph our tool believes it was pointing at, whose number is in
`cited_number`. Fill in the `label` column with `yes` if the reasoning uses or clearly refers
to that fact, `no` if it does not, and `unclear` if you genuinely cannot tell; put anything
odd in `notes`, leave every other column alone, and send the file back when you are done. No
legal training is needed and you should not look up legal terminology -- you are judging where
a statement came from, not whether the Court got it right, so a figure that looks slightly off
is still `yes` when the cited paragraph is plainly its source. Both texts always come from the
same case, so almost everything will look related; related is not the question, whether the
reasoning leans on that particular fact is. Four things come up often and are not faults in
the sheet: if `cited_number` appears nowhere in the reasoning, the answer is simply `no`; if
the Court points at a range or a list of paragraphs rather than a single one and we show you
one of them, `unclear` is the honest answer; if the paragraph we show carries no content of
its own and merely points further back, `unclear` again, with a word in `notes`; and a
paragraph containing `...` is the Court's own abridgement, not something we cut. Work from
these two texts alone -- the `full_judgment` link is there for curiosity, not for the task,
and you should never need to open it. Please work in order, mark a hard row `unclear` rather
than skipping it, do not discuss individual rows with the other annotators, and ask me
anything before doing eighty rows rather than after.
