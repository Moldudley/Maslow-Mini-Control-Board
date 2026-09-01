"""Generate the Motor Control Section hierarchical sheet of the merged board.

The source of truth is the netlist of
  Motor Controller Board/Four Motor Control Board M5_*.kicad_pcb
which has no schematic of its own, so this sheet is synthesised from its PCB
connectivity.  Every pin -> net relationship is taken verbatim from that board,
with these deliberate changes for the merge:

  * H1 (the 2x5 board-to-board header) is deleted; BOARDCOM1/BOARDCOM2 become
    hierarchical pins BOARDCOM_A / BOARDCOM_B.
  * VCC (the XT60 input rail) is renamed VIN so it merges with the driver
    section's VIN, which used to arrive over H1 pins 6/8/10.
  * 3V3 -> +3V3_MC and BOOT -> BOOT_MC so they stay distinct from the driver
    section's rails of the same original name.
  * the LM2596's TO-263 tab (pad 6) was left floating on the source PCB; it is
    internally GND, and is bonded to GND here.

Reference designators are the originals + 100 so they cannot collide with the
driver section (whose highest number is 82).

Connectivity is expressed with a label on every pin rather than drawn wires -
the same style the driver board's own EasyEDA-imported schematic uses.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (uid, esc, load_lib_pins, load_lib_body, load_pcb_footprints,
                    close_paren, PROJ, MOTOR_PCB)

PROJECT = "Maslow Mini Merged Board"
fps = load_pcb_footprints(MOTOR_PCB)

# --------------------------------------------------------------- net renaming
RENAME = {
    'VCC': 'VIN',            # merges with the driver section (was H1 pins 6/8/10)
    '3V3': '+3V3',           # one regulator now, so one 3.3 V rail for both sections
    'U16_1': 'VIN_BUCK',     # shared buck input; the driver's D7 ORs into it too
    'MCU_RST': 'RST',        # merges with the driver section's reset net
    'BOOT': 'BOOT_MC',       # each MCU keeps its own boot button
    'BOARDCOM1': 'BOARDCOM_A', 'BOARDCOM2': 'BOARDCOM_B',
    'USB2_A5': 'CC1_MC', 'USB2_B5': 'CC2_MC',
    'L2_1': 'SW_BUCK',
    'LED2_1': 'AXISLED_A', 'LED3_2': 'WIFILED_A',
    'USBD+': 'USB_D+_MC', 'USBD-': 'USB_D-_MC', 'USB5V': 'VBUS_MC',
}
AXIS = {'U2': 'TR', 'U3': 'TL', 'U5': 'BL', 'U6': 'BR'}
for u, ax in AXIS.items():
    RENAME[f'{u}_6'] = f'IPROPI_{ax}'
    RENAME[f'{u}_12'] = f'VCP_{ax}'
    RENAME[f'{u}_13'] = f'CPH_{ax}'
    RENAME[f'{u}_14'] = f'CPL_{ax}'
HIER = {'BOARDCOM_A', 'BOARDCOM_B'}
def net(n):
    return RENAME.get(n, n)

# ------------------------------------------------------------ symbol mapping
FP_TO_SYM = {
    'R0402': 'MaslowMerged:R', 'R0603': 'MaslowMerged:R', 'R0805': 'MaslowMerged:R',
    'C0603': 'MaslowMerged:C', 'C0805': 'MaslowMerged:C',
    'CAP-SMD_BD6.3-L6.6-W6.6-LS7.3-FD': 'MaslowMerged:C_Polarized',
    'CAP-SMD_BD6.3-L6.6-W6.6-LS7.6-RD': 'MaslowMerged:C_Polarized',
    'CAP-SMD_BD10.0-L10.3-W10.3-LS10.9-FD': 'MaslowMerged:C_Polarized',
    'IND-SMD_L6.0-W6.0': 'MaslowMerged:L',
    'LED0603-R-RD': 'MaslowMerged:LED_A1K2', 'LED0603_RED': 'MaslowMerged:LED_A1K2',
    'LED0603-RD': 'MaslowMerged:LED_K1A2',
    'SMA_L4.2-W2.6-LS5.3-RD': 'MaslowMerged:D_Schottky_K1A2',
    'SMA_L4.3-W2.7-LS5.1-RD': 'MaslowMerged:D_Schottky_K1A2',
    'HTSSOP-16_L5.0-W4.4-P0.65-LS6.4-BL-EP': 'MaslowMerged:DRV8876PWPR',
    'SOP-16_L5.0-W4.4-P0.65-LS6.4-BL': 'MaslowMerged:TCA9546A',
    'LGA-8_L6.0-W8.0-P1.27-BL': 'MaslowMerged:ZDSD01GLGEAG',
    'TO-263-5_L10.2-W8.6-P1.70-LS14.4-TL': 'MaslowMerged:LM2596R-3.3',
    'CONN-TH_XT60PB-M': 'MaslowMerged:XT60PB-M',
    'CONN-TH_B2B-PH-K-S': 'MaslowMerged:B2B-PH-K-S',
    'CONN-TH_B4B-PH-K-S': 'MaslowMerged:B4B-PH-K-S',
    'USB-C-SMD_KH-TYPE-C-16P': 'MaslowMerged:KH-TYPE-C-16P',
    'SW-SMD_4P-L6.2-W6.4-P4.00-LS7.2': 'MaslowMerged:SW_Push_4P',
    'ESP32-S3-WROOM-1': 'ProPrj_Dri-easyedapro:ESP32-S3-WROOM-1(N8R2)',
}
DELETED = {
    'H1',            # 2x5 board-to-board header - the point of the merge
    'R28',           # EN pull-up; the driver section's R28 serves both MCUs now
    'D1', 'R15',     # power-on LED; the driver section's LED2 + R17 is kept (3.6 mA vs 11 mA)
}
NC_PINS = {('SW1', '1'), ('SW1', '3'), ('USB2', 'A8'), ('USB2', 'B8')}

# D2/D3 were SS14 (40 V / 1 A); the driver section's surviving D7 is SS36 (60 V / 3 A)
# doing the identical job.  One BOM line, and more margin on a 24 V rail that also
# carries six motor stages.
OVERRIDE = {
    'D2': {'symbol': 'ProPrj_Dri-easyedapro:SS36', 'value': 'SS36',
           'footprint': 'Diode_SMD:D_SMA'},
    'D3': {'symbol': 'ProPrj_Dri-easyedapro:SS36', 'value': 'SS36',
           'footprint': 'Diode_SMD:D_SMA'},
}

def sym_of(ref):
    o = OVERRIDE.get(ref)
    return o['symbol'] if o and 'symbol' in o else FP_TO_SYM[fps[ref]['footprint']]

def val_of(ref):
    o = OVERRIDE.get(ref)
    return o['value'] if o and 'value' in o else fps[ref]['value']

def fpname_of(ref):
    o = OVERRIDE.get(ref)
    if o and 'footprint' in o:
        return o['footprint']
    lib_id = sym_of(ref)
    if lib_id.startswith('ProPrj_Dri-easyedapro'):
        return 'ProPrj_Dri-easyedapro:WIRELM-SMD_ESP32-S3-WROOM-1'
    return f"MaslowMerged:{fps[ref]['footprint']}"

libpins, libbody = {}, {}
for lib, path in (('MaslowMerged', 'MaslowMerged.kicad_sym'),
                  ('ProPrj_Dri-easyedapro', 'ProPrj_Dri-easyedapro.kicad_sym')):
    full = os.path.join(PROJ, path)
    for k, v in load_lib_pins(full).items():
        libpins[f'{lib}:{k}'] = v
    for k, v in load_lib_body(full).items():
        libbody[f'{lib}:{k}'] = v

def newref(ref):
    m = re.match(r'([A-Za-z_]+)(\d+)$', ref)
    return f'{m.group(1)}{int(m.group(2)) + 100}'

# ------------------------------------------------------------------- blocks
BLOCKS = [
    ("24 V INPUT  /  3.3 V BUCK REGULATOR",
     ['U1', 'C40', 'D2', 'D3', 'U16', 'L2', 'D5', 'C29', 'C31', 'C30']),
    ("USB-C PROGRAMMING PORT  (motor MCU)", ['USB2', 'R9', 'R14', 'C32', 'C33']),
    ("SD NAND", ['U9']),
    ("ESP32-S3-WROOM-1  -  MOTOR CONTROL MCU",
     ['U10', 'C34', 'SW1', 'R4', 'R30', 'R32', 'R7',
      'LED2', 'R3', 'LED3', 'R2']),
    ("TCA9546A I2C MUX  /  AXIS ENCODER PORTS",
     ['U7', 'R17', 'R8', 'CN9', 'R25', 'R6', 'CN11', 'R26', 'R27',
      'CN5', 'R20', 'R21', 'CN12', 'R18', 'R19']),
    ("BELT AXIS DRIVER  -  TOP RIGHT",
     ['U2', 'CN3', 'C7', 'C11', 'C9', 'C8', 'R12', 'R10', 'C14']),
    ("BELT AXIS DRIVER  -  TOP LEFT",
     ['U3', 'CN4', 'C13', 'C15', 'C12', 'C10', 'R13', 'R11', 'C17']),
    ("BELT AXIS DRIVER  -  BOTTOM LEFT",
     ['U5', 'CN10', 'C16', 'C22', 'C20', 'C18', 'R24', 'R22', 'C26']),
    ("BELT AXIS DRIVER  -  BOTTOM RIGHT",
     ['U6', 'CN1', 'C24', 'C23', 'C21', 'C19', 'R1', 'R23', 'C27']),
]
for _, members in BLOCKS:                       # drop placeholders
    members[:] = [m for m in members if m in fps]
assert sorted(m for _, ms in BLOCKS for m in ms) == sorted(set(fps) - DELETED), \
    set(fps) - DELETED - {m for _, ms in BLOCKS for m in ms}

# how the blocks sit on the page: rows of (block index, allotted width)
ROWS = [[(0, 560), (1, 300), (2, 200)],
        [(3, 560), (4, 500)],
        [(5, 530), (6, 530)],
        [(7, 530), (8, 530)]]

# --------------------------------------------------------- extent estimation
GRID = 1.27
CH = 1.15          # mm of advance per character at 1.5748 mm text height
PAD = 5.0          # label arrow + breathing room

def snap(v):
    return round(v / GRID) * GRID

def pin_labels(ref):
    """[(pin_number, sx, sy, label_angle, text or None)] in symbol-relative
    schematic coordinates (x right, y down)."""
    f = fps[ref]
    out = []
    for num, (px, py, pangle) in libpins[sym_of(ref)].items():
        sx, sy = px, -py
        lang = {0: 180, 180: 0, 90: 270, 270: 90}[int(pangle)]
        if (ref, num) in NC_PINS:
            text = None
        else:
            n = f['pad_nets'].get(num, {}).get('net')
            if n is None:
                text = 'GND' if (ref == 'U16' and num == '6') else None
            else:
                text = net(n)
        out.append((num, sx, sy, lang, text))
    return out

def extent(ref):
    """(left, right, top, bottom) offsets from the symbol origin, including the
    space each pin's label and the reference/value text will occupy."""
    xs, ys = [], []
    for num, sx, sy, lang, text in pin_labels(ref):
        L = (len(text) * CH + PAD) if text else 3.0
        xs += [sx]; ys += [sy]
        if lang == 180: xs.append(sx - L)      # label reads leftwards
        elif lang == 0: xs.append(sx + L)      # rightwards
        elif lang == 90: ys.append(sy - L)     # upwards
        else: ys.append(sy + L)                # lang 270: downwards
    body = libbody.get(sym_of(ref))
    if body:                       # the drawn body can reach past the outermost pin
        bx0, bx1, by0, by1 = body
        xs += [bx0, bx1]; ys += [-by1, -by0]
    l, rt = min(xs) - 1.5, max(xs) + 1.5
    tp, bt = min(ys) - 1.5, max(ys) + 1.5
    # the reference and value are drawn left-justified just above the part
    tw = max(len(newref(ref)) * 1.20, len(str(val_of(ref))) * 1.00)
    return l, max(rt, l + 1 + tw), tp, bt

