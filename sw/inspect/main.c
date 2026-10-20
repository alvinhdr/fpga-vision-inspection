/* =============================================================================
 * File   : main.c
 * Project: Real-Time FPGA Vision Inspection Station
 * Purpose: ARM (Cortex-A9 core 0, bare metal) program. Once per video frame: read the result set of the
 *          hardware, do the maths (insp_math.c), decide PASS/FAIL, write the overlay registers, print one
 *          result line on the UART (115200 8N1). Commands come from the PC as text lines.
 *
 * Result line (docs/PROTOCOL.md, one line per frame, no floats on the wire, fixed decimals):
 *   R,<frame>,<status>,<A_px>,<cx>,<cy>,<L_px>,<W_px>,<angle_deg>,<L_mm>,<W_mm>,<verdict>
 *   status  = NOPART | EDGE | NOISY | MEASURED        verdict = PASS | FAIL | NOCAL | NONE
 *
 * Commands (end with Enter):
 *   ?          help                    s          status line (S,...)
 *   m 0|1      result lines off/on     t <0..255> threshold        p 0|1 polarity (1 = bright part)
 *   f 0|1      3x3 filter              o 0|1      overlay on the TV  b 0|1 binary view
 *   w x0 y0 W H  inspection window     n <mm> <tol> nominal length and tolerance (mm)
 *   v <mm> <tol> nominal width and tolerance (0 = width not checked)   g 0|1  median of 9 frames off/on (default on)
 *   k <mm>     calibrate: the part now in the window is <mm> long (needs a MEASURED frame)
 *   c <mm/px>  set the calibration directly (e.g. c 0.137)
 *   z          reset the skipped-frame counter
 * Note: xil_printf has no float support, so numbers are printed with fmt_fixed().
 * ========================================================================== */
#include <stdint.h>
#include <string.h>
#include "xil_printf.h"
#include "xparameters.h"
#include "xuartps_hw.h"
#include "sleep.h"

#define INSP_ON_BOARD
#include "insp_regs.h"
#include "insp_math.h"

static int  key_available(void) { return XUartPs_IsReceiveData(STDIN_BASEADDRESS); }
static char key_read(void)      { return (char)XUartPs_RecvByte(STDIN_BASEADDRESS); }

/* ---- tiny helpers (no float printf / scanf on this bare-metal setup) ---------------------------- */
static void fmt_fixed(char *out, double v, int dec)
{
    int neg = v < 0.0;
    if (neg) v = -v;
    uint32_t scale = 1;
    for (int i = 0; i < dec; i++) scale *= 10u;
    uint64_t q = (uint64_t)(v * (double)scale + 0.5);
    uint32_t ip = (uint32_t)(q / scale), fp = (uint32_t)(q % scale);
    char tmp[16]; int n = 0;
    if (neg && q != 0) *out++ = '-';
    do { tmp[n++] = (char)('0' + ip % 10u); ip /= 10u; } while (ip);
    while (n) *out++ = tmp[--n];
    if (dec) {
        *out++ = '.';
        for (int i = dec - 1; i >= 0; i--) { uint32_t d = fp; for (int j = 0; j < i; j++) d /= 10u; *out++ = (char)('0' + d % 10u); }
    }
    *out = 0;
}

static double parse_double(const char **sp)
{
    const char *s = *sp;
    while (*s == ' ') s++;
    int neg = (*s == '-'); if (neg) s++;
    double v = 0.0;
    while (*s >= '0' && *s <= '9') v = v * 10.0 + (*s++ - '0');
    if (*s == '.') { s++; double f = 0.1; while (*s >= '0' && *s <= '9') { v += (*s++ - '0') * f; f *= 0.1; } }
    *sp = s;
    return neg ? -v : v;
}

static const char *status_name(insp_status_t s)
{
    switch (s) { case INSP_NOPART: return "NOPART"; case INSP_EDGE: return "EDGE";
                 case INSP_NOISY: return "NOISY"; default: return "MEASURED"; }
}

static const char *verdict_name(unsigned v, const insp_geom_t *g, const insp_cfg_t *c)
{
    if (g->status != INSP_MEASURED) return "NONE";
    if (c->k_mm_per_px <= 0.0)      return "NOCAL";
    return v == INSP_VERDICT_PASS ? "PASS" : "FAIL";
}

/* ---- state ------------------------------------------------------------------------------------- */
static insp_window_t win = { 400, 240, 480, 360 };
static insp_cfg_t    cfg;
static insp_geom_t   last_geom;
static int           stream_on = 1;
static uint32_t      skipped = 0, results = 0;
/* WIN_POS and WIN_SIZE are two AXI writes, so one frame may be measured with a mixed window
 * (old position, new size). Results are ignored until two new result sets have passed. */
static uint32_t      ignore_until = 0;

