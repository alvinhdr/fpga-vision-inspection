"""
test_arm_math.py - PC test of the ARM maths in C (sw/inspect/insp_math.c) against the Python twin (py/measure.py).
Project: Real-Time FPGA Vision Inspection Station

1. py/golden.py computes the accumulators of every recorded frame (per-frame threshold: 120 dark / 180 bright, as in
   py/measure.py --report) and writes them to a CSV.
2. The C code (compiled with the MinGW gcc that ships inside Vivado, no install needed) turns each line into
   status / centre / angle / length / width / box ratio / mm / verdict.
3. Every number is compared with measure.frame_math() (relative error limit 1e-9).
Also runs a "mutation" (wrong window origin given to the C code) that MUST be detected.

  .\\.venv\\Scripts\\python.exe scripts\\test_arm_math.py data\\raw\\s1
"""
import csv
import glob
import math
import os
import subprocess
import sys

import cv2

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "py"))
from golden import FIELDS, Settings, measure_frame  # noqa: E402
import measure  # noqa: E402

GCC = r"C:\Xilinx\2025.1\tps\mingw\10.0.0\win64.o\nt\bin\gcc.exe"   # standalone MinGW-W64 gcc inside Vivado
STATUS = {0: "NOPART", 1: "EDGE", 2: "NOISY", 3: "MEASURED"}
K, L_NOM, L_TOL = 0.137, 10.0, 1.0       # arbitrary test calibration and tolerance


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "raw", "s1")
    build = os.path.join(ROOT, "build")
    os.makedirs(build, exist_ok=True)
    exe = os.path.join(build, "test_insp_math.exe")
    subprocess.run([GCC, "-O2", "-Wall", "-Wextra", "-o", exe,
                    os.path.join(ROOT, "sw", "test", "test_insp_math.c"),
                    os.path.join(ROOT, "sw", "inspect", "insp_math.c"),
                    "-I", os.path.join(ROOT, "sw", "inspect"), "-I", os.path.join(ROOT, "sw", "common"), "-lm"],
                   check=True)

    files = sorted(glob.glob(os.path.join(folder, "*.png")))
    csv_path = os.path.join(build, "acc_test.csv")
    py_res = {}
    with open(csv_path, "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["file"] + FIELDS)
        for fn in files:
            bgr = cv2.imread(fn)
            s = Settings()
            s.t = 180 if bgr[s.y0:s.y0 + s.h, s.x0:s.x0 + s.w].mean() > 45 else 120
            r = measure_frame(bgr, s)
            wr.writerow([os.path.basename(fn)] + [r[k] for k in FIELDS])
            py_res[os.path.basename(fn)] = measure.frame_math(r, s)

    def run_c(x0, y0, w, h):
        out = subprocess.run([exe, csv_path, str(x0), str(y0), str(w), str(h), str(K), str(L_NOM), str(L_TOL)],
                             capture_output=True, text=True, check=True).stdout
        return [ln.split(",") for ln in out.strip().splitlines()]

    def compare(rows, label):
        bad = 0
        for c in rows:
            name = c[0]
            p = py_res[name]
            status = STATUS[int(c[1])]
            errs = []
            if status != p["status"] and not (status == "MEASURED" and p["status"] == "MEASURED"):
                errs.append(f"status C {status} py {p['status']}")
            if status != "NOPART" and p["status"] != "NOPART":
                pairs = [("cx", float(c[2]), p["cx"]), ("cy", float(c[3]), p["cy"]),
                         ("theta", float(c[4]), p["theta_deg"]), ("L_px", float(c[5]), p["L_px"]),
                         ("W_px", float(c[6]), p["W_px"]), ("box_ratio", float(c[9]), p["box_ratio"])]
                if int(c[7]) != p["bbox_w"] or int(c[8]) != p["bbox_h"]:
                    errs.append("bbox")
                for n, a, b in pairs:
                    if abs(a - b) > 1e-9 * max(1.0, abs(b)):
                        errs.append(f"{n} C {a} py {b}")
                # verdict
                lmm = p["L_px"] * K
                py_v = 0
                if p["status"] == "MEASURED":
                    py_v = 2 if abs(lmm - L_NOM) > L_TOL else 1
                else:
                    py_v = 3
                if int(c[11]) != py_v:
                    errs.append(f"verdict C {c[11]} py {py_v}")
            if errs:
                bad += 1
                if bad <= 5:
                    print("  ", name, "; ".join(errs))
        print(f"{label}: {len(rows)} frames, {len(rows) - bad} agree, {bad} differ")
        return bad

    s0 = Settings()
    bad = compare(run_c(s0.x0, s0.y0, s0.w, s0.h), "C vs Python (correct window)")
    mut = compare(run_c(s0.x0 + 7, s0.y0, s0.w, s0.h), "mutation (window x0 + 7 given to C)")
    ok = bad == 0 and mut > 0
    print("RESULT:", "PASS" if ok else "FAIL (either C differs from Python, or the mutation was not detected)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