EXT = {r: extent(r) for r in fps if r not in DELETED}
TITLE_H = 7.5        # room above each component for its reference + value
GAP_X, GAP_Y = 7.0, 8.0

def pack(members, max_w):
    """Greedy row packing.  Returns (placements relative to block origin, w, h)."""
    place, rows_ = {}, []
    cur, cur_w = [], 0.0
    for r in members:
        l, rt, t, b = EXT[r]
        w = rt - l + GAP_X
        if cur and cur_w + w > max_w:
            rows_.append((cur, cur_w)); cur, cur_w = [], 0.0
        cur.append(r); cur_w += w
    if cur:
        rows_.append((cur, cur_w))
    y = 0.0; width = 0.0
    for row, _ in rows_:
        h = max(EXT[r][3] - EXT[r][2] for r in row) + TITLE_H
        x = 0.0
        for r in row:
            l, rt, t, b = EXT[r]
            place[r] = (snap(x - l), snap(y + TITLE_H - t))
            x += (rt - l) + GAP_X
            width = max(width, x)
        y += h + GAP_Y
    return place, width, y

MARGIN_X, MARGIN_Y = 18.0, 38.0
BLOCK_PAD = 5.0
P, FRAMES = {}, []
cy = MARGIN_Y
for row in ROWS:
    cx = MARGIN_X
    row_h = 0.0
    for bi, alloc in row:
        title, members = BLOCKS[bi]
        rel, w, h = pack(members, alloc)
        for r, (rx, ry) in rel.items():
            P[r] = (snap(cx + BLOCK_PAD + rx), snap(cy + BLOCK_PAD + ry))
        FRAMES.append((title, cx, cy, w + 2 * BLOCK_PAD, h + 2 * BLOCK_PAD - GAP_Y))
        cx += w + 2 * BLOCK_PAD + 14.0
        row_h = max(row_h, h + 2 * BLOCK_PAD - GAP_Y)
    cy += row_h + 22.0

