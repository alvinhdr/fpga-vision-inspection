"""
sim_meas.py - bit-exact check of rtl/meas_core.sv against py/golden.py on recorded frames (Vivado xsim).
Project: Real-Time FPGA Vision Inspection Station

For each test case: the frames are written as raw RGB (build/sim/tb_meas_core/frames.bin), tb_meas_core plays
them with video timing, and every result line (A, SX, SY, SXX, SYY, SXY, UMIN, UMAX, VMIN, VMAX) is compared
with golden.measure_frame() using the same settings.

  .\\.venv\\Scripts\\python.exe scripts\\sim_meas.py                 (all cases, all frames of data/raw/s1)
  .\\.venv\\Scripts\\python.exe scripts\\sim_meas.py --quick         (2 frames, default settings)
  .\\.venv\\Scripts\\python.exe scripts\\sim_meas.py --case default --limit 20
Exit code 0 = every case bit-exact.
"""
import argparse
import glob
import os
import subprocess
import sys
import time

import cv2
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "py"))
from golden import FIELDS, Settings, measure_frame  # noqa: E402

VIVADO_BIN = os.environ.get("VIVADO_BIN", r"C:\Xilinx\2025.1\Vivado\bin")
SIM_DIR = os.path.join(ROOT, "build", "sim", "tb_meas_core")
SOURCES = ["rtl/video_pkg.sv", "rtl/insp_pkg.sv", "rtl/rgb2gray.sv", "rtl/pix_pos_counter.sv",
           "rtl/meas_core.sv", "tb/tb_meas_core.sv"]

# name: (settings, how many frames: None = all)
CASES = {
    "default":     (dict(x0=400, y0=240, w=480, h=360, t=120, pol=1, filt_en=1), None),
    "bright_t180": (dict(x0=400, y0=240, w=480, h=360, t=180, pol=1, filt_en=1), None),
    "filter_off":  (dict(x0=400, y0=240, w=480, h=360, t=120, pol=1, filt_en=0), 40),
    "pol0_t60":    (dict(x0=400, y0=240, w=480, h=360, t=60, pol=0, filt_en=1), 20),
    "full_frame":  (dict(x0=0, y0=0, w=1280, h=720, t=100, pol=1, filt_en=1), 12),
    "corner_br":   (dict(x0=1000, y0=500, w=280, h=220, t=60, pol=1, filt_en=1), 12),
    "tiny_1x1":    (dict(x0=640, y0=360, w=1, h=1, t=20, pol=1, filt_en=0), 6),
    "thin_3x2":    (dict(x0=630, y0=350, w=3, h=2, t=20, pol=1, filt_en=1), 6),
    "one_row":     (dict(x0=100, y0=300, w=1100, h=1, t=40, pol=1, filt_en=0), 6),
}


def build():
    os.makedirs(SIM_DIR, exist_ok=True)
    with open(os.path.join(SIM_DIR, "sim.prj"), "w") as f:
        for s in SOURCES:
            rel = os.path.relpath(os.path.join(ROOT, s), SIM_DIR).replace("\\", "/")
            f.write(f'sv xil_defaultlib "{rel}"\n')
    for cmd, log in (([os.path.join(VIVADO_BIN, "xvlog.bat"), "-sv", "-prj", "sim.prj"], "xvlog.log"),
                     ([os.path.join(VIVADO_BIN, "xelab.bat"), "-timescale", "1ns/1ps", "-s", "snap",
                       "xil_defaultlib.tb_meas_core"], "xelab.log")):
        with open(os.path.join(SIM_DIR, log), "w") as fh:
            if subprocess.run(cmd, cwd=SIM_DIR, stdout=fh, stderr=subprocess.STDOUT).returncode != 0:
                print(open(os.path.join(SIM_DIR, log)).read()[-3000:])
                sys.exit(f"{log} failed")


def run_case(name, st, files):
    s = Settings(**st)
    binf = os.path.join(SIM_DIR, "frames.bin")
    expected = []
    with open(binf, "wb") as fh:
        for fn in files:
            bgr = cv2.imread(fn)
            fh.write(np.ascontiguousarray(bgr[:, :, ::-1]).tobytes())        # R, G, B per pixel
            r = measure_frame(bgr, s)
            expected.append([r[k] for k in FIELDS])
    out = os.path.join(SIM_DIR, f"res_{name}.txt")
    # no "=" in plusargs: Windows .bat files split arguments at "="
    args = [f"IN_frames.bin", f"OUT_{os.path.basename(out)}", f"FRAMES_{len(files)}",
            f"X0_{s.x0}", f"Y0_{s.y0}", f"W_{s.w}", f"H_{s.h}", f"T_{s.t}", f"POL_{s.pol}", f"FILT_{s.filt_en}"]
    cmd = [os.path.join(VIVADO_BIN, "xsim.bat"), "snap", "-runall"]
    for a in args:
        cmd += ["-testplusarg", a]
    t0 = time.time()
    with open(os.path.join(SIM_DIR, f"xsim_{name}.log"), "w") as fh:
        subprocess.run(cmd, cwd=SIM_DIR, stdout=fh, stderr=subprocess.STDOUT)
    log = open(os.path.join(SIM_DIR, f"xsim_{name}.log")).read()
    got = [[int(v) for v in ln.split()] for ln in open(out).read().split("\n") if ln.strip()] if os.path.exists(out) else []
    bad = 0
    for i, (e, g) in enumerate(zip(expected, got)):
        if e != g:
            bad += 1
            if bad <= 3:
                print(f"   frame {os.path.basename(files[i])}: golden {e}\n{'':>12}rtl    {g}")
    ok = bad == 0 and len(got) == len(expected) and "TEST DONE" in log
    print(f"{name:<12} {len(files):>3} frames  {len(got):>3} results  {len(expected) - bad if len(got) == len(expected) else '-':>3} "
          f"bit-exact   {'PASS' if ok else 'FAIL'}   ({time.time() - t0:.0f} s)")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=os.path.join(ROOT, "data", "raw", "s1"))
    ap.add_argument("--case", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    files = sorted(glob.glob(os.path.join(args.folder, "*.png")))
    build()
    cases = {"default": CASES["default"]} if args.quick else ({args.case: CASES[args.case]} if args.case else CASES)
    all_ok = True
    for name, (st, n) in cases.items():
        lim = 2 if args.quick else (args.limit or n)
        # spread the chosen frames over the whole set (dark and bright, all labels)
        sel = files if not lim or lim >= len(files) else [files[int(i)] for i in np.linspace(0, len(files) - 1, lim)]
        all_ok &= run_case(name, st, sel)
    print("ALL CASES BIT-EXACT" if all_ok else "SOME CASES FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