/* Smoothing: the verdict uses the MEDIAN of the last SM_N valid length/width values, so one bad frame (a speck
 * of fluff, a flash on the metal) cannot flip PASS/FAIL. A speck frame (NOISY) is skipped and the last median is kept (at most
 * SM_MISS_MAX in a row); NOPART or EDGE clears the history. A part needs SM_MIN valid frames (83 ms at 60 fps) before it gets a verdict. `g 0` switches smoothing off. */
#define SM_N   9
#define SM_MIN 5
static double  sm_L[SM_N], sm_W[SM_N];
static int     sm_n = 0, sm_pos = 0, sm_miss = 0, smooth_on = 1;
#define SM_MISS_MAX 12      /* speck frames skipped in a row before the history is dropped */
static double  sm_cx = 0.0, sm_cy = 0.0;

static double median_n(const double *a, int n)
{
    double t[SM_N];
    for (int i = 0; i < n; i++) t[i] = a[i];
    for (int i = 1; i < n; i++) { double v = t[i]; int j = i - 1; while (j >= 0 && t[j] > v) { t[j + 1] = t[j]; j--; } t[j + 1] = v; }
    return t[n / 2];
}

static void apply_window(void)
{
    insp_wr(INSP_WIN_POS,  ((uint32_t)win.y0 << 16) | (uint32_t)win.x0);
    insp_wr(INSP_WIN_SIZE, ((uint32_t)win.h  << 16) | (uint32_t)win.w);
}

static void set_ctrl_bit(uint32_t bit, int on)
{
    uint32_t c = insp_rd(INSP_CTRL);
    insp_wr(INSP_CTRL, on ? (c | bit) : (c & ~bit));
}

static void print_status(void)
{
    char k[16], ln[16], lt[16], wn[16], wt[16];
    fmt_fixed(k, cfg.k_mm_per_px, 4); fmt_fixed(ln, cfg.L_nom, 2); fmt_fixed(lt, cfg.L_tol, 2);
    fmt_fixed(wn, cfg.W_nom, 2); fmt_fixed(wt, cfg.W_tol, 2);
    xil_printf("S,id=0x%08x,ctrl=0x%x,thresh=%u,win=%d %d %d %d,k_mm_px=%s,L_nom=%s,L_tol=%s,W_nom=%s,W_tol=%s,smooth=%d,frames=%u,results=%u,skipped=%u,video=%u\r\n",
               insp_rd(INSP_ID), insp_rd(INSP_CTRL), insp_rd(INSP_THRESH) & 0xFFu,
               win.x0, win.y0, win.w, win.h, k, ln, lt, wn, wt, smooth_on,
               insp_rd(INSP_PIX_FRAMES), results, skipped, (insp_rd(INSP_STATUS) >> 1) & 1u);
}

static void help(void)
{
    xil_printf("# commands: ? s m t p f o b w n k c z  (see top of sw/inspect/main.c)\r\n");
}

static void do_command(const char *line)
{
    const char *s = line + 1;
    char cmd = line[0];
    switch (cmd) {
        case '?': help(); break;
        case 's': print_status(); break;
        case 'z': skipped = 0; results = 0; break;
        case 'm': stream_on = (int)parse_double(&s) != 0; break;
        case 't': { int v = (int)parse_double(&s); insp_wr(INSP_THRESH, (uint32_t)(v < 0 ? 0 : v > 255 ? 255 : v)); break; }
        case 'p': set_ctrl_bit(INSP_CTRL_POL,         (int)parse_double(&s) != 0); break;
        case 'f': set_ctrl_bit(INSP_CTRL_FILT_EN,     (int)parse_double(&s) != 0); break;
        case 'o': set_ctrl_bit(INSP_CTRL_OVERLAY_EN,  (int)parse_double(&s) != 0); break;
        case 'b': set_ctrl_bit(INSP_CTRL_BINARY_VIEW, (int)parse_double(&s) != 0); break;
        case 'w': {
            int x0 = (int)parse_double(&s), y0 = (int)parse_double(&s), w = (int)parse_double(&s), h = (int)parse_double(&s);
            if (x0 < 0 || y0 < 0 || w < 1 || h < 1 || x0 + w > 1280 || y0 + h > 720) { xil_printf("ERR window outside 1280x720\r\n"); break; }
            win.x0 = x0; win.y0 = y0; win.w = w; win.h = h; apply_window();
            ignore_until = insp_rd(INSP_FRAME_CNT) + 2u;
            break;
        }
        case 'n': cfg.L_nom = parse_double(&s); cfg.L_tol = parse_double(&s); break;
        case 'v': cfg.W_nom = parse_double(&s); cfg.W_tol = parse_double(&s); break;       /* width check, tol 0 = off */
        case 'g': smooth_on = (int)parse_double(&s) != 0; sm_n = 0; sm_pos = 0; break;
        case 'c': cfg.k_mm_per_px = parse_double(&s); break;
        case 'k': {
            double known = parse_double(&s);
            double k = insp_calibrate(&last_geom, known);
            if (k <= 0.0) { xil_printf("ERR no MEASURED part in the window\r\n"); break; }
            cfg.k_mm_per_px = k;
            char b[16]; fmt_fixed(b, k, 4);
            xil_printf("K,%s\r\n", b);
            break;
        }
        default: xil_printf("ERR unknown command, ? for help\r\n"); break;
    }
}