PAGE_W = max(f[1] + f[3] for f in FRAMES) + MARGIN_X
PAGE_H = cy + 34.0

# ------------------------------------------------------------ emit schematic
def label(kind, name, x, y, angle, shape="input", size=1.5748):
    just = "left" if angle in (0, 90) else "right"
    o = [f'\t({kind} "{esc(name)}"', f'\t\t(shape {shape})',
         f'\t\t(at {x:g} {y:g} {angle})',
         f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t)\n\t\t\t(justify {just})\n\t\t)',
         f'\t\t(uuid "{uid("lbl", kind, name, x, y, angle)}")']
    if kind == 'global_label':
        o.append('\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}"\n'
                 f'\t\t\t(at {x:g} {y:g} 0)\n\t\t\t(hide yes)\n\t\t\t(show_name no)\n'
                 '\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n'
                 '\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)')
    o.append('\t)')
    return "\n".join(o)

def text_note(s, x, y, size=2.5, bold=True):
    b = '\n\t\t\t\t(bold yes)' if bold else ''
    return (f'\t(text "{esc(s)}"\n\t\t(at {x:g} {y:g} 0)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size}){b}\n\t\t\t)\n'
            f'\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "{uid("txt", s, x, y)}")\n\t)')

def block_rect(x, y, w, h, name):
    return (f'\t(rectangle\n\t\t(start {x:g} {y:g})\n\t\t(end {x+w:g} {y+h:g})\n'
            f'\t\t(stroke\n\t\t\t(width 0.2)\n\t\t\t(type dash)\n\t\t)\n'
            f'\t\t(fill\n\t\t\t(type none)\n\t\t)\n\t\t(uuid "{uid("rect", name)}")\n\t)')

