# AI layer — what it does, what it shows, what it does not

**Design (agreed 2026-10-19):** the measuring core stays classic (exact numbers, checkable against a ruler). The AI is an add-on
that only sees the per-frame features the board already sends: length, width, area, fill (area / (length x width)) and, derived,
the aspect ratio. Script: `py/ai_eval.py` (scikit-learn 1.9.1), data: the real board recording `data/runs/20261020_final.csv`
(stale lines removed, first 20 lines of each recording dropped, only valid measurements; 6,548 lines, 30 recordings:
good bolts 4,456 lines, bad_a 541, bad_b 515, bad_c 607, bad_d 429).

## A) Which part is it? (5 classes, leave-one-placement-out)
Each recording is held out in turn; the model is trained on all other recordings and tested on the held-out one.

| Model | Frame accuracy | Recordings correct (majority) |
|---|---|---|
| Decision tree, depth 3 | **86.2 %** | 25 / 30 |
| k-NN (k = 15, standardized features) | 83.7 % | 24 / 30 |

Confusion of the tree (rows = truth): good 4,277 right, 168 called bad_c; bad_a 383 right, 158 called bad_b; bad_b 309 right, 196 called bad_a;
bad_c 464 right, 128 called bad_a; bad_d 212 right, 217 called bad_c. Errors happen between parts of similar length: the length of a shiny
part changes with its angle by up to 5-7 mm (`docs/RESULTS.md`). The tree is small enough for the ARM (7 comparisons):
`L <= 12.68 mm`, then fill, width and area. It was **not** exported to C or run on the board.

## B) Reject a defect it has never seen (the realistic task)
Train on good bolts only (leave-one-good-placement-out), test on the held-out good placement (must be accepted) and on **all** bad parts
(must be rejected; none of them was used for training).

| Method | Good accepted | Bad rejected |
|---|---|---|
| One-class model: Mahalanobis distance on (length, width, fill), threshold = 99th percentile of the good training distances | 98.7 % | **100.0 %** (every bad type 100 %) |
| Plain tolerance rule fitted on the same good data only: median +- 4.5 robust sigma on length, width and fill | 99.5 % | 99.0 % |

## What this shows, honestly
- The AI is **not better** than a tolerance rule on this data. Both separate the four wrong part types from the good bolts almost perfectly,
  because those parts differ a lot in length or width.
- The benefit of the learned model is practical: it needs **no hand-set tolerance** (it is fitted from good examples alone) and it uses the correlation
  between features. The tolerance rule used on the board (length 11.3 +- 1.6 mm, width 1.3 +- 0.7 mm) was set by hand and tuned in-sample; this
  experiment is the fair comparison.
- It does **not** solve the hard cases: a part that differs by 0.5 mm would not be separated with a ruler-calibrated camera at 0.17 mm per pixel,
  and the long shiny parts are not recognised by type reliably.

## Limits
- 5 good bolts and 4 wrong part types, 3 placements each, one camera and lamp setup. Small data: the percentages have wide uncertainty.
- Frame-level rates count each video frame; frames of one recording are strongly correlated, so the effective number of independent samples is
  about the 30 recordings.
- Nothing from the AI layer was run on the board.
