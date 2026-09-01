"""Generate the merged board's PCB with the mechanically-constrained parts
already placed, and everything else staged off-board.

Placed at their original positions:
  * the six motor driver ICs  - 4x DRV8876 (motor section) and 2x MP6541A
    (driver section)
  * every connector           - XT60 inlet, both USB-C receptacles, the motor
    output headers, the axis encoder ports and the vacuum control header

Each section keeps its internal geometry exactly; the driver section is
translated as a rigid body so the two sit side by side.  The original board
outlines are drawn on Dwgs.User so you can see where each one sat.

Everything else is dropped into a staging grid to the right of the board, with
its original rotation and side preserved, for you to place by hand.

Footprint instances are lifted verbatim out of the two source PCBs, so pad
shapes, back-side mirroring, teardrop settings and 3D models all survive; only
the position, reference, net names and schematic path are rewritten.

    python3 tools/pcb_layout.py
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import uid, esc, close_paren, PROJ, MOTOR_PCB, DRIVER_SCH, kicad_cli

DRIVER_PCB = DRIVER_SCH.replace(".kicad_sch", ".kicad_pcb")
MERGED_SCH = os.path.join(PROJ, "Maslow Mini Merged Board.kicad_sch")
DEST = os.path.join(PROJ, "Maslow Mini Merged Board.kicad_pcb")
KICAD_FP = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"

REF_OFFSET = 100
MOTOR_SHEET = uid("sheetsym", "motor")
DRIVER_SHEET = uid("sheetsym", "driver")

# ---- how the two sections sit relative to each other -----------------------
# motor section keeps its own coordinates; the driver section is translated so
# its outline butts up against the motor outline with a 5 mm gap, tops aligned.
MOTOR_SHIFT = (0.0, 0.0)
DRIVER_SHIFT = (71.5, -4.5)
BOARD = (114.0, 44.0, 257.0, 159.0)          # Edge.Cuts placeholder rectangle
                                             # (2 mm clear of both original outlines)
STAGE_X, STAGE_Y, STAGE_W = 268.0, 46.0, 330.0

# ---- what stays where it was ----------------------------------------------
FIXED_MOTOR = {
    "U2", "U3", "U5", "U6",                              # DRV8876 belt drivers
    "U1",                                                # XT60 power inlet
    "CN1", "CN3", "CN4", "CN10",                         # motor outputs
    "CN5", "CN9", "CN11", "CN12",                        # axis encoder ports
    "USB2",                                              # USB-C
}
FIXED_DRIVER = {
    "U14", "U15",                                        # MP6541A 3-phase drivers
    "CN3", "CN4",                                        # motor phase outputs
    "CN5",                                               # vacuum control
    "USB1",                                              # USB-C
}

# parts whose merged footprint differs from the one on their source PCB
REBUILD = {"D102": "Diode_SMD:D_SMA", "D103": "Diode_SMD:D_SMA"}


# ------------------------------------------------------------------ helpers
def blocks(text, keyword):
    for m in re.finditer(r'^\t\(%s[\s"]' % keyword, text, re.M):
        s = m.start() + 1
        yield s, close_paren(text, s)


def source_footprints(path):
    """reference -> raw footprint block, as placed on that board."""
    txt = open(path, encoding="utf-8").read()
    out = {}
    for s, e in blocks(txt, "footprint"):
        blk = txt[s:e]
        m = re.search(r'\(property "Reference" "([^"]*)"', blk)
        if m:
            out[m.group(1)] = blk
    return out, txt


def edge_lines(txt, dx, dy, layer):
    """Edge.Cuts graphics from a source board, moved and re-layered."""
    out = []
    for kind in ("gr_line", "gr_arc", "gr_circle", "gr_rect", "gr_poly", "gr_curve"):
        for s, e in blocks(txt, kind):
            blk = txt[s:e]
            if '"Edge.Cuts"' not in blk:
                continue
            blk = re.sub(r'\(layer "Edge\.Cuts"\)', f'(layer "{layer}")', blk)
            blk = re.sub(r"\((start|end|center|mid|xy) ([-\d.]+) ([-\d.]+)\)",
                         lambda m: f"({m.group(1)} {float(m.group(2)) + dx:.4f} "
                                   f"{float(m.group(3)) + dy:.4f})", blk)
            blk = re.sub(r'\(uuid "[^"]*"\)',
                         lambda m, c=[0]: f'(uuid "{uid("edge", layer, dx, dy, len(out), c[0])}")',
                         blk)
            out.append("\t" + blk)
    return out


def fp_bbox(blk):
    """(w, h) of a placed footprint, from its courtyard if it has one."""
    pts = []
    for s, e in [(m.start(), close_paren(blk, m.start()))
                 for m in re.finditer(r"\((fp_line|fp_rect|fp_poly|fp_circle|pad) ", blk)]:
        sub = blk[s:e]
        crt = "CrtYd" in sub
        for a, b in re.findall(r"\((?:start|end|center|mid|xy|at) ([-\d.]+) ([-\d.]+)", sub):
            pts.append((float(a), float(b), crt))
    crt = [(x, y) for x, y, c in pts if c]
    use = crt or [(x, y) for x, y, _ in pts]
    if not use:
        return 6.0, 6.0
    xs = [p[0] for p in use]
    ys = [p[1] for p in use]
    return max(xs) - min(xs) + 2.0, max(ys) - min(ys) + 2.0


def load_kicad_mod(lib_id):
    lib, name = lib_id.split(":", 1)
    for root in (os.path.join(PROJ, f"{lib}.pretty"), os.path.join(KICAD_FP, f"{lib}.pretty")):
        p = os.path.join(root, name.replace("/", "_") + ".kicad_mod")
        if os.path.exists(p):
            return open(p, encoding="utf-8").read()
    raise FileNotFoundError(lib_id)


# ------------------------------------------------------------------- inputs
sch_nets = {}
import subprocess, tempfile
with tempfile.TemporaryDirectory() as tmp:
    xml = os.path.join(tmp, "n.xml")
    subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadxml",
                    "-o", xml, MERGED_SCH], check=True, capture_output=True, text=True)
    root = ET.parse(xml).getroot()
    comps = {}
    for c in root.find("components").findall("comp"):
        comps[c.get("ref")] = {
            "value": (c.find("value").text or ""),
            "footprint": (c.find("footprint").text or ""),
        }
    for net in root.find("nets").findall("net"):
        for n in net.findall("node"):
            sch_nets[(n.get("ref"), n.get("pin"))] = net.get("name")

motor_fps, motor_txt = source_footprints(MOTOR_PCB)
driver_fps, driver_txt = source_footprints(DRIVER_PCB)

# symbol UUIDs, for the schematic <-> board link
driver_sch = open(DRIVER_SCH.replace(str(DRIVER_SCH), os.path.join(PROJ, "driver_section.kicad_sch")),
                  encoding="utf-8").read()
driver_uuid = {}
for s, e in blocks(driver_sch, "symbol"):
    blk = driver_sch[s:e]
    ref = re.search(r'\(property "Reference" "([^"]*)"', blk)
    u = re.search(r'\(uuid "([^"]*)"\)', blk)
    if ref and u:
        driver_uuid[ref.group(1)] = u.group(1)


def section(ref):
    m = re.match(r"([A-Za-z_]+)(\d+)$", ref)
    n = int(m.group(2))
    if n >= REF_OFFSET:
        return "M", f"{m.group(1)}{n - REF_OFFSET}"
    return "D", ref


# --------------------------------------------------------------- build parts
placed, staged = [], []
for ref in sorted(comps, key=lambda r: (re.match(r"[A-Za-z_]+", r).group(0),
                                        int(re.search(r"\d+", r).group(0)))):
    sec, src_ref = section(ref)
    fp_id = comps[ref]["footprint"]

    if ref in REBUILD:
        blk = load_kicad_mod(REBUILD[ref]).strip()
        blk = re.sub(r"^\(footprint \"[^\"]+\"", f'(footprint "{esc(fp_id)}"', blk, count=1)
        blk = re.sub(r"\n\s*\((version|generator|generator_version) [^)]*\)", "", blk)
        blk = re.sub(r'\(uuid "[^"]*"\)',
                     lambda m, c=[0]: (c.__setitem__(0, c[0] + 1) or
                                       f'(uuid "{uid("fpchild", ref, c[0])}")'), blk)
        blk = re.sub(r"^", "\t", blk, flags=re.M).lstrip("\t")
        # a library footprint carries no placement; give it one so set_at() and
        # the reference rewrite below have something to bite on
        blk = re.sub(r'^(\t\t\(layer "[^"]+"\)\n)', r"\1\t\t(at 0 0)\n", blk,
                     count=1, flags=re.M)
        ref_in_block = "REF**"      # a library copy carries the placeholder
        src_at_rot = 0.0
        src_layer = "F.Cu"
    else:
        src = (motor_fps if sec == "M" else driver_fps)[src_ref]
        blk = src
        blk = re.sub(r'^\(footprint "[^"]+"', f'(footprint "{esc(fp_id)}"', blk, count=1)
        m = re.search(r"^\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk, re.M)
        ref_in_block = src_ref
        src_at_rot = float(m.group(3) or 0)
        src_layer = re.search(r'^\t\t\(layer "([^"]+)"\)', blk, re.M).group(1)

    # reference designator
    blk = blk.replace(f'(property "Reference" "{ref_in_block}"',
                      f'(property "Reference" "{ref}"', 1)
    blk = re.sub(r'\(property "Value" "[^"]*"',
                 f'(property "Value" "{esc(comps[ref]["value"])}"', blk, count=1)

    # schematic link + stable identity
    sym = uid("sym", src_ref) if sec == "M" else driver_uuid[src_ref]
    sheet = MOTOR_SHEET if sec == "M" else DRIVER_SHEET
    path_node = f'\t\t(path "/{sheet}/{sym}")'
    if re.search(r"^\t\t\(path \"", blk, re.M):
        blk = re.sub(r"^\t\t\(path \"[^\"]*\"\)", path_node, blk, count=1, flags=re.M)
    else:
        blk = re.sub(r"^(\t\t\(at [^\n]*\n)", r"\1" + path_node + "\n", blk, count=1, flags=re.M)
    blk = re.sub(r"^\t\t\(uuid \"[^\"]*\"\)", f'\t\t(uuid "{uid("fp", ref)}")', blk,
                 count=1, flags=re.M)

    # pad nets, straight from the merged schematic
    def fix_pad(m):
        s = m.start()
        pad = blk_ref[0][s:close_paren(blk_ref[0], s)]
        name = re.match(r'\(pad "([^"]*)"', pad).group(1)
        net = sch_nets.get((ref, name))
        if net:
            repl = f'(net "{esc(net)}")'
            if re.search(r'\(net (?:\d+ )?"[^"]*"\)', pad):
                pad = re.sub(r'\(net (?:\d+ )?"[^"]*"\)', repl, pad, count=1)
            else:
                pad = re.sub(r'(\(layers[^\n]*\)\n)', r"\1\t\t\t" + repl + "\n", pad, count=1)
        else:
            pad = re.sub(r'\n\s*\(net (?:\d+ )?"[^"]*"\)', "", pad)
        return pad

    blk_ref = [blk]
    out, pos = [], 0
    for m in re.finditer(r'\(pad "', blk):
        s = m.start()
        e = close_paren(blk, s)
        out.append(blk[pos:s])
        out.append(fix_pad(m))
        pos = e
    out.append(blk[pos:])
    blk = "".join(out)

    fixed = (src_ref in FIXED_MOTOR) if sec == "M" else (src_ref in FIXED_DRIVER)
    (placed if fixed else staged).append((ref, sec, src_ref, blk, src_at_rot, src_layer))


def set_at(blk, x, y, rot):
    return re.sub(r"^\t\t\(at [-\d.]+ [-\d.]+(?: [-\d.]+)?\)",
                  f"\t\t(at {x:.4f} {y:.4f}{'' if rot == 0 else f' {rot:g}'})",
                  blk, count=1, flags=re.M)


body = []

# --- parts that keep their original position -------------------------------
for ref, sec, src_ref, blk, rot, layer in placed:
    dx, dy = MOTOR_SHIFT if sec == "M" else DRIVER_SHIFT
    m = re.search(r"^\t\t\(at ([-\d.]+) ([-\d.]+)", blk, re.M)
    body.append("\t" + set_at(blk, float(m.group(1)) + dx, float(m.group(2)) + dy, rot))

# --- everything else, packed into a staging grid ---------------------------
GAP = 3.0
sizes = {t[0]: fp_bbox(t[3]) for t in staged}


def pack(items):
    rows, cur, cur_w = [], [], 0.0
    for item in items:
        w = sizes[item[0]][0] + GAP
        if cur and cur_w + w > STAGE_W:
            rows.append(cur)
            cur, cur_w = [], 0.0
        cur.append(item)
        cur_w += w
    if cur:
        rows.append(cur)
    return rows


def by_ref(t):
    return (re.match(r"[A-Za-z_]+", t[0]).group(0), int(re.search(r"\d+", t[0]).group(0)))


# the two sections are packed separately so the staging area does not mix them
groups = [("MOTOR CONTROL SECTION", sorted((s for s in staged if s[1] == "M"), key=by_ref)),
          ("DRIVER SECTION", sorted((s for s in staged if s[1] == "D"), key=by_ref))]

stage_labels = []
y = STAGE_Y + 8.0
rows = []
for title, items in groups:
    stage_labels.append((title, y - 3.0))
    grp = pack(items)
    rows += grp
    for row in grp:
        h = max(sizes[i[0]][1] for i in row)
        x = STAGE_X
        for item in row:
            w, ih = sizes[item[0]]
            body.append("\t" + set_at(item[3], x + w / 2, y + h / 2, item[4]))
            x += w + GAP
        y += h + GAP
    y += 9.0

STAGE_BOTTOM = y


def gr_text(s, x, y, size=3.0, layer="Cmts.User"):
    return (f'\t(gr_text "{esc(s)}"\n\t\t(at {x} {y})\n\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{uid("grtext", s)}")\n'
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n"
            f"\t\t\t\t(thickness {size / 6:.2f})\n\t\t\t\t(bold yes)\n\t\t\t)\n"
            f"\t\t\t(justify left bottom)\n\t\t)\n\t)")


def gr_line(x1, y1, x2, y2, layer, tag, width=0.15):
    return (f"\t(gr_line\n\t\t(start {x1:.3f} {y1:.3f})\n\t\t(end {x2:.3f} {y2:.3f})\n"
            f"\t\t(stroke\n\t\t\t(width {width})\n\t\t\t(type solid)\n\t\t)\n"
            f'\t\t(layer "{layer}")\n\t\t(uuid "{uid("grline", tag)}")\n\t)')


# --- board outline ---------------------------------------------------------
x1, y1, x2, y2 = BOARD
for i, (a, b, c, d) in enumerate(((x1, y1, x2, y1), (x2, y1, x2, y2),
                                  (x2, y2, x1, y2), (x1, y2, x1, y1))):
    body.append(gr_line(a, b, c, d, "Edge.Cuts", f"outline{i}", 0.1))

# --- the two original outlines, for reference ------------------------------
body += edge_lines(motor_txt, *MOTOR_SHIFT, "Dwgs.User")
body += edge_lines(driver_txt, *DRIVER_SHIFT, "Dwgs.User")

body.append(gr_text("MOTOR CONTROL SECTION", x1 + 4, y1 - 8, 3.0))
body.append(gr_text("DRIVER SECTION", x1 + 80, y1 - 8, 3.0))
body.append(gr_text("Edge.Cuts here is a placeholder rectangle.  Both original board "
                    "outlines, cutouts included, are on Dwgs.User.",
                    x1, y2 + 5, 2.2))
body.append(gr_text("STAGING - place these by hand.  Original rotation and board side "
                    "are preserved.", STAGE_X, STAGE_Y, 3.0))
for title, ly in stage_labels:
    body.append(gr_text(f"{title} - parts to place", STAGE_X, ly, 2.2))
body.append(gr_text("Driver section was translated by "
                    f"({DRIVER_SHIFT[0]:+g}, {DRIVER_SHIFT[1]:+g}) mm as a rigid body; "
                    "the motor section is at its original coordinates.",
                    STAGE_X, STAGE_BOTTOM + 6, 2.0))

# --- assemble --------------------------------------------------------------
src = open(DRIVER_PCB, encoding="utf-8").read()
layers = src[src.index("\t(layers"):close_paren(src, src.index("\t(layers") + 1)]
setup = src[src.index("\t(setup"):close_paren(src, src.index("\t(setup") + 1)]

out = ["(kicad_pcb",
       "\t(version 20260206)",
       '\t(generator "maslow-merge")',
       '\t(generator_version "10.0")',
       "\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)",
       '\t(paper "A1")',
       layers,
       setup]
out += body
out.append(")")
open(DEST, "w", encoding="utf-8").write("\n".join(out) + "\n")

print(f"wrote {DEST}")
print(f"  {len(placed)} parts kept at their original positions:")
print(f"     motor : {sorted(r for r, s, *_ in placed if s == 'M')}")
print(f"     driver: {sorted(r for r, s, *_ in placed if s == 'D')}")
print(f"  {len(staged)} parts staged off-board in {len(rows)} rows "
      f"(x {STAGE_X:.0f}..{STAGE_X + STAGE_W:.0f}, y {STAGE_Y:.0f}..{STAGE_BOTTOM:.0f})")
print(f"  board outline {x2 - x1:g} x {y2 - y1:g} mm")