def no_connect(x, y, tag):
    return f'\t(no_connect\n\t\t(at {x:g} {y:g})\n\t\t(uuid "{uid("nc", tag)}")\n\t)'

def sym_prop(name, value, x, y, rot=0, hide=True, size=1.27, justify=None):
    j = f'\n\t\t\t\t(justify {justify})' if justify else ''
    return (f'\t\t(property "{esc(name)}" "{esc(value)}"\n\t\t\t(at {x:g} {y:g} {rot})'
            + ('\n\t\t\t(hide yes)' if hide else '')
            + '\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
              f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size {size} {size})\n\t\t\t\t){j}\n\t\t\t)\n\t\t)')

SHEET_UUID = uid("sheetfile", "motor_control_section")
ROOT_UUID = uid("sheetfile", "root")
SHEET_INST = uid("sheetsym", "motor")

out = ['(kicad_sch', '\t(version 20260306)', '\t(generator "maslow-merge")',
       '\t(generator_version "10.0")', f'\t(uuid "{SHEET_UUID}")',
       f'\t(paper "User" {PAGE_W:.1f} {PAGE_H:.1f})']

def extract_symbol_block(path, name):
    txt = open(path, encoding='utf-8').read()
    i = txt.find(f'\t(symbol "{name}"')
    if i < 0:
        raise KeyError(name)
    return txt[i:close_paren(txt, i)]

used = sorted({sym_of(r) for r in P} | {'MaslowMerged:PWR_FLAG'})
out.append('\t(lib_symbols')
for lib_id in used:
    lib, name = lib_id.split(':', 1)
    blk = extract_symbol_block(os.path.join(PROJ, f'{lib}.kicad_sym'), name)
    # only the outer symbol takes the "LIB:" prefix - KiCad's schematic loader
    # rejects the file if the nested unit sub-symbols carry it too
    blk = blk.replace(f'\t(symbol "{name}"', f'\t(symbol "{esc(lib_id)}"', 1)
    out.append(re.sub(r'^\t', '\t\t', blk, flags=re.M))
out.append('\t)')

out.append(text_note("MOTOR CONTROL SECTION", MARGIN_X, 14, 4.0))
out.append(text_note("Derived from \"Four Motor Control Board M5\" - that board ships as a PCB with "
                     "no schematic, so this sheet is reconstructed from its netlist.  H1 removed; "
                     "BoardCom is the hierarchical link to the driver section.",
                     MARGIN_X, 21, 1.9, bold=False))
