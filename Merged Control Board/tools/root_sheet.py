"""Root sheet of the merged board: two sub-sheets, joined only at BoardCom."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import uid, esc, PROJ, DRIVER_SCH

PROJECT = "Maslow Mini Merged Board"
ROOT_UUID = uid("sheetfile", "root")
M_INST, D_INST = uid("sheetsym", "motor"), uid("sheetsym", "driver")

def eff(size=1.27, just=None, bold=False):
    j = f'\n\t\t\t\t(justify {just})' if just else ''
    b = '\n\t\t\t\t\t(bold yes)' if bold else ''
    return (f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size {size} {size}){b}\n\t\t\t\t){j}\n\t\t\t)')

def sheet(name, filename, x, y, w, h, inst_uuid, pins, page):
    o = [f'\t(sheet\n\t\t(at {x} {y})\n\t\t(size {w} {h})',
         '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)',
         '\t\t(stroke\n\t\t\t(width 0.3)\n\t\t\t(type solid)\n\t\t)',
         '\t\t(fill\n\t\t\t(color 0 0 0 0.0000)\n\t\t)',
         f'\t\t(uuid "{inst_uuid}")',
         f'\t\t(property "Sheetname" "{esc(name)}"\n\t\t\t(at {x} {y - 2.4} 0)\n'
         + eff(2.5, "left bottom", True) + '\n\t\t)',
         f'\t\t(property "Sheetfile" "{esc(filename)}"\n\t\t\t(at {x} {y + h + 3.5} 0)\n'
         + eff(1.6, "left top") + '\n\t\t)']
    for pname, ptype, px, py, pang, just in pins:
        o.append(f'\t\t(pin "{esc(pname)}" {ptype}\n\t\t\t(at {px} {py} {pang})\n'
                 + eff(1.6, just) + f'\n\t\t\t(uuid "{uid("sheetpin", inst_uuid, pname)}")\n\t\t)')
    o.append(f'\t\t(instances\n\t\t\t(project "{PROJECT}"\n\t\t\t\t(path "/{ROOT_UUID}"\n'
             f'\t\t\t\t\t(page "{page}")\n\t\t\t\t)\n\t\t\t)\n\t\t)')
    o.append('\t)')
    return "\n".join(o)

def wire(x1, y1, x2, y2, tag):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1} {y1})\n\t\t\t(xy {x2} {y2})\n\t\t)\n'
            f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "{uid("wire", tag)}")\n\t)')

def text(s, x, y, size=2.0, bold=False):
    b = '\n\t\t\t\t(bold yes)' if bold else ''
    return (f'\t(text "{esc(s)}"\n\t\t(at {x} {y} 0)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size}){b}\n\t\t\t)\n'
            f'\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "{uid("rtxt", s, x, y)}")\n\t)')

def label(name, x, y, angle, tag):
    just = "left" if angle in (0, 90) else "right"
    return (f'\t(label "{esc(name)}"\n\t\t(at {x} {y} {angle})\n'
            + eff(1.8, just) + f'\n\t\t(uuid "{uid("rlbl", tag)}")\n\t)')

MX, MY, MW, MH = 39.37, 88.9, 100.33, 39.37
DX, DY, DW, DH = 234.95, 88.9, 100.33, 39.37

out = ['(kicad_sch', '\t(version 20260306)', '\t(generator "maslow-merge")',
       '\t(generator_version "10.0")', f'\t(uuid "{ROOT_UUID}")', '\t(paper "A3")',
       '\t(title_block\n\t\t(title "Maslow Mini Merged Control Board")\n'
       '\t\t(rev "M1")\n\t\t(company "Maslow CNC")\n'
       '\t\t(comment 1 "Merge of \'Four Motor Control Board M5\' and \'Driver Board 2026-08-01\'")\n'
       '\t\t(comment 2 "Both ESP32-S3 MCUs are retained; they meet only on the BoardCom pair")\n'
       '\t)',
       '\t(lib_symbols\n\t)']

out.append(text("MASLOW MINI  -  MERGED CONTROL BOARD", 25, 30, 4.5, True))
out.append(text("One PCB.  Both ESP32-S3 MCUs are retained and meet only on the BoardCom pair "
                "below - everything else about the two", 25, 38, 2.2))
out.append(text("original circuits is unchanged, apart from the redundancy that a single board "
                "makes pointless.", 25, 44, 2.2))
out.append(text("The 2x5 board-to-board header (H1 on both boards) is gone.  Its four signal pins "
                "become the two BoardCom nets;", 25, 53, 2.0))
out.append(text("its power pins (VIN x3, GND x3) become shared VIN and GND rails spanning both "
                "sections.", 25, 59, 2.0))
out.append(text("Each section still has its own ESP32-S3, its own USB-C programming port and its "
                "own boot button.", 25, 65, 2.0))

motor_pins = [("BOARDCOM_A", "bidirectional", MX + MW, MY + 13.97, 0, "right"),
              ("BOARDCOM_B", "bidirectional", MX + MW, MY + 24.13, 0, "right")]
driver_pins = [("BOARDCOM_A", "bidirectional", DX, DY + 13.97, 180, "left"),
               ("BOARDCOM_B", "bidirectional", DX, DY + 24.13, 180, "left")]

out.append(sheet("Motor Control Section", "motor_control_section.kicad_sch",
                 MX, MY, MW, MH, M_INST, motor_pins, 2))
out.append(sheet("Driver Section", "driver_section.kicad_sch",
                 DX, DY, DW, DH, D_INST, driver_pins, 3))

for i, pname in enumerate(("BOARDCOM_A", "BOARDCOM_B")):
    y = MY + 13.97 + i * 10.16
    out.append(wire(MX + MW, y, DX, y, pname))
    out.append(label(pname, round((MX + MW + DX) / 2 / 1.27) * 1.27, y, 0, pname))

out.append(text("BoardCom - the only electrical link between the two MCUs", MX + MW + 6, MY + 8, 1.8, True))
out.append(text("BOARDCOM_A:  motor IO16  <->  driver IO38", MX + MW + 6, MY + 34, 1.6))
out.append(text("BOARDCOM_B:  motor IO15  <->  driver IO39", MX + MW + 6, MY + 39, 1.6))
out.append(text("(the crossover is the one the mated H1 headers used to make:", MX + MW + 6, MY + 45, 1.6))
out.append(text(" motor H1.1/1.3 -> driver H1.1/1.3 with BOARDCOM1/2 swapped between the boards)",
                MX + MW + 6, MY + 50, 1.6))

out.append(text("SHARED ACROSS BOTH SECTIONS", 25, 165, 2.4, True))
out.append(text("VIN (XT60 input, was H1 pins 6/8/10)   -   GND (was H1 pins 5/7/9)", 25, 172, 2.0))
out.append(text("+3V3   -   one LM2596 (U116, 3 A) now feeds both sections.  The driver board's "
                "0.5 A MP2459 and its chain (U2, L3, D2, D6, C80, C81, R61-R63) are deleted;", 25, 178, 2.0))
out.append(text("            D7 is kept and ORs the driver USB port's VBUS into the shared buck "
                "input, so either USB port can still power the board.", 25, 184, 2.0))
out.append(text("RST   -   one EN net.  SW2 resets both MCUs; R28 (10k) + C134 (1 uF) are the "
                "single RC.  R128 and C30 deleted.", 25, 190, 2.0))
out.append(text("Also removed as redundant:  D101 + R115 (second power-on LED; LED2 + R17 kept), "
                "and D102/D103 changed SS14 -> SS36 to match D7.", 25, 196, 2.0))
out.append(text("Kept separate on purpose:  BOOT_MC / BOOT_DRV, the two USB-C ports, and the "
                "two MCUs themselves.", 25, 205, 2.0))
out.append(text("Motor-section reference designators are the originals + 100 (U2 -> U102, ...) so "
                "they do not collide with the driver section.", 25, 211, 2.0))

out.append('\t(sheet_instances\n'
           '\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n'
           f'\t\t(path "/{M_INST}"\n\t\t\t(page "2")\n\t\t)\n'
           f'\t\t(path "/{D_INST}"\n\t\t\t(page "3")\n\t\t)\n\t)')
out.append('\t(embedded_fonts no)')
out.append(')')

open(os.path.join(PROJ, f"{PROJECT}.kicad_sch"), 'w', encoding='utf-8').write("\n".join(out) + "\n")

# ---- drop sheet_instances from the two child sheets (only the root carries them)
for child in ("motor_control_section.kicad_sch", "driver_section.kicad_sch"):
    p = os.path.join(PROJ, child)
    t = open(p, encoding='utf-8').read()
    t = re.sub(r'\t\(sheet_instances\n(?:.*\n)*?\t\)\n', '', t, count=1)
    open(p, 'w', encoding='utf-8').write(t)

# ---- project file, based on the driver board's settings
pro = json.load(open(DRIVER_SCH.replace(".kicad_sch", ".kicad_pro")))
pro['meta'] = {'filename': f'{PROJECT}.kicad_pro', 'version': 3}
pro['sheets'] = [[ROOT_UUID, 'Root'], [M_INST, 'Motor Control Section'], [D_INST, 'Driver Section']]
pro['boards'] = []
pro.setdefault('schematic', {})['legacy_lib_list'] = []
json.dump(pro, open(os.path.join(PROJ, f"{PROJECT}.kicad_pro"), 'w'), indent=2)

# ---- library tables
open(os.path.join(PROJ, "sym-lib-table"), 'w').write(
    '(sym_lib_table\n'
    '  (version 7)\n'
    '  (lib (name "ProPrj_Dri-easyedapro")(type "KiCad")(uri "${KIPRJMOD}/ProPrj_Dri-easyedapro.kicad_sym")(options "")(descr "Symbols carried over from the driver board"))\n'
    '  (lib (name "MaslowMerged")(type "KiCad")(uri "${KIPRJMOD}/MaslowMerged.kicad_sym")(options "")(descr "Symbols authored for the motor-control section"))\n'
    ')\n')
open(os.path.join(PROJ, "fp-lib-table"), 'w').write(
    '(fp_lib_table\n'
    '  (version 7)\n'
    '  (lib (name "ProPrj_Dri-easyedapro")(type "KiCad")(uri "${KIPRJMOD}/ProPrj_Dri-easyedapro.pretty")(options "")(descr "Footprints carried over from the driver board"))\n'
    '  (lib (name "MaslowMerged")(type "KiCad")(uri "${KIPRJMOD}/MaslowMerged.pretty")(options "")(descr "Footprints extracted from the motor control board PCB"))\n'
    ')\n')
print("wrote root sheet, project file and library tables")
