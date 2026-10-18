/* =============================================================================
 * File   : insp_regs.h
 * Project: Real-Time FPGA Vision Inspection Station (pattern from fpga-edge-ai-video)
 * Purpose: Register map of the AXI4-Lite slave (docs/REGISTERS.md, PROPOSED in M2, final in M4).
 *          Base address = AXIL_BASE in scripts/build_hw.tcl.
 * ========================================================================== */
#ifndef INSP_REGS_H
#define INSP_REGS_H

#include <stdint.h>

#define INSP_BASE          0x43C00000u

#define INSP_ID            0x000u   /* RO  0x1A570001                                        */
#define INSP_CTRL          0x004u   /* RW  [0] POL [1] FILT_EN [2] OVERLAY_EN [3] BINARY_VIEW */
#define INSP_THRESH        0x008u   /* RW  [7:0] threshold T                                 */
#define INSP_WIN_POS       0x00Cu   /* RW  [10:0] x0  [26:16] y0                             */
#define INSP_WIN_SIZE      0x010u   /* RW  [10:0] W   [26:16] H                              */
#define INSP_STATUS        0x014u   /* RO  [0] READY_BANK [1] VIDEO_LOCKED                   */
#define INSP_FRAME_CNT     0x018u   /* RO  complete result sets since reset                  */
#define INSP_PIX_FRAMES    0x01Cu   /* RO  all video frames seen since reset                 */

#define INSP_R_A           0x040u   /* RO  [19:0]                                            */
#define INSP_R_SX          0x044u   /* RO  [29:0]                                            */
#define INSP_R_SY          0x048u   /* RO  [28:0]                                            */
#define INSP_R_SXX_LO      0x04Cu
#define INSP_R_SXX_HI      0x050u   /* RO  [6:0]                                             */
#define INSP_R_SYY_LO      0x054u
#define INSP_R_SYY_HI      0x058u   /* RO  [5:0]                                             */
#define INSP_R_SXY_LO      0x05Cu
#define INSP_R_SXY_HI      0x060u   /* RO  [5:0]                                             */
#define INSP_R_BBOX_U      0x064u   /* RO  [10:0] UMIN  [26:16] UMAX                         */
#define INSP_R_BBOX_V      0x068u   /* RO  [10:0] VMIN  [26:16] VMAX                         */
#define INSP_R_FRAME_ID    0x06Cu   /* RO  FRAME_CNT value of this result set                */

#define INSP_OVL_VERDICT   0x080u   /* RW  [2:0] 0 none 1 PASS 2 FAIL 3 NOISY/EDGE           */
#define INSP_OVL_CENTRE    0x084u   /* RW  [10:0] cx  [26:16] cy (frame coordinates)         */

#define INSP_CTRL_POL          (1u << 0)
#define INSP_CTRL_FILT_EN      (1u << 1)
#define INSP_CTRL_OVERLAY_EN   (1u << 2)
#define INSP_CTRL_BINARY_VIEW  (1u << 3)

#define INSP_ID_VALUE      0x1A570001u
#define INSP_CLK_MHZ       100u      /* clk_acc */

#define INSP_VERDICT_NONE  0u
#define INSP_VERDICT_PASS  1u
#define INSP_VERDICT_FAIL  2u
#define INSP_VERDICT_OTHER 3u

/* Raw per-frame sums, exactly the values of py/golden.py (docs/MEASUREMENT.md section 5). */
typedef struct {
    uint32_t A, SX, SY;
    uint64_t SXX, SYY, SXY;
    uint32_t umin, umax, vmin, vmax;
} insp_acc_t;

/* Only on the board (Xilinx BSP): memory-mapped access and the safe read of a result set. */
#ifdef INSP_ON_BOARD
#include "xil_io.h"

static inline uint32_t insp_rd(uint32_t off)           { return Xil_In32(INSP_BASE + off); }
static inline void     insp_wr(uint32_t off, uint32_t v) { Xil_Out32(INSP_BASE + off, v); }

/* Read the newest complete result set. Returns the frame id, or 0 if it could not be read consistently. */
static inline uint32_t insp_read_result(insp_acc_t *r)
{
    for (int tries = 0; tries < 4; tries++) {
        uint32_t id0 = insp_rd(INSP_FRAME_CNT);
        r->A   = insp_rd(INSP_R_A);
        r->SX  = insp_rd(INSP_R_SX);
        r->SY  = insp_rd(INSP_R_SY);
        r->SXX = ((uint64_t)insp_rd(INSP_R_SXX_HI) << 32) | insp_rd(INSP_R_SXX_LO);
        r->SYY = ((uint64_t)insp_rd(INSP_R_SYY_HI) << 32) | insp_rd(INSP_R_SYY_LO);
        r->SXY = ((uint64_t)insp_rd(INSP_R_SXY_HI) << 32) | insp_rd(INSP_R_SXY_LO);
        uint32_t bu = insp_rd(INSP_R_BBOX_U), bv = insp_rd(INSP_R_BBOX_V);
        r->umin = bu & 0x7FFu; r->umax = (bu >> 16) & 0x7FFu;
        r->vmin = bv & 0x7FFu; r->vmax = (bv >> 16) & 0x7FFu;
        uint32_t fid = insp_rd(INSP_R_FRAME_ID);
        uint32_t id1 = insp_rd(INSP_FRAME_CNT);
        if (fid == id0 && (id1 - id0) < 2u) return fid;
    }
    return 0;
}
#endif /* INSP_ON_BOARD */

#endif