out.append(text_note("VCC -> VIN and 3V3 -> +3V3: this LM2596 now feeds BOTH sections and the "
                     "driver's 0.5 A MP2459 is deleted.  R28/D1/R15 deleted as redundant.  "
                     "Reference designators are the originals + 100.",
                     MARGIN_X, 26, 1.9, bold=False))

for title, x, y, w, h in FRAMES:
    out.append(block_rect(x, y, w, h, title))
    out.append(text_note(title, x + 2, y - 1.8, 2.6))

for ref in sorted(P, key=lambda r: (P[r][1], P[r][0])):
    f = fps[ref]
    lib_id = sym_of(ref)
    x, y = P[ref]
    nref = newref(ref)
    l, rt, t, b = EXT[ref]
    out.append(f'\t(symbol\n\t\t(lib_id "{esc(lib_id)}")\n\t\t(at {x:g} {y:g} 0)\n'
               f'\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
               f'\t\t(dnp no)\n\t\t(uuid "{uid("sym", ref)}")')
    out.append(sym_prop("Reference", nref, x + l + 1, y + t - 3.4, hide=False,
                        size=1.5748, justify="left bottom"))
    out.append(sym_prop("Value", val_of(ref), x + l + 1, y + t - 0.8, hide=False,
                        size=1.27, justify="left bottom"))
    out.append(sym_prop("Footprint", fpname_of(ref), 0, 0))
    out.append(sym_prop("Datasheet", "", 0, 0))
    out.append(sym_prop("Description", "", 0, 0))
    out.append(sym_prop("Source Board", f"Four Motor Control Board M5 / {ref}", 0, 0))
    for num, *_ in pin_labels(ref):
        out.append(f'\t\t(pin "{esc(num)}"\n\t\t\t(uuid "{uid("pin", ref, num)}")\n\t\t)')
    out.append(f'\t\t(instances\n\t\t\t(project "{PROJECT}"\n'
               f'\t\t\t\t(path "/{ROOT_UUID}/{SHEET_INST}"\n'
               f'\t\t\t\t\t(reference "{nref}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)')
    out.append('\t)')
    for num, sx, sy, lang, txt in pin_labels(ref):
        if txt is None:
            out.append(no_connect(x + sx, y + sy, f'{ref}.{num}'))
        else:
            kind = 'hierarchical_label' if txt in HIER else 'global_label'
            shape = 'bidirectional' if txt in HIER else 'input'
            out.append(label(kind, txt, x + sx, y + sy, lang, shape))

# ERC power-source markers for rails fed from a connector or a switching node
flag_y = cy + 8.0
for i, rail in enumerate(('VIN', '+3V3', 'VBUS_MC', 'VIN_BUCK')):
    x, y = snap(MARGIN_X + i * 55), snap(flag_y)
    out.append(f'\t(symbol\n\t\t(lib_id "MaslowMerged:PWR_FLAG")\n\t\t(at {x:g} {y:g} 0)\n'
               f'\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom no)\n\t\t(on_board no)\n'
               f'\t\t(dnp no)\n\t\t(uuid "{uid("flg", rail)}")')
    out.append(sym_prop("Reference", f"#FLG{i+1}", x, y - 7, hide=True))
    out.append(sym_prop("Value", "PWR_FLAG", x + 2, y - 4, hide=False, justify="left"))
    out.append(sym_prop("Footprint", "", 0, 0))
    out.append(sym_prop("Datasheet", "", 0, 0))
    out.append(sym_prop("Description", "", 0, 0))
    out.append(f'\t\t(pin "1"\n\t\t\t(uuid "{uid("flgpin", rail)}")\n\t\t)')
    out.append(f'\t\t(instances\n\t\t\t(project "{PROJECT}"\n'
               f'\t\t\t\t(path "/{ROOT_UUID}/{SHEET_INST}"\n'
               f'\t\t\t\t\t(reference "#FLG{i+1}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)')
    out.append('\t)')
    out.append(label('global_label', rail, x, y, 90))
out.append(text_note("PWR_FLAG markers only tell ERC these rails are driven - "
                     "they are not parts.", MARGIN_X, flag_y + 8, 1.9, bold=False))

out.append('\t(embedded_fonts no)')
out.append(')')

dest = os.path.join(PROJ, "motor_control_section.kicad_sch")
open(dest, 'w', encoding='utf-8').write("\n".join(out) + "\n")
print(f"wrote {dest}")
print(f"  {len(P)} of {len(fps)} components placed (deleted: {sorted(DELETED)})")
print(f"  page {PAGE_W:.0f} x {PAGE_H:.0f} mm")
