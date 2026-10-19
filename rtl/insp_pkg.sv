// =============================================================================
// File   : insp_pkg.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: Shared types for the measurement core: settings and the per-frame result set.
//          Bit widths follow docs/MEASUREMENT.md section 5 (sized for the whole 1280 x 720 frame,
//          so no window setting can overflow). py/golden.py asserts the same widths.
// =============================================================================
`default_nettype none

package insp_pkg;

    localparam int CW = 11;     // coordinate width (0..2047), same as video_pkg::POS_W

    // Settings used by the measurement core (latched at the start of each frame)
    typedef struct packed {
        logic [CW-1:0] x0;      // window left column
        logic [CW-1:0] y0;      // window top row
        logic [CW-1:0] w;       // window width  (>= 1, x0 + w <= 1280; checked by software)
        logic [CW-1:0] h;       // window height (>= 1, y0 + h <= 720)
        logic [7:0]    thresh;  // T
        logic          pol;     // 1: object = gray > T, 0: object = gray < T
        logic          filt_en; // 1: 3x3 majority filter (>= 5 of 9)
    } meas_cfg_t;

    // One complete result set (MEASUREMENT.md section 5)
    typedef struct packed {
        logic [19:0]   a;       // object pixels
        logic [29:0]   sx;      // sum u
        logic [28:0]   sy;      // sum v
        logic [38:0]   sxx;     // sum u*u
        logic [37:0]   syy;     // sum v*v
        logic [37:0]   sxy;     // sum u*v
        logic [CW-1:0] umin, umax, vmin, vmax;   // 0x7FF / 0 when A = 0
    } meas_res_t;

    localparam meas_cfg_t CFG_DEFAULT = '{x0: 11'd400, y0: 11'd240, w: 11'd480, h: 11'd360,
                                          thresh: 8'd120, pol: 1'b1, filt_en: 1'b1};

endpackage

`default_nettype wire
