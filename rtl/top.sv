// =============================================================================
// File   : top.sv
// Project: Real-Time FPGA Vision Inspection Station
// Board  : Digilent Zybo Z7-10
// Purpose: Top level of the inspection station.
//          Adapted from fpga-edge-ai-video (CNN, ROI buffer and result CDC removed).
//
//   Laptop --HDMI--> dvi2rgb --(RGB + sync, clk_pix 74.25 MHz)--> insp_pipeline
//                                                        --> rgb2dvi --HDMI--> TV
//   insp_pipeline: position -> measurement core (threshold, 3x3 filter, moment sums, box) ->
//   result banks; video delayed 4 clocks and overlay drawn (6 clocks in total, no frame buffer).
//   ARM (PS, ps_bd) <-> AXI-Lite (clk_acc 100 MHz) <-> axil_insp: settings, result sets, overlay.
//   clk_ref (200 MHz) is made from the 125 MHz board clock for dvi2rgb (IDELAYCTRL + EDID).
//   Clock crossings: docs/CDC.md.
//
// LEDs:  led[0] blinks: clk_sys running   led[1] on: 200 MHz ref locked
//        led[2] on: HDMI input locked     led[3] blinks: pixel clock running
// Switches: sw[0] up: binary view   sw[1] up: hide the overlay
// =============================================================================
`default_nettype none

module top (
    // Board clock
    input  wire         sysclk,          // 125 MHz

    // HDMI RX (input from laptop)
    input  wire         hdmi_rx_clk_p,
    input  wire         hdmi_rx_clk_n,
    input  wire  [2:0]  hdmi_rx_p,
    input  wire  [2:0]  hdmi_rx_n,
    output wire         hdmi_rx_hpd,     // hot-plug detect: "a screen is connected"
    inout  wire         hdmi_rx_scl,     // DDC (I2C) clock, for EDID
    inout  wire         hdmi_rx_sda,     // DDC (I2C) data,  for EDID

    // HDMI TX (output to monitor)
    output wire         hdmi_tx_clk_p,
    output wire         hdmi_tx_clk_n,
    output wire  [2:0]  hdmi_tx_p,
    output wire  [2:0]  hdmi_tx_n,

    // Debug LEDs and switches
    output wire  [3:0]  led,
    input  wire  [1:0]  sw,

    // Zynq PS fixed pins (DDR memory and MIO). Connected to the ARM only.
    inout  wire  [14:0] DDR_addr,
    inout  wire  [2:0]  DDR_ba,
    inout  wire         DDR_cas_n,
    inout  wire         DDR_ck_n,
    inout  wire         DDR_ck_p,
    inout  wire         DDR_cke,
    inout  wire         DDR_cs_n,
    inout  wire  [3:0]  DDR_dm,
    inout  wire  [31:0] DDR_dq,
    inout  wire  [3:0]  DDR_dqs_n,
    inout  wire  [3:0]  DDR_dqs_p,
    inout  wire         DDR_odt,
    inout  wire         DDR_ras_n,
    inout  wire         DDR_reset_n,
    inout  wire         DDR_we_n,
    inout  wire         FIXED_IO_ddr_vrn,
    inout  wire         FIXED_IO_ddr_vrp,
    inout  wire  [53:0] FIXED_IO_mio,
    inout  wire         FIXED_IO_ps_clk,
    inout  wire         FIXED_IO_ps_porb,
    inout  wire         FIXED_IO_ps_srstb
);

    // -------------------------------------------------------------------------
    // Parameters
    // -------------------------------------------------------------------------
    localparam int SYS_BLINK_BIT = 26;   // 2^26 / 125 MHz   = 0.54 s (clk_sys) per LED toggle
    localparam int PIX_BLINK_BIT = 25;   // 2^25 / 74.25 MHz = 0.45 s per LED toggle

    // -------------------------------------------------------------------------
    // Clocks from the board oscillator (Clocking Wizard IP, PLL)
    //   clk_ref = 200 MHz for dvi2rgb, clk_sys = 125 MHz for our own slow logic.
    //   sysclk drives ONLY the PLL (see docs/TIMING.md, DRC REQP-1712).
    // -------------------------------------------------------------------------
    logic clk_ref;          // 200 MHz
    logic clk_sys;          // 125 MHz
    logic ref_locked;       // high when the PLL outputs are stable

    clk_wiz_ref u_clk_wiz_ref (
        .clk_in1  (sysclk),
        .clk_out1 (clk_ref),
        .clk_out2 (clk_sys),
        .locked   (ref_locked)
    );

    // -------------------------------------------------------------------------
    // HDMI input: TMDS -> parallel RGB (Digilent dvi2rgb)
    // -------------------------------------------------------------------------
    logic        clk_pix;           // recovered pixel clock (74.25 MHz at 720p)
    logic        pix_locked;        // high when the HDMI input is locked
    logic [23:0] rx_data;           // 24-bit pixel (Digilent channel order, see docs)
    logic        rx_de;             // data enable: 1 = visible pixel
    logic        rx_hsync;
    logic        rx_vsync;

    logic ddc_scl_i, ddc_scl_o, ddc_scl_t;
    logic ddc_sda_i, ddc_sda_o, ddc_sda_t;

    dvi2rgb_0 u_dvi2rgb (
        .TMDS_Clk_p    (hdmi_rx_clk_p),
        .TMDS_Clk_n    (hdmi_rx_clk_n),
        .TMDS_Data_p   (hdmi_rx_p),
        .TMDS_Data_n   (hdmi_rx_n),
        .RefClk        (clk_ref),
        .aRst_n        (ref_locked),     // hold in reset until clk_ref is stable
        .vid_pData     (rx_data),
        .vid_pVDE      (rx_de),
        .vid_pHSync    (rx_hsync),
        .vid_pVSync    (rx_vsync),
        .PixelClk      (clk_pix),
        .aPixelClkLckd (),               // deprecated, unused
        .pLocked       (pix_locked),
        .SDA_I         (ddc_sda_i),
        .SDA_O         (ddc_sda_o),
        .SDA_T         (ddc_sda_t),
        .SCL_I         (ddc_scl_i),
        .SCL_O         (ddc_scl_o),
        .SCL_T         (ddc_scl_t),
        .pRst_n        (1'b1)            // no extra synchronous reset
    );

    // DDC (I2C) pins are bidirectional: IOBUF = tri-state buffer.
    // T = 1 -> pin is released (input), T = 0 -> pin is driven with O.
    IOBUF u_iobuf_ddc_scl (.IO(hdmi_rx_scl), .I(ddc_scl_o), .T(ddc_scl_t), .O(ddc_scl_i));
    IOBUF u_iobuf_ddc_sda (.IO(hdmi_rx_sda), .I(ddc_sda_o), .T(ddc_sda_t), .O(ddc_sda_i));

    // Tell the laptop "a screen is connected" only after the EDID emulator
    // (clocked by clk_ref) is ready to answer.
    assign hdmi_rx_hpd = ref_locked;

    // -------------------------------------------------------------------------
    // Settings: clk_acc (AXI registers) -> clk_pix, ONE multi-bit req/ack crossing
    // (all bits change together; docs/CDC.md). Before the ARM runs, clk_acc is
    // stopped and the INIT values (= register reset values) are used.
    // -------------------------------------------------------------------------
    logic clk_acc, rst_acc_n;

    localparam int SET_W = $bits(insp_pkg::meas_cfg_t) + 1 + 1 + 3 + 11 + 11;
    localparam logic [SET_W-1:0] SET_INIT = {insp_pkg::CFG_DEFAULT, 1'b1, 1'b0, 3'd0, 11'd0, 11'd0};

    insp_pkg::meas_cfg_t acc_cfg, pix_cfg;
    logic                acc_ovl_en, acc_bin_view, pix_ovl_en, pix_bin_view;
    logic [2:0]          acc_verdict, pix_verdict;
    logic [10:0]         acc_cx, acc_cy, pix_cx, pix_cy;

    cdc_bus_sync #(.W(SET_W), .INIT(SET_INIT)) u_set_sync (
        .clk_src (clk_acc),
        .i_data  ({acc_cfg, acc_ovl_en, acc_bin_view, acc_verdict, acc_cx, acc_cy}),
        .clk_dst (clk_pix),
        .o_data  ({pix_cfg, pix_ovl_en, pix_bin_view, pix_verdict, pix_cx, pix_cy})
    );

    // Switches are asynchronous to clk_pix -> 2-flop synchronizers (docs/CDC.md)
    //   sw[0] up: binary view ("what the FPGA sees")   sw[1] up: hide the overlay
    logic sw_bin_pix, sw_hide_pix;
    cdc_sync_2ff u_sync_sw0 (.clk_dst(clk_pix), .d_async(sw[0]), .q_sync(sw_bin_pix));
    cdc_sync_2ff u_sync_sw1 (.clk_dst(clk_pix), .d_async(sw[1]), .q_sync(sw_hide_pix));

    // -------------------------------------------------------------------------
    // Pixel clock domain: position, measurement core, result banks, overlay
    // -------------------------------------------------------------------------
    video_pkg::video_t   rx_vid, tx_vid;
    insp_pkg::meas_res_t bank0, bank1;
    logic                done_toggle, sof_toggle;
    assign rx_vid = '{data: rx_data, de: rx_de, hs: rx_hsync, vs: rx_vsync};

    insp_pipeline u_insp (
        .clk_pix       (clk_pix),
        .i_vid         (rx_vid),
        .o_vid         (tx_vid),
        .i_cfg         (pix_cfg),
        .i_ovl_en      (pix_ovl_en && !sw_hide_pix),
        .i_bin_view    (pix_bin_view || sw_bin_pix),
        .i_verdict     (pix_verdict),
        .i_cx          (pix_cx),
        .i_cy          (pix_cy),
        .o_bank0       (bank0),
        .o_bank1       (bank1),
        .o_done_toggle (done_toggle),
        .o_sof_toggle  (sof_toggle)
    );

    logic [23:0] tx_data;
    logic        tx_de;
    logic        tx_hsync;
    logic        tx_vsync;

    assign tx_data  = tx_vid.data;
    assign tx_de    = tx_vid.de;
    assign tx_hsync = tx_vid.hs;
    assign tx_vsync = tx_vid.vs;

    // -------------------------------------------------------------------------
    // HDMI output: parallel RGB -> TMDS (Digilent rgb2dvi)
    // rgb2dvi makes its own 5x serial clock from clk_pix with an MMCM.
    // -------------------------------------------------------------------------
    rgb2dvi_0 u_rgb2dvi (
        .TMDS_Clk_p  (hdmi_tx_clk_p),
        .TMDS_Clk_n  (hdmi_tx_clk_n),
        .TMDS_Data_p (hdmi_tx_p),
        .TMDS_Data_n (hdmi_tx_n),
        .aRst_n      (pix_locked),       // hold in reset until the input is locked
        .vid_pData   (tx_data),
        .vid_pVDE    (tx_de),
        .vid_pHSync  (tx_hsync),
        .vid_pVSync  (tx_vsync),
        .PixelClk    (clk_pix)
    );

    // -------------------------------------------------------------------------
    // Zynq Processing System (ARM). Block design "ps_bd": PS + AXI-Lite master
    // port (M_AXI_LITE, base 0x43C0_0000) + clk_acc (100 MHz) and its reset.
    // -------------------------------------------------------------------------
    logic [31:0] axi_awaddr, axi_wdata, axi_araddr, axi_rdata;
    logic [3:0]  axi_wstrb;
    logic [1:0]  axi_bresp, axi_rresp;
    logic        axi_awvalid, axi_awready, axi_wvalid, axi_wready, axi_bvalid, axi_bready;
    logic        axi_arvalid, axi_arready, axi_rvalid, axi_rready;

    ps_bd_wrapper u_ps (
        .DDR_addr            (DDR_addr),
        .DDR_ba              (DDR_ba),
        .DDR_cas_n           (DDR_cas_n),
        .DDR_ck_n            (DDR_ck_n),
        .DDR_ck_p            (DDR_ck_p),
        .DDR_cke             (DDR_cke),
        .DDR_cs_n            (DDR_cs_n),
        .DDR_dm              (DDR_dm),
        .DDR_dq              (DDR_dq),
        .DDR_dqs_n           (DDR_dqs_n),
        .DDR_dqs_p           (DDR_dqs_p),
        .DDR_odt             (DDR_odt),
        .DDR_ras_n           (DDR_ras_n),
        .DDR_reset_n         (DDR_reset_n),
        .DDR_we_n            (DDR_we_n),
        .FIXED_IO_ddr_vrn    (FIXED_IO_ddr_vrn),
        .FIXED_IO_ddr_vrp    (FIXED_IO_ddr_vrp),
        .FIXED_IO_mio        (FIXED_IO_mio),
        .FIXED_IO_ps_clk     (FIXED_IO_ps_clk),
        .FIXED_IO_ps_porb    (FIXED_IO_ps_porb),
        .FIXED_IO_ps_srstb   (FIXED_IO_ps_srstb),
        .M_AXI_LITE_araddr   (axi_araddr),
        .M_AXI_LITE_arprot   (),
        .M_AXI_LITE_arready  (axi_arready),
        .M_AXI_LITE_arvalid  (axi_arvalid),
        .M_AXI_LITE_awaddr   (axi_awaddr),
        .M_AXI_LITE_awprot   (),
        .M_AXI_LITE_awready  (axi_awready),
        .M_AXI_LITE_awvalid  (axi_awvalid),
        .M_AXI_LITE_bready   (axi_bready),
        .M_AXI_LITE_bresp    (axi_bresp),
        .M_AXI_LITE_bvalid   (axi_bvalid),
        .M_AXI_LITE_rdata    (axi_rdata),
        .M_AXI_LITE_rready   (axi_rready),
        .M_AXI_LITE_rresp    (axi_rresp),
        .M_AXI_LITE_rvalid   (axi_rvalid),
        .M_AXI_LITE_wdata    (axi_wdata),
        .M_AXI_LITE_wready   (axi_wready),
        .M_AXI_LITE_wstrb    (axi_wstrb),
        .M_AXI_LITE_wvalid   (axi_wvalid),
        .clk_acc             (clk_acc),
        .rst_acc_n           (rst_acc_n)
    );

    // AXI-Lite registers (clk_acc): settings, result sets, overlay (docs/REGISTERS.md)
    axil_insp u_axil (
        .clk            (clk_acc),
        .rst_n          (rst_acc_n),
        .s_axi_awaddr   (axi_awaddr[15:0]),
        .s_axi_awvalid  (axi_awvalid),
        .s_axi_awready  (axi_awready),
        .s_axi_wdata    (axi_wdata),
        .s_axi_wstrb    (axi_wstrb),
        .s_axi_wvalid   (axi_wvalid),
        .s_axi_wready   (axi_wready),
        .s_axi_bresp    (axi_bresp),
        .s_axi_bvalid   (axi_bvalid),
        .s_axi_bready   (axi_bready),
        .s_axi_araddr   (axi_araddr[15:0]),
        .s_axi_arvalid  (axi_arvalid),
        .s_axi_arready  (axi_arready),
        .s_axi_rdata    (axi_rdata),
        .s_axi_rresp    (axi_rresp),
        .s_axi_rvalid   (axi_rvalid),
        .s_axi_rready   (axi_rready),
        .o_cfg          (acc_cfg),
        .o_ovl_en       (acc_ovl_en),
        .o_bin_view     (acc_bin_view),
        .o_verdict      (acc_verdict),
        .o_cx           (acc_cx),
        .o_cy           (acc_cy),
        .i_bank0        (bank0),
        .i_bank1        (bank1),
        .i_done_toggle  (done_toggle),
        .i_sof_toggle   (sof_toggle),
        .i_video_locked (pix_locked)
    );

    // -------------------------------------------------------------------------
    // Debug LEDs
    // -------------------------------------------------------------------------
    logic [SYS_BLINK_BIT:0] sys_cnt_q = '0;
    logic [PIX_BLINK_BIT:0] pix_cnt_q = '0;
    logic                   pix_locked_sys;

    always_ff @(posedge clk_sys)  sys_cnt_q <= sys_cnt_q + 1'b1;
    always_ff @(posedge clk_pix) pix_cnt_q <= pix_cnt_q + 1'b1;

    // pix_locked comes from the pixel clock domain -> synchronize to clk_sys.
    cdc_sync_2ff u_sync_pix_locked (
        .clk_dst (clk_sys),
        .d_async (pix_locked),
        .q_sync  (pix_locked_sys)
    );

    assign led[0] = sys_cnt_q[SYS_BLINK_BIT];
    assign led[1] = ref_locked;
    assign led[2] = pix_locked_sys;
    assign led[3] = pix_cnt_q[PIX_BLINK_BIT];

endmodule

`default_nettype wire