int main(void)
{
    xil_printf("\r\n# === fpga-vision-inspection: ARM program ===\r\n");
    if (insp_rd(INSP_ID) != INSP_ID_VALUE)
        xil_printf("ERR wrong ID 0x%08x (wrong bitstream, or registers not built yet?)\r\n", insp_rd(INSP_ID));

    insp_default_cfg(&cfg);
    memset(&last_geom, 0, sizeof last_geom);
    apply_window();
    set_ctrl_bit(INSP_CTRL_OVERLAY_EN, 1);
    print_status();
    help();

    uint32_t last_id = insp_rd(INSP_FRAME_CNT);
    char line[48]; unsigned n = 0;

    while (1) {
        /* commands */
        while (key_available()) {
            char ch = key_read();
            if (ch == '\r' || ch == '\n') { if (n) { line[n] = 0; do_command(line); n = 0; } }
            else if (n < sizeof line - 1) line[n++] = ch;
        }

        /* a new result set? */
        uint32_t id = insp_rd(INSP_FRAME_CNT);
        if (id == last_id) { usleep(500); continue; }

        insp_acc_t r;
        uint32_t got = insp_read_result(&r);
        if (!got) continue;                                   /* could not read consistently: try again */
        if (got - last_id > 1u) skipped += got - last_id - 1u;
        last_id = got;
        if ((int32_t)(got - ignore_until) < 0) continue;      /* settings just changed */
        results++;

        insp_geom_t g;
        insp_geometry(&r, &win, &cfg, &g);
        if (smooth_on) {
            int held = 0;
            if (g.status == INSP_MEASURED) {
                sm_L[sm_pos] = g.L_px; sm_W[sm_pos] = g.W_px;
                sm_pos = (sm_pos + 1) % SM_N; if (sm_n < SM_N) sm_n++;
                sm_miss = 0; sm_cx = g.cx; sm_cy = g.cy;
            } else if (g.status == INSP_NOISY && sm_n >= SM_MIN && sm_miss < SM_MISS_MAX) {
                sm_miss++; held = 1;                       /* a speck frame: skip it, keep the last median */
            } else {
                sm_n = 0; sm_pos = 0; sm_miss = 0;         /* part gone, at the edge, or noise for too long */
            }
            if (sm_n >= SM_MIN && (g.status == INSP_MEASURED || held)) {
                g.L_px = median_n(sm_L, sm_n); g.W_px = median_n(sm_W, sm_n);
                if (held) { g.cx = sm_cx; g.cy = sm_cy; }
                if (cfg.k_mm_per_px > 0.0) { g.L_mm = g.L_px * cfg.k_mm_per_px; g.W_mm = g.W_px * cfg.k_mm_per_px; }
                g.status = INSP_MEASURED;
            } else if (g.status == INSP_MEASURED) {
                g.status = INSP_NOISY;                     /* still warming up: no verdict yet */
            }
        }
        unsigned v = insp_decide(&g, &cfg);
        if (g.status == INSP_MEASURED) last_geom = g;

        /* overlay: verdict colour + centre cross (frame coordinates) */
        insp_wr(INSP_OVL_VERDICT, g.status == INSP_NOPART ? INSP_VERDICT_NONE
                                  : (g.status == INSP_MEASURED && cfg.k_mm_per_px > 0.0) ? v : INSP_VERDICT_OTHER);
        insp_wr(INSP_OVL_CENTRE, ((uint32_t)(g.cy + 0.5) << 16) | (uint32_t)(g.cx + 0.5));

        if (stream_on) {
            char cx[16], cy[16], lp[16], wp[16], an[16], lm[16], wm[16];
            fmt_fixed(cx, g.cx, 1); fmt_fixed(cy, g.cy, 1); fmt_fixed(lp, g.L_px, 2); fmt_fixed(wp, g.W_px, 2);
            fmt_fixed(an, g.theta_deg, 1); fmt_fixed(lm, g.L_mm, 2); fmt_fixed(wm, g.W_mm, 2);
            xil_printf("R,%u,%s,%u,%s,%s,%s,%s,%s,%s,%s,%s\r\n", got, status_name(g.status), r.A,
                       cx, cy, lp, wp, an, lm, wm, verdict_name(v, &g, &cfg));
        }
    }
    return 0;
}
