# =============================================================================
# File   : make_diagram.py
# Project: Real-Time FPGA Vision Inspection Station (adapted from fpga-edge-ai-video)
# Purpose: Make the architecture diagram in the standard diagrams.net (draw.io) look:
#            docs/images/architecture.drawio   editable file (open it at app.diagrams.net)
#            docs/images/architecture-bw.png   picture for the README, drawn from the SAME shapes
#          Both come from one list of boxes and arrows below, so they always match.
#
# Usage  : .venv\Scripts\python.exe scripts/make_diagram.py
# Needs  : Pillow, Windows fonts Arial (arial.ttf, arialbd.ttf)
# =============================================================================
import html
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_PNG = os.path.join(ROOT, "docs", "images", "architecture-bw.png")
OUT_XML = os.path.join(ROOT, "docs", "images", "architecture.drawio")
FONT = r"C:\Windows\Fonts\arial.ttf"
FONT_B = r"C:\Windows\Fonts\arialbd.ttf"

W, H = 960, 500

# black and white: white boxes, black outlines (the two clock sides are marked by a divider line, see DIVIDER_Y)
BLUE = GREEN = YELLOW = GRAY = ("#ffffff", "#000000")
DIVIDER_Y = 298

# id: (x, y, w, h, [(line, bold), ...], colors)
NODES = {
    "cam": (10, 80, 100, 70, [("Phone camera", True), ("IP Webcam", False)], YELLOW),
    "laptop": (135, 80, 105, 70, [("Laptop", True), ("full screen", False), ("720p60", False)], YELLOW),
    "hdmiin": (265, 80, 100, 70, [("HDMI in", True), ("(Digilent IP)", False)], BLUE),
    "overlay": (400, 80, 170, 70, [("Overlay", True), ("frame, box, cross,", False), ("binary view", False)], BLUE),
    "hdmiout": (600, 80, 100, 70, [("HDMI out", True), ("(Digilent IP)", False)], BLUE),
    "tv": (730, 80, 130, 70, [("Monitor", True), ("picture + result", False)], YELLOW),
    "meas": (265, 200, 305, 80, [("Measurement core (SystemVerilog)", True), ("threshold, 3x3 filter,", False),
                                 ("sums A, x, y, x2, y2, xy + bounding box", False)], GREEN),
    "banks": (600, 200, 120, 80, [("Result banks", True), ("2 banks", False)], BLUE),
    "arm": (265, 360, 305, 100, [("ARM CPU (C) + AXI-Lite registers", True), ("centre, angle, length, width,", False),
                                 ("mm, PASS/FAIL, median of 9 frames", False)], GRAY),
    "pc": (650, 360, 170, 100, [("PC (UART 115200)", True), ("logger, viewer,", False), ("replay", False)], GRAY),
}

# edges: id, source, target, exit (x, y), entry (x, y), waypoints, both_ends
EDGES = [
    ("e1", "cam", "laptop", (1, 0.5), (0, 0.5), [], False),
    ("e2", "laptop", "hdmiin", (1, 0.5), (0, 0.5), [], False),
    ("e3", "hdmiin", "overlay", (1, 0.5), (0, 0.5), [], False),
    ("e4", "overlay", "hdmiout", (1, 0.5), (0, 0.5), [], False),
    ("e5", "hdmiout", "tv", (1, 0.5), (0, 0.5), [], False),
    ("e6", "hdmiin", "meas", (0.3, 1), (0.1, 0), [], False),
    ("e7", "meas", "banks", (1, 0.5), (0, 0.5), [], False),
    ("e8", "banks", "arm", (0.2, 1), (0.9, 0), [(624, 330), (539, 330)], False),
    ("e9", "arm", "pc", (1, 0.5), (0, 0.5), [], True),
]

# free text: id, x, y, text lines, anchor ("l" left, "c" centre, "r" right of x)
LABELS = [
    ("t2", 636, 318, ["crosses to the 100 MHz side", "(toggle + bank pointer)"], "l"),
    ("t3", 485, 34, ["verdict colour + centre cross are written by the ARM, drawn on the next frame"], "c"),
    ("t4", 620, 176, ["no frame buffer: a pixel leaves 81 ns after it came in, 60 frames/s"], "c"),
    ("t5", 20, 482, ["Digilent Zybo Z7-10 (FPGA + ARM). Every clock crossing is listed in docs/CDC.md"], "l"),
    ("t6", 20, DIVIDER_Y - 11, ["video side: 74.25 MHz"], "l"),
    ("t7", 20, DIVIDER_Y + 12, ["ARM side: 100 MHz"], "l"),
]

LEGEND = []          # no colour legend in the black-and-white version
LEG_X = ()
LEG_Y = 0


def edge_points(src, dst, ex, en, via):
    sx, sy, sw, sh = NODES[src][:4]
    dx, dy, dw, dh = NODES[dst][:4]
    p0 = (sx + sw * ex[0], sy + sh * ex[1])
    p1 = (dx + dw * en[0], dy + dh * en[1])
    return [p0, *via, p1]


