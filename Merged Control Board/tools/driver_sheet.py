"""Turn the standalone Driver Board schematic into the Driver Section sub-sheet
of the merged board.

Edits, and nothing else:

 1. delete H1 (2x5 board-to-board header) - the merge makes it pointless
 2. delete the MP2459 3.3 V buck chain (U2, L3, D2, D6, C80, C81, R61, R62,
    R63).  The motor section's LM2596 is a 3 A part and carries both sections;
    the MP2459 is 0.5 A and was already marginal feeding one ESP32-S3 on its
    own.  D7 stays and now feeds the shared buck input, so this USB port can
    still power the board.
 3. delete C30, the 100 nF EN cap.  The motor side's 1 uF (C134) survives as
    the single EN RC together with R28 and SW2, which now reset both MCUs.
    1 uF is the value Espressif's design guide asks for.
 4. the surviving BOARDCOM1/BOARDCOM2 labels at the ESP32 become hierarchical
    pins.  The crossover from the old H1 mating is preserved:
        driver BOARDCOM1 (IO39) -> BOARDCOM_B
        driver BOARDCOM2 (IO38) -> BOARDCOM_A
 5. 3V3 -> +3V3, which merges with the motor section's rail (one regulator
    now), and BOOT -> BOOT_DRV so each MCU keeps its own boot button.
    VIN, GND and RST also merge with the motor section.
 6. re-target symbol instance paths at the new project / sheet.

Everything the deletions leave behind - labels that sat on a deleted pin,
wires with nothing at one end, junctions in a wholly removed branch - is found
by walking the sheet's connectivity graph rather than by hard-coded position,
so this stays correct if the source schematic moves.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import uid, esc, close_paren, PROJ, DRIVER_SCH

SRC = DRIVER_SCH
DEST = os.path.join(PROJ, "driver_section.kicad_sch")

OLD_ROOT_UUID = "d47c1592-85aa-4594-b513-aeb672840812"
OLD_PROJECT = "ProPrj_Driver Board to share_2026-08-01"
PROJECT = "Maslow Mini Merged Board"
SHEET_UUID = uid("sheetfile", "driver_section")
ROOT_UUID = uid("sheetfile", "root")
SHEET_INST = uid("sheetsym", "driver")

DELETE_REFS = {
    "H1",                                                  # 2x5 board-to-board header
    "U2", "L3", "D2", "D6", "C80", "C81", "R61", "R62", "R63",   # MP2459 buck chain
    "C30",                                                 # EN cap, superseded by C134 (1 uF)
}
# D7 is deliberately kept: it now ORs this port's VBUS into the shared buck input.

RAIL_RENAMES = [("3V3", "+3V3"), ("BOOT", "BOOT_DRV")]
HIER = {"BOARDCOM1": ("BOARDCOM_B", "bidirectional"),
        "BOARDCOM2": ("BOARDCOM_A", "bidirectional")}

TOL = 0.02          # mm; coordinates in this file are quantised to 0.01

txt = open(SRC, encoding="utf-8").read()


# --------------------------------------------------------------- sheet parsing
def top_nodes(text):
    """(start, end, kind) for every node at one tab of indent."""
    for m in re.finditer(r'^\t\(([a-z_]+)[\s")]', text, re.M):
        s = m.start() + 1
        yield s, close_paren(text, s), m.group(1)


NODES = list(top_nodes(txt))


def at_of(block):
    m = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", block)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3) or 0)) if m else None


def wire_pts(block):
    pts = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", block)
    return [(float(a), float(b)) for a, b in pts]


# lib_symbols pin geometry, straight out of this sheet
LIBPINS = {}
_lib_s, _lib_e, _ = next(n for n in NODES if n[2] == "lib_symbols")
_lib = txt[_lib_s:_lib_e]
for m in re.finditer(r'^\t\t\(symbol "([^"]+)"', _lib, re.M):
    s = m.start() + 2
    blk = _lib[s:close_paren(_lib, s)]
    pins = {}
    for pm in re.finditer(r"\(pin\s+\w+\s+\w+\s*\n", blk):
        ps = pm.start()
        pin = blk[ps:close_paren(blk, ps)]
        a = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", pin)
        num = re.search(r'\(number "([^"]*)"', pin)
        if a and num:
            pins[num.group(1)] = (float(a.group(1)), float(a.group(2)), float(a.group(3)))
    if pins:
        LIBPINS[m.group(1)] = pins


def pin_xy(px, py, X, Y, angle, mirror_x, mirror_y):
    """Symbol-local pin -> sheet coordinates.  Verified against this sheet:
    every pin lands on a wire end, label, junction or another pin."""
    u, v = px, -py
    if mirror_x:
        v = -v
    if mirror_y:
        u = -u
    a = int(angle) % 360
    u, v = {0: (u, v), 90: (v, -u), 180: (-u, -v), 270: (-v, u)}[a]
    return round(X + u, 2), round(Y + v, 2)


# ------------------------------------------------ classify symbols, find pins
deleted_spans = []
surviving_pins = set()
deleted_refs_seen = set()

for s, e, kind in NODES:
    if kind != "symbol":
        continue
    blk = txt[s:e]
    ref_m = re.search(r'\(property "Reference" "([^"]*)"', blk)
    if not ref_m:
        continue
    ref = ref_m.group(1)
    if ref in DELETE_REFS:
        deleted_spans.append((s, e))
        deleted_refs_seen.add(ref)
        continue
    lib = re.match(r'\t?\(symbol\s*\n?\s*\(lib_id "([^"]+)"', blk)
    lib = lib.group(1) if lib else None
    if lib not in LIBPINS:
        continue
    X, Y, A = at_of(blk)
    mir = re.search(r"\(mirror ([xy])\)", blk)
    mx = bool(mir and mir.group(1) == "x")
    my = bool(mir and mir.group(1) == "y")
    for num, (px, py, _pa) in LIBPINS[lib].items():
        surviving_pins.add(pin_xy(px, py, X, Y, A, mx, my))

missing = DELETE_REFS - deleted_refs_seen
assert not missing, f"asked to delete parts that are not on the sheet: {sorted(missing)}"


# ------------------------------------------------------- connectivity cleanup
class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def on_segment(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > TOL:
        return False
    return (min(x1, x2) - TOL <= x <= max(x1, x2) + TOL
            and min(y1, y2) - TOL <= y <= max(y1, y2) + TOL)


def key(p):
    return (round(p[0], 2), round(p[1], 2))


# graphical items that carry connectivity
items = []          # (start, end, kind, [points])
for s, e, kind in NODES:
    if (s, e) in deleted_spans:
        continue
    blk = txt[s:e]
    if kind == "wire":
        items.append((s, e, kind, [key(p) for p in wire_pts(blk)]))
    elif kind in ("junction", "no_connect", "global_label", "label", "hierarchical_label"):
        a = at_of(blk)
        items.append((s, e, kind, [key(a[:2])]))

dsu = DSU()
wires = [it for it in items if it[2] == "wire"]
for it in items:
    for p in it[3]:
        dsu.find(p)
    for p in it[3][1:]:
        dsu.union(it[3][0], p)
# a point sitting on a wire's span joins that wire
allpts = {p for it in items for p in it[3]} | surviving_pins
for w in wires:
    a, b = w[3][0], w[3][-1]
    for p in allpts:
        if p not in (a, b) and on_segment(p, a, b):
            dsu.union(p, a)

live = {dsu.find(p) for p in surviving_pins if p in dsu.p}
drop = set()
for s, e, kind, pts in items:
    if not any(dsu.find(p) in live for p in pts):
        drop.add((s, e))          # whole branch is orphaned

# prune wires left with a free end (nothing else terminates there)
def occupancy(dropped):
    occ = {}
    for p in surviving_pins:
        occ[p] = occ.get(p, 0) + 1
    for s, e, kind, pts in items:
        if (s, e) in dropped:
            continue
        for p in pts:
            occ[p] = occ.get(p, 0) + 1
    return occ

changed = True
while changed:
    changed = False
    occ = occupancy(drop)
    remaining_wires = [w for w in wires if (w[0], w[1]) not in drop]
    for w in remaining_wires:
        a, b = w[3][0], w[3][-1]
        for endpoint in (a, b):
            if occ.get(endpoint, 0) > 1:
                continue
            # a free end is still fine if it lands mid-span on another wire
            if any(on_segment(endpoint, o[3][0], o[3][-1])
                   for o in remaining_wires if o is not w):
                continue
            drop.add((w[0], w[1]))
            changed = True
            break

cuts = list(deleted_spans) + sorted(drop)


# ---------------------------------------------- BOARDCOM -> hierarchical pins
rewrites = []
for s, e, kind in NODES:
    if kind != "global_label" or (s, e) in cuts:
        continue
    blk = txt[s:e]
    name = re.match(r'\(global_label "([^"]+)"', blk).group(1)
    if name in HIER:
        new, shape = HIER[name]
        x, y, a = at_of(blk)
        just = "left" if a in (0.0, 90.0) else "right"
        rewrites.append((s, e,
                         f'\t(hierarchical_label "{new}"\n\t\t(shape {shape})\n'
                         f"\t\t(at {x:g} {y:g} {a:g})\n"
                         f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.5748 1.5748)\n\t\t\t)\n"
                         f"\t\t\t(justify {just})\n\t\t)\n"
                         f'\t\t(uuid "{uid("hier", "driver", new)}")\n\t)'))

# ------------------------------------------------- apply cuts, then rewrites
edits = sorted([(s, e, None) for s, e in cuts] + rewrites, key=lambda t: -t[0])
for s, e, repl in edits:
    if repl is None:
        s -= 1                       # take the leading tab with it
        end = e
        while end < len(txt) and txt[end] in " \t":
            end += 1
        if end < len(txt) and txt[end] == "\n":
            end += 1
        txt = txt[:s] + txt[end:]
    else:
        txt = txt[:s - 1] + repl + txt[e:]

# ------------------------------------------------------------ rail renaming
for old, new in RAIL_RENAMES:
    n = txt.count(f'(global_label "{old}"')
    txt = txt.replace(f'(global_label "{old}"', f'(global_label "{new}"')
    print(f"  renamed {n} x global_label {old} -> {new}")

# --------------------------------------- project / sheet path re-targeting
txt = txt.replace(f'(project "{OLD_PROJECT}"', f'(project "{PROJECT}"')
txt = txt.replace(f'(path "/{OLD_ROOT_UUID}"', f'(path "/{ROOT_UUID}/{SHEET_INST}"')
txt = txt.replace(f'\t(uuid "{OLD_ROOT_UUID}")', f'\t(uuid "{SHEET_UUID}")', 1)
txt = re.sub(r'\t\(sheet_instances\n(?:.*\n)*?\t\)\n', "", txt, count=1)

# ------------------------------------------------- tidy up after the deletions
# The source schematic left D6/D7's field text parked at D2's position when
# those diodes were added.  D2 is gone now, so D7's reference and value would
# float alone in the middle of a motor-driver block.  Any kept symbol whose
# VISIBLE field ended up implausibly far from its body gets it moved back;
# on this sheet that is D7 and nothing else.
def reseat_stray_fields(text, limit=100.0):
    moved = []
    for m in list(re.finditer(r"^\t\(symbol[\s\"]", text, re.M))[::-1]:
        s = m.start() + 1
        e = close_paren(text, s)
        blk = text[s:e]
        ref_m = re.search(r'\(property "Reference" "([^"]*)"', blk)
        sat = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", blk)
        if not ref_m or not sat:
            continue
        X, Y = float(sat.group(1)), float(sat.group(2))
        new_blk, shifted = blk, False
        for pm in list(re.finditer(r'\(property "(Reference|Value)" "([^"]*)"\n', blk))[::-1]:
            ps = pm.start()
            pe = close_paren(blk, ps)
            pblk = blk[ps:pe]
            if "(hide yes)" in pblk:
                continue
            a = re.search(r"\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)", pblk)
            if not a:
                continue
            if abs(float(a.group(1)) - X) + abs(float(a.group(2)) - Y) < limit:
                continue
            dy = -1.27 if pm.group(1) == "Reference" else 1.27
            fixed = pblk.replace(a.group(0), f"(at {X - 2.54:g} {Y + dy:g} 0)", 1)
            if "(justify" not in fixed:
                fixed = fixed.replace("(effects", "(effects\n\t\t\t\t(justify right)", 1)
            new_blk = new_blk[:ps] + fixed + new_blk[pe:]
            shifted = True
        if shifted:
            moved.append(ref_m.group(1))
            text = text[:s] + new_blk + text[e:]
    return text, moved


txt, reseated = reseat_stray_fields(txt)

# The "3.3V Regulator" block now holds only decoupling, and its notes describe a
# PMOS/LDO arrangement this schematic has never actually contained.
TEXT_EDITS = {
    "3.3V Regulator": "3.3 V DECOUPLING",
    "200ma LDO / Power OR-ing with PMOS":
        "Regulator is now U116 (LM2596-3.3) on the motor section",
    "-PMOS gate VBUS pull-up": None,          # matched by prefix
}
retitled, dropped_notes = [], 0
for s, e, kind in list(top_nodes(txt))[::-1]:
    if kind != "text":
        continue
    body = txt[s:e]
    lit = re.match(r'\(text "((?:[^"\\]|\\.)*)"', body)
    if not lit:
        continue
    val = lit.group(1)
    for old, repl in TEXT_EDITS.items():
        if not val.startswith(old):
            continue
        if repl is None:
            end = e
            while end < len(txt) and txt[end] in " \t":
                end += 1
            if end < len(txt) and txt[end] == "\n":
                end += 1
            txt = txt[:s - 1] + txt[end:]
            dropped_notes += 1
        else:
            txt = txt[:s] + body.replace(f'"{val}"', f'"{esc(repl)}"', 1) + txt[e:]
            retitled.append(repl)
        break

# ---------------------------------------------------------------- sheet note
NOTE_LINES = [
    ("DRIVER SECTION", 4.0, True),
    ('Imported from "ProPrj_Driver Board to share_2026-08-01", except:', 1.8, False),
    ("  - H1 (2x5 board-to-board header) deleted; BOARDCOM1/2 at U12 are now hierarchical "
     "pins BOARDCOM_B / BOARDCOM_A", 1.8, False),
    ("  - MP2459 buck chain (U2, L3, D2, D6, C80, C81, R61-R63) deleted - the motor "
     "section's 3 A LM2596 now feeds both sections", 1.8, False),
    ("  - D7 kept, and now ORs this port's VBUS into the shared buck input VIN_BUCK", 1.8, False),
    ("  - C30 deleted; R28 + SW2 + C134 (1 uF, motor section) are now the EN RC and reset "
     "button for BOTH MCUs", 1.8, False),
    ("  - 3V3 -> +3V3 and BOOT -> BOOT_DRV.  +3V3, VIN, GND and RST are shared with the "
     "motor section; BOOT is not", 1.8, False),
]
note = ""
y = 17.0
for line, size, bold in NOTE_LINES:
    note += (f'\t(text "{esc(line)}"\n\t\t(at 556 {y} 0)\n'
             "\t\t(effects\n\t\t\t(font\n"
             f"\t\t\t\t(size {size} {size})" + ("\n\t\t\t\t(bold yes)" if bold else "") + "\n\t\t\t)\n"
             "\t\t\t(justify left bottom)\n\t\t)\n"
             f'\t\t(uuid "{uid("txt", "driver-note", line)}")\n\t)\n')
    y += size * 1.55 + 1.4
# anchor on the file-final node: a bare "\t(embedded_fonts" also occurs inside
# every lib_symbols entry at deeper indent
tail = re.search(r"\n\t\(embedded_fonts no\)\n\)\s*$", txt)
txt = txt[:tail.start()] + "\n" + note + "\t(embedded_fonts no)\n)\n"

open(DEST, "w", encoding="utf-8").write(txt)
print("wrote", DEST)
print(f"  deleted symbols: {sorted(DELETE_REFS)}")
print(f"  removed {len(drop)} orphaned wires / labels / junctions left behind by them")
print(f"  re-seated stray field text on: {reseated or 'nothing'}")
print(f"  retitled {len(retitled)} block captions, dropped {dropped_notes} stale notes")
print(f"  hierarchical pins: {[r[2].split('\"')[1] for r in rewrites]}")
