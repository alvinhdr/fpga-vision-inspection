"""
analyze_evidence.py - numbers for docs/RESULTS.md from the evidence CSV written by py/evidence.py.
Project: Real-Time FPGA Vision Inspection Station
  .\.venv\Scripts\python.exe py\analyze_evidence.py data\runs\20261020_final.csv
Prints: repeatability (still bolt), per-placement accuracy and PASS/FAIL, confusion tables (placement and frame level),
mean length per part, empty-mat result, frame continuity. The first quarter of every 3 s recording is dropped
(hand leaving, smoothing warm-up); repeat recordings use the last 80 %.
"""
import csv
import collections
import sys

import numpy as np

rows = list(csv.DictReader(open(sys.argv[1])))
f = lambda r, k: float(r[k])
print(f"{len(rows)} result lines; groups {dict(collections.Counter(r['group'] for r in rows))}")

print("\nREPEATABILITY (bolt_good_01, not touched, 10 s each, last 80 %):")
for pl in "123":
    R = [r for r in rows if r["group"] == "repeat" and r["placement"] == pl]
    R = R[len(R) // 5:]
    M = [r for r in R if r["status"] == "MEASURED"]
    if not M:
        print(f" pos {pl}: no valid lines"); continue
    L = np.array([f(r, "L_mm") for r in M]); Lp = np.array([f(r, "L_px") for r in M]); W = np.array([f(r, "W_mm") for r in M])
    cx = np.array([f(r, "cx") for r in M]); cy = np.array([f(r, "cy") for r in M])
    print(" pos %s: %d lines (%d valid) | L mean %.3f mm  std %.3f mm (%.2f px)  range %.2f..%.2f | W mean %.2f mm std %.3f | centre std cx %.2f cy %.2f px | %s" % (
        pl, len(R), len(M), L.mean(), L.std(), Lp.std(), L.min(), L.max(), W.mean(), W.std(), cx.std(), cy.std(),
        dict(collections.Counter(r["verdict"] for r in R))))

plc = collections.defaultdict(list)
for r in rows:
    if r["group"] == "acc":
        plc[(r["part"], r["class"], r["placement"])].append(r)
print("\nPER PLACEMENT (first quarter dropped): part, median L, W, verdicts -> majority")
conf = collections.Counter(); lc = collections.Counter(); per = collections.defaultdict(list); perW = collections.defaultdict(list)
for (part, cls, pl), R in sorted(plc.items()):
    R2 = R[len(R) // 4:]
    vs = collections.Counter(r["verdict"] for r in R2)
    M = [r for r in R2 if r["status"] == "MEASURED"]
    L = np.median([f(r, "L_mm") for r in M]) if M else float("nan")
    W = np.median([f(r, "W_mm") for r in M]) if M else float("nan")
    maj = vs.most_common(1)[0][0]
    conf[(cls, maj)] += 1; per[part].append(L); perW[part].append(W)
    for r in R2:
        lc[(cls, r["verdict"])] += 1
    print("  %-13s #%s L %6.2f W %5.2f %s -> %s" % (part, pl, L, W, dict(vs), maj))
print("\nPLACEMENT level (majority verdict):")
for c in ("good", "bad"):
    print("  %-5s PASS %2d  FAIL %2d  NONE %2d" % (c, conf[(c, "PASS")], conf[(c, "FAIL")], conf[(c, "NONE")] + conf[(c, "NOCAL")]))
print("FRAME level:")
for c in ("good", "bad"):
    n = sum(v for (a, b), v in lc.items() if a == c)
    d = lc[(c, "PASS")] + lc[(c, "FAIL")]
    print("  %-5s n=%d  PASS %.1f %%  FAIL %.1f %%  undecided %.1f %%" % (c, n, 100 * lc[(c, "PASS")] / n, 100 * lc[(c, "FAIL")] / n, 100 * (n - d) / n))
print("\nPer part: median over placements of L_mm / W_mm, spread (max-min) of L:")
for p, v in per.items():
    print("  %-13s L %6.2f  W %5.2f  L spread %.2f" % (p, np.nanmedian(v), np.nanmedian(perW[p]), np.nanmax(v) - np.nanmin(v)))
E = [r for r in rows if r["group"] == "empty"]
print("\nempty mat:", dict(collections.Counter(r["status"] for r in E)))
fr = np.array([int(r["frame"]) for r in rows])
print("frame numbers continuous inside recordings: jumps >1 in the whole file: %d (each recording start is a jump)" % int((np.diff(fr) > 1).sum()))
