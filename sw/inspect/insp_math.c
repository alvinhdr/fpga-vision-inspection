/* =============================================================================
 * File   : insp_math.c
 * Project: Real-Time FPGA Vision Inspection Station
 * Purpose: See insp_math.h. Formulas: docs/MEASUREMENT.md section 6.
 *          All sums are exact integers below 2^53, so double arithmetic loses nothing.
 * ========================================================================== */
#include <math.h>
#include "insp_math.h"

#define RAD2DEG (180.0 / 3.14159265358979323846)

void insp_default_cfg(insp_cfg_t *c)
{
    c->k_mm_per_px   = 0.0;
    c->L_nom = 0.0; c->L_tol = 0.0;
    c->W_nom = 0.0; c->W_tol = 0.0;
    c->a_min         = 50;
    c->box_ratio_max = 1.5;
}

void insp_geometry(const insp_acc_t *r, const insp_window_t *win, const insp_cfg_t *c, insp_geom_t *g)
{
    g->status = INSP_NOPART;
    g->cx = g->cy = g->theta_deg = g->L_px = g->W_px = g->box_ratio = g->L_mm = g->W_mm = 0.0;
    g->bbox_w = g->bbox_h = 0;
    if (r->A < c->a_min || r->A == 0) return;           /* never divide by A = 0 */

    const double A   = (double)r->A;
    const double cx  = (double)r->SX / A;
    const double cy  = (double)r->SY / A;
    const double m20 = (double)r->SXX / A - cx * cx;
    const double m02 = (double)r->SYY / A - cy * cy;
    const double m11 = (double)r->SXY / A - cx * cy;
    const double half = (m20 + m02) / 2.0;
    const double d    = sqrt(((m20 - m02) / 2.0) * ((m20 - m02) / 2.0) + m11 * m11);
    const double l1   = half + d;
    double l2         = half - d;
    if (l2 < 0.0) l2 = 0.0;

    g->cx        = cx + (double)win->x0;
    g->cy        = cy + (double)win->y0;
    g->theta_deg = 0.5 * atan2(2.0 * m11, m20 - m02) * RAD2DEG;
    g->L_px      = sqrt(12.0 * l1 + 1.0);
    g->W_px      = sqrt(12.0 * l2 + 1.0);
    g->bbox_w    = (int)r->umax - (int)r->umin + 1;
    g->bbox_h    = (int)r->vmax - (int)r->vmin + 1;
    g->box_ratio = (double)g->bbox_w * (double)g->bbox_h / (((g->L_px + g->W_px) * (g->L_px + g->W_px)) / 2.0);
    if (c->k_mm_per_px > 0.0) {
        g->L_mm = g->L_px * c->k_mm_per_px;
        g->W_mm = g->W_px * c->k_mm_per_px;
    }

    const int edge = (r->umin == 0u) || (r->vmin == 0u) ||
                     ((int)r->umax == win->w - 1) || ((int)r->vmax == win->h - 1);
    if (edge)                                   g->status = INSP_EDGE;
    else if (g->box_ratio > c->box_ratio_max)   g->status = INSP_NOISY;
    else                                        g->status = INSP_MEASURED;
}

unsigned insp_decide(const insp_geom_t *g, const insp_cfg_t *c)
{
    if (g->status != INSP_MEASURED || c->k_mm_per_px <= 0.0) return INSP_VERDICT_OTHER;
    if (fabs(g->L_mm - c->L_nom) > c->L_tol) return INSP_VERDICT_FAIL;
    if (c->W_tol > 0.0 && fabs(g->W_mm - c->W_nom) > c->W_tol) return INSP_VERDICT_FAIL;
    return INSP_VERDICT_PASS;
}

double insp_calibrate(const insp_geom_t *g, double known_length_mm)
{
    if (g->status != INSP_MEASURED || g->L_px <= 0.0 || known_length_mm <= 0.0) return 0.0;
    return known_length_mm / g->L_px;
}
