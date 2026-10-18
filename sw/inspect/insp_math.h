/* =============================================================================
 * File   : insp_math.h
 * Project: Real-Time FPGA Vision Inspection Station
 * Purpose: The ARM's per-frame maths (docs/MEASUREMENT.md section 6): sums -> centre, angle, length,
 *          width, millimetres, status and PASS/FAIL. Pure C (no Xilinx headers), so the same file is
 *          compiled for the ARM and for the PC test (sw/inspect/test_insp_math.c).
 *          Python twin: py/measure.py frame_math() - both must give the same numbers.
 * ========================================================================== */
#ifndef INSP_MATH_H
#define INSP_MATH_H

#include <stdint.h>
#include "insp_regs.h"

typedef enum {
    INSP_NOPART = 0,   /* A < a_min                                                         */
    INSP_EDGE,         /* bounding box touches the window edge: part not fully inside        */
    INSP_NOISY,        /* box ratio too big: far specks spoil the moments                    */
    INSP_MEASURED      /* geometry is valid                                                  */
} insp_status_t;

typedef struct { int x0, y0, w, h; } insp_window_t;

typedef struct {
    insp_status_t status;
    double cx, cy;          /* centre in FRAME coordinates (window origin added)  */
    double theta_deg;       /* long axis angle, image y points down               */
    double L_px, W_px;      /* equivalent rectangle length / width                */
    int    bbox_w, bbox_h;
    double box_ratio;
    double L_mm, W_mm;      /* only valid when the calibration k > 0              */
} insp_geom_t;

typedef struct {
    double k_mm_per_px;     /* calibration; 0 = not calibrated                    */
    double L_nom, L_tol;    /* nominal length and tolerance in mm                 */
    double W_nom, W_tol;    /* W_tol <= 0: width is not checked                   */
    uint32_t a_min;         /* minimum area in pixels                             */
    double box_ratio_max;   /* 1.5 (MEASUREMENT.md section 6)                     */
} insp_cfg_t;

void insp_default_cfg(insp_cfg_t *c);
void insp_geometry(const insp_acc_t *r, const insp_window_t *win, const insp_cfg_t *c, insp_geom_t *g);
/* Returns INSP_VERDICT_PASS / FAIL for status MEASURED, INSP_VERDICT_OTHER otherwise (NOPART, EDGE, NOISY). */
unsigned insp_decide(const insp_geom_t *g, const insp_cfg_t *c);
/* mm per pixel from one measurement of a reference part of known length. Returns 0 if not measurable. */
double insp_calibrate(const insp_geom_t *g, double known_length_mm);

#endif
