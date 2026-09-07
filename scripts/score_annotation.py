"""Recompute every annotation figure in the paper from annotation_merged.csv alone.

No other input, no network, no keys: if this disagrees with the text, the text is wrong.
"""
import csv, os, sys, itertools
from collections import Counter

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'data', 'annotation', 'annotation_merged.csv')
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
rows = list(csv.DictReader(open(path, encoding='utf-8')))
LETTERS = [c[-1] for c in rows[0] if c.startswith('label_')]
lab = lambda r, l: r[f'label_{l}']
seen = lambda r, l: bool(lab(r, l))

print(f'{len(rows)} items: ' + ', '.join(f'{k} {v}' for k, v in Counter(r['kind'] for r in rows).items()))
print()

print('CONTROLS  (scoreable only: defective and range-excused controls dropped)')
scoreable = [r for r in rows if r['control_status'] == 'scoreable']
for l in LETTERS:
    mine = [r for r in scoreable if seen(r, l)]
    c = Counter(lab(r, l) for r in mine)
    miss = sorted(r['pair_id'] for r in mine if lab(r, l) == 'yes')
    print(f'  {l}: {c["no"]}/{len(mine)} caught, unclear {c["unclear"]}, false pass {c["yes"]}'
          + (f'  {miss}' if miss else ''))
dropped = Counter(r['control_status'] for r in rows if r['kind'] == 'control')
print(f'  (of 19 controls: {dropped["scoreable"]} scoreable, {dropped["defective"]} defective, '
      f'{dropped["excused"]} excused because the number appears only inside a cited range)')
print()

print('RANGE ROWS  (the brief says `unclear`; a low share means the annotator got my bad DM rule)')
for l in LETTERS:
    mine = [r for r in rows if r['cite_class'] == 'range' and seen(r, l)]
    n_unclear = sum(1 for r in mine if lab(r, l) == 'unclear')
    print(f'  {l}: {n_unclear}/{len(mine)} unclear')
print()

gs = [r for r in rows if r['kind'] == 'genuine' and r['cite_class'] == 'single']
print(f'VALIDATION  on the {len(gs)} genuine single-pointer items, the subset the protocol can validate')
for l in LETTERS:
    mine = [r for r in gs if seen(r, l)]
    c = Counter(lab(r, l) for r in mine)
    print(f'  {l}: mapping confirmed {c["yes"]}/{len(mine)} = {c["yes"]/len(mine):.0%}'
          f'   (no {c["no"]}, unclear {c["unclear"]})')
print()

print('PAIRWISE AGREEMENT on the same subset')
for x, y in itertools.combinations(LETTERS, 2):
    sh = [r for r in gs if seen(r, x) and seen(r, y)]
    if not sh: continue
    ag = sum(1 for r in sh if lab(r, x) == lab(r, y))
    print(f'  {x} vs {y}: {ag}/{len(sh)} = {ag/len(sh):.2f}')
print()

bad = [r for r in rows if r['kind'] == 'genuine' and r['cite_class'] == 'uncited']
print(f'CONSTRUCTION ERRORS: {len(bad)} of {sum(1 for r in rows if r["kind"]=="genuine")} genuine pairs '
      f'show a number the reasoning never cites')
for r in bad:
    print(f'  {r["pair_id"]}: shown {r["cited_number"]}, '
          + ', '.join(f'{l}={lab(r,l)}' for l in LETTERS if seen(r, l)))
