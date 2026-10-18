/* =============================================================================
 * File   : test_insp_math.c
 * Project: Real-Time FPGA Vision Inspection Station
 * Purpose: PC test of insp_math.c. Reads the accumulator CSV written by py/golden.py (--out) and prints
 *          one result line per frame; scripts/test_arm_math.py compares it with py/measure.py.
 *   usage: test_insp_math <acc.csv> <x0> <y0> <w> <h> [k_mm_per_px L_nom L_tol]
 * CSV columns: file,A,SX,SY,SXX,SYY,SXY,UMIN,UMAX,VMIN,VMAX
 * Output:      file,status,cx,cy,theta_deg,L_px,W_px,bbox_w,bbox_h,box_ratio,L_mm,verdict
 * ========================================================================== */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "insp_math.h"

int main(int argc, char **argv)
{
    if (argc < 6) { fprintf(stderr, "usage: %s acc.csv x0 y0 w h [k Lnom Ltol]\n", argv[0]); return 2; }
    FILE *f = fopen(argv[1], "r");
    if (!f) { perror("open"); return 2; }
    insp_window_t win = { atoi(argv[2]), atoi(argv[3]), atoi(argv[4]), atoi(argv[5]) };
    insp_cfg_t cfg;
    insp_default_cfg(&cfg);
    if (argc >= 9) { cfg.k_mm_per_px = atof(argv[6]); cfg.L_nom = atof(argv[7]); cfg.L_tol = atof(argv[8]); }

    char line[512];
    if (!fgets(line, sizeof line, f)) return 2;          /* header */
    while (fgets(line, sizeof line, f)) {
        char name[256];
        unsigned long long A, SX, SY, SXX, SYY, SXY;
        unsigned umin, umax, vmin, vmax;
        if (sscanf(line, "%255[^,],%llu,%llu,%llu,%llu,%llu,%llu,%u,%u,%u,%u",
                   name, &A, &SX, &SY, &SXX, &SYY, &SXY, &umin, &umax, &vmin, &vmax) != 11) continue;
        insp_acc_t r = { (uint32_t)A, (uint32_t)SX, (uint32_t)SY, SXX, SYY, SXY, umin, umax, vmin, vmax };
        insp_geom_t g;
        insp_geometry(&r, &win, &cfg, &g);
        printf("%s,%d,%.12g,%.12g,%.12g,%.12g,%.12g,%d,%d,%.12g,%.12g,%u\n", name, (int)g.status, g.cx, g.cy,
               g.theta_deg, g.L_px, g.W_px, g.bbox_w, g.bbox_h, g.box_ratio, g.L_mm, insp_decide(&g, &cfg));
    }
    fclose(f);
    return 0;
}