# ----------------------------------------------------------------------------- PNG
def make_png():
    S = 3
    img = Image.new("RGB", (W * S, H * S), "white")
    d = ImageDraw.Draw(img)

    def f(size, bold=False):
        return ImageFont.truetype(FONT_B if bold else FONT, int(size * S))

    def put(x, y, s, size, bold, anchor):
        d.text((x * S, y * S), s, font=f(size, bold), fill="black", anchor=anchor)

    for _, (x, y, w, h, lines, (fill, stroke)) in NODES.items():
        d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=9 * S, fill=fill, outline=stroke, width=int(1.6 * S))
        lh = 16
        y0 = y + h / 2 - (len(lines) - 1) * lh / 2
        for i, (line, bold) in enumerate(lines):
            put(x + w / 2, y0 + i * lh, line, 12.5, bold, "mm")

    def arrowhead(p, q):
        import math
        a = math.atan2(q[1] - p[1], q[0] - p[0])
        L, Wd = 11, 5.5
        base = (q[0] - L * math.cos(a), q[1] - L * math.sin(a))
        pts = [q, (base[0] + Wd * math.sin(a), base[1] - Wd * math.cos(a)), (base[0] - Wd * math.sin(a), base[1] + Wd * math.cos(a))]
        d.polygon([(px * S, py * S) for px, py in pts], fill="black")
        return base

    d.line([(20 * S, DIVIDER_Y * S), ((W - 20) * S, DIVIDER_Y * S)], fill="black", width=int(1.6 * S))

    for _, src, dst, ex, en, via, both in EDGES:
        pts = edge_points(src, dst, ex, en, via)
        line = list(pts)
        line[-1] = arrowhead(pts[-2], pts[-1])
        if both:
            line[0] = arrowhead(pts[1], pts[0])
        d.line([(px * S, py * S) for px, py in line], fill="black", width=int(1.6 * S), joint="curve")

    for _, x, y, lines, anchor in LABELS:
        a = {"l": "lm", "c": "mm", "r": "rm"}[anchor]
        small = y > 470
        for i, line in enumerate(lines):
            put(x, y + i * 15 - (len(lines) - 1) * 7.5, line, 11 if not small else 10.5, False, a)

    for (fill, stroke), x, (_, label) in zip([c for c, _ in LEGEND], LEG_X, LEGEND):
        d.rounded_rectangle([x * S, LEG_Y * S, (x + 22) * S, (LEG_Y + 16) * S], radius=4 * S, fill=fill, outline=stroke, width=int(1.4 * S))
        put(x + 30, LEG_Y + 8, label, 11.5, False, "lm")

    img = img.resize((W * 2, H * 2), Image.LANCZOS)
    img.save(OUT_PNG, optimize=True)
    print("saved", OUT_PNG, img.size)


# ----------------------------------------------------------------------------- draw.io XML
def make_xml():
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']

    def label_html(lines):
        parts = [f"<b>{html.escape(t)}</b>" if bold else html.escape(t) for t, bold in lines]
        return html.escape("<br>".join(parts), quote=True)

    for nid, (x, y, w, h, lines, (fill, stroke)) in NODES.items():
        style = f"rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor={fill};strokeColor={stroke};fontSize=12;"
        cells.append(f'<mxCell id="{nid}" value="{label_html(lines)}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    for eid, src, dst, ex, en, via, both in EDGES:
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;startArrow={'classic' if both else 'none'};"
                 f"exitX={ex[0]};exitY={ex[1]};entryX={en[0]};entryY={en[1]};strokeColor=#000000;")
        pts = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in via)
        arr = f'<Array as="points">{pts}</Array>' if via else ""
        cells.append(f'<mxCell id="{eid}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
                     f'<mxGeometry relative="1" as="geometry">{arr}</mxGeometry></mxCell>')

    cells.append('<mxCell id="divider" style="endArrow=none;html=1;strokeColor=#000000;strokeWidth=1.5;" edge="1" parent="1">'
                 f'<mxGeometry relative="1" as="geometry"><mxPoint x="20" y="{DIVIDER_Y}" as="sourcePoint"/>'
                 f'<mxPoint x="{W - 20}" y="{DIVIDER_Y}" as="targetPoint"/></mxGeometry></mxCell>')

    for tid, x, y, lines, anchor in LABELS:
        align = {"l": "left", "c": "center", "r": "right"}[anchor]
        w = 330
        x0 = {"l": x, "c": x - w / 2, "r": x - w}[anchor]
        h = 15 * len(lines) + 6
        txt = html.escape("<br>".join(html.escape(t) for t in lines), quote=True)
        cells.append(f'<mxCell id="{tid}" value="{txt}" style="text;html=1;align={align};verticalAlign=middle;fontSize=11;" vertex="1" parent="1">'
                     f'<mxGeometry x="{x0}" y="{y - h / 2}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    for i, ((fill, stroke), x, (_, label)) in enumerate(zip([c for c, _ in LEGEND], LEG_X, LEGEND)):
        cells.append(f'<mxCell id="lg{i}" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{LEG_Y}" width="22" height="16" as="geometry"/></mxCell>')
        cells.append(f'<mxCell id="lt{i}" value="{html.escape(label)}" style="text;html=1;align=left;verticalAlign=middle;fontSize=11;" vertex="1" parent="1">'
                     f'<mxGeometry x="{x + 30}" y="{LEG_Y - 2}" width="180" height="20" as="geometry"/></mxCell>')

    xml = ('<mxfile host="app.diagrams.net"><diagram name="Architecture" id="arch">'
           f'<mxGraphModel dx="{W}" dy="{H}" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
           f'pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0"><root>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")
    with open(OUT_XML, "w", encoding="utf-8") as fh:
        fh.write(xml)
    print("saved", OUT_XML)


if __name__ == "__main__":
    make_png()
    make_xml()
