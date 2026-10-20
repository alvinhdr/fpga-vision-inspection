"""
ai_eval.py - AI layer evaluation: can a small learned model use the measured features to judge parts?
Project: Real-Time FPGA Vision Inspection Station

The classic core (FPGA sums + ARM maths) stays unchanged. The model only sees the per-frame features that the board already
sends: length, width, area, fill and aspect ratio. Data: data/runs/20261020_final.csv (real board results, stale prefix
removed, first 20 lines of each recording dropped, MEASURED lines only).

  A) 5-class type recognition (good, bad_a, bad_b, bad_c, bad_d), validated leave-ONE-PLACEMENT-out:
     all placements of a part except one are used for training, the held-out placement is the test.
  B) NOVELTY test = the realistic task "reject a defect I have never seen": train on good bolts only
     (leave-one-good-placement-out), test on the held-out good placement (must be accepted) and on ALL bad parts
     (must be rejected). Compared with a plain tolerance rule fitted on the same good data only.

  .\\.venv\\Scripts\\python.exe py\\ai_eval.py data\\runs\\20261020_final.csv
"""
import collections
import csv
import os
import sys

import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uart_log import strip_stale_prefix  # noqa: E402

K_MM = 0.1728
FEATS = ["L_mm", "W_mm", "fill", "A_mm2"]


def load(path):
    rows, _ = strip_stale_prefix(list(csv.DictReader(open(path))))
    groups = collections.OrderedDict()
    for r in rows:
        if r["group"] in ("acc", "repeat"):
            groups.setdefault((r["part"], r["placement"], r["group"]), []).append(r)
    X, y, g = [], [], []
    for (part, pl, grp), R in groups.items():
        for r in R[20:]:
            if r["status"] != "MEASURED":
                continue
            L, W = float(r["L_mm"]), float(r["W_mm"])
            Lp, Wp, A = float(r["L_px"]), float(r["W_px"]), int(r["A_px"])
            X.append([L, W, A / (Lp * Wp), A * K_MM ** 2])
            y.append("good" if part.startswith("bolt_good") else part)
            g.append(f"{grp}:{part}:{pl}")
    return np.array(X), np.array(y), np.array(g)


def majority_by_group(pred, truth, g):
    ok = 0
    n = 0
    for k in sorted(set(g)):
        m = g == k
        p = collections.Counter(pred[m]).most_common(1)[0][0]
        ok += p == truth[m][0]
        n += 1
    return ok, n


def main():
    X, y, g = load(sys.argv[1])
    print(f"{len(X)} measured lines, {len(set(g))} recordings; classes {dict(collections.Counter(y))}")

    # ------------------------------------------------------------------ A) type recognition
    print("\nA) 5-class type recognition, leave-one-placement-out (frame level, then majority per recording)")
    # the 3 'repeat' recordings and the 3 'acc' placements of bolt_good_01 are different recordings: each is one group
    models = {
        "decision tree (depth 3)": lambda: DecisionTreeClassifier(max_depth=3, random_state=0),
        "k-NN (k=15, standardized)": None,
    }
    for name in models:
        pred = np.empty(len(y), dtype=object)
        for k in sorted(set(g)):
            te = g == k
            tr = ~te
            if name.startswith("decision"):
                m = models[name]().fit(X[tr], y[tr])
                pred[te] = m.predict(X[te])
            else:
                sc = StandardScaler().fit(X[tr])
                m = KNeighborsClassifier(15).fit(sc.transform(X[tr]), y[tr])
                pred[te] = m.predict(sc.transform(X[te]))
        acc = np.mean(pred == y)
        ok, n = majority_by_group(pred, y, g)
        print(f"  {name:<28} frame accuracy {100 * acc:5.1f} %   recordings correct {ok}/{n}")
        if name.startswith("decision"):
            cl = ["good", "bad_a", "bad_b", "bad_c", "bad_d"]
            print("   confusion (rows truth, columns predicted):  " + "  ".join(f"{c:>6}" for c in cl))
            for t in cl:
                row = [int(((y == t) & (pred == c)).sum()) for c in cl]
                print(f"   {t:>6}: " + "  ".join(f"{v:6d}" for v in row))
    full_tree = DecisionTreeClassifier(max_depth=3, random_state=0).fit(X, y)
    print("\n  tree fitted on all data (this is what could be exported to the ARM):")
    print("   " + export_text(full_tree, feature_names=FEATS).replace("\n", "\n   "))

    # ------------------------------------------------------------------ B) novelty: good only
    print("B) reject an UNSEEN defect: trained on good bolts only, leave-one-good-placement-out")
    good_groups = sorted({k for k in g if ":bolt_good" in k})
    bad_mask = y != "good"
    res = {"AI (Mahalanobis, 99th pct)": [0, 0, 0, 0], "tolerance rule (median +- 4.5 robust sigma)": [0, 0, 0, 0]}
    for k in good_groups:
        te = g == k
        trn = (y == "good") & ~te
        Xg = X[trn][:, :3]                                  # L, W, fill
        mu = Xg.mean(0)
        cov = np.cov(Xg.T) + 1e-6 * np.eye(3)
        ic = np.linalg.inv(cov)
        d = lambda Z: np.sqrt(np.einsum("ij,jk,ik->i", Z - mu, ic, Z - mu))
        thr = np.percentile(d(Xg), 99)
        med = np.median(Xg, 0)
        sig = 1.4826 * np.median(np.abs(Xg - med), 0) + 1e-6
        rule = lambda Z: np.all(np.abs(Z - med) <= 4.5 * sig, axis=1)[:]  # True = accept
        for key, accept in (("AI (Mahalanobis, 99th pct)", lambda Z: d(Z) <= thr),
                            ("tolerance rule (median +- 4.5 robust sigma)", rule)):
            r = res[key]
            a_good = accept(X[te][:, :3])
            a_bad = accept(X[bad_mask][:, :3])
            r[0] += a_good.sum(); r[1] += len(a_good); r[2] += (~a_bad).sum(); r[3] += len(a_bad)
    for key, r in res.items():
        print(f"  {key:<45} good accepted {100 * r[0] / r[1]:5.1f} %   bad rejected {100 * r[2] / r[3]:5.1f} %   (frame level)")
    # per bad type (AI), single fit on all good lines
    Xg = X[y == "good"][:, :3]; mu = Xg.mean(0); ic = np.linalg.inv(np.cov(Xg.T) + 1e-6 * np.eye(3))
    dd = lambda Z: np.sqrt(np.einsum("ij,jk,ik->i", Z - mu, ic, Z - mu))
    thr = np.percentile(dd(Xg), 99)
    print("  rejection per bad type (model fitted on all good lines, in-sample for good):")
    for t in ("bad_a", "bad_b", "bad_c", "bad_d"):
        print(f"   {t}: {100 * np.mean(dd(X[y == t][:, :3]) > thr):5.1f} % rejected")


if __name__ == "__main__":
    main()
