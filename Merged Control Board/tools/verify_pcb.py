"""Check the generated PCB against the schematic and against the source boards.

  1. every schematic component appears exactly once on the board, with the
     footprint the schematic asks for
  2. every pad carries the net the schematic gives it - compared as a partition
     of (reference, pad) nodes, so net naming cannot hide an error
  3. each footprint's schematic path points at the right sheet and symbol
  4. the parts that were supposed to keep their positions really did, to within
     a rigid translation of their section

    python3 tools/verify_pcb.py
"""
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import uid, close_paren, PROJ, MOTOR_PCB, DRIVER_SCH, kicad_cli
from pcb_layout import (FIXED_MOTOR, FIXED_DRIVER, MOTOR_SHIFT, DRIVER_SHIFT,
                        REF_OFFSET, MOTOR_SHEET, DRIVER_SHEET, DRIVER_PCB,
                        source_footprints, blocks)

BOARD = os.path.join(PROJ, "Maslow Mini Merged Board.kicad_pcb")
MERGED_SCH = os.path.join(PROJ, "Maslow Mini Merged Board.kicad_sch")
TOL = 0.001


def board_footprints():
    txt = open(BOARD, encoding="utf-8").read()
    out = {}
    for s, e in blocks(txt, "footprint"):
        blk = txt[s:e]
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        at = re.search(r"^\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk, re.M)
        pads = {}
        for pm in re.finditer(r'\(pad "([^"]*)"', blk):
            pad = blk[pm.start():close_paren(blk, pm.start())]
            n = re.search(r'\(net (?:\d+ )?"([^"]*)"\)', pad)
            if pm.group(1):
                pads[pm.group(1)] = n.group(1) if n else None
        out[ref] = {
            "footprint": re.match(r'\(footprint "([^"]+)"', blk).group(1),
            "at": (float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)),
            "layer": re.search(r'^\t\t\(layer "([^"]+)"\)', blk, re.M).group(1),
            "path": (re.search(r'^\t\t\(path "([^"]*)"\)', blk, re.M) or [None, None])[1],
            "pads": pads,
        }
    return out


def main():
    with tempfile.TemporaryDirectory() as tmp:
        xml = os.path.join(tmp, "n.xml")
        subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadxml",
                        "-o", xml, MERGED_SCH], check=True, capture_output=True, text=True)
        root = ET.parse(xml).getroot()
    sch = {c.get("ref"): (c.find("value").text or "", c.find("footprint").text or "")
           for c in root.find("components").findall("comp")}
    sch_nets = {}
    for net in root.find("nets").findall("net"):
        for n in net.findall("node"):
            sch_nets.setdefault(net.get("name"), set()).add((n.get("ref"), n.get("pin")))

    pcb = board_footprints()
    fails = []

    # 1 - component set and footprint assignment
    missing = sorted(set(sch) - set(pcb))
    extra = sorted(set(pcb) - set(sch))
    if missing:
        fails.append(f"on the schematic but not the board: {missing}")
    if extra:
        fails.append(f"on the board but not the schematic: {extra}")
    wrong_fp = [r for r in sch if r in pcb and pcb[r]["footprint"] != sch[r][1]]
    if wrong_fp:
        fails.append(f"footprint differs from the schematic: {wrong_fp}")
    print(f"components: schematic {len(sch)}, board {len(pcb)}")

    # 2 - nets, as a partition
    pcb_nets = {}
    for ref, f in pcb.items():
        for pad, net in f["pads"].items():
            if net:
                pcb_nets.setdefault(net, set()).add((ref, pad))
    exp = {frozenset(v) for v in sch_nets.values() if len(v) > 1}
    act = {frozenset(v) for v in pcb_nets.values() if len(v) > 1}
    print(f"multi-pad nets: schematic {len(exp)}, board {len(act)}")
    if exp - act:
        for f in sorted(exp - act, key=len)[:5]:
            fails.append(f"net on the schematic but not the board: {sorted(f)}")
    if act - exp:
        for f in sorted(act - exp, key=len)[:5]:
            fails.append(f"net on the board but not the schematic: {sorted(f)}")

    # 3 - schematic link
    paths = {}
    for ref, f in pcb.items():
        n = int(re.search(r"\d+", ref).group(0))
        src = (f"{re.match(r'[A-Za-z_]+', ref).group(0)}{n - REF_OFFSET}"
               if n >= REF_OFFSET else ref)
        sheet = MOTOR_SHEET if n >= REF_OFFSET else DRIVER_SHEET
        if not f["path"] or not f["path"].startswith(f"/{sheet}/"):
            fails.append(f"{ref}: path does not point at its sheet ({f['path']})")
        paths.setdefault(f["path"], []).append(ref)
        if n >= REF_OFFSET and f["path"] != f"/{sheet}/{uid('sym', src)}":
            fails.append(f"{ref}: path does not match its schematic symbol")
    dupes = {p: r for p, r in paths.items() if len(r) > 1}
    if dupes:
        fails.append(f"duplicate schematic paths: {dupes}")
    print(f"schematic paths: {len(paths)} unique across {len(pcb)} footprints")

    # 4 - the fixed parts really are where they were
    motor_src, _ = source_footprints(MOTOR_PCB)
    driver_src, _ = source_footprints(DRIVER_PCB)

    def src_at(blk):
        m = re.search(r"^\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk, re.M)
        return float(m.group(1)), float(m.group(2)), float(m.group(3) or 0)

    checked = 0
    for src_ref in sorted(FIXED_MOTOR):
        ref = f"{re.match(r'[A-Za-z_]+', src_ref).group(0)}{int(re.search(r'\d+', src_ref).group(0)) + REF_OFFSET}"
        ox, oy, orot = src_at(motor_src[src_ref])
        nx, ny, nrot = pcb[ref]["at"]
        if (abs(nx - (ox + MOTOR_SHIFT[0])) > TOL or abs(ny - (oy + MOTOR_SHIFT[1])) > TOL
                or abs(nrot - orot) > TOL):
            fails.append(f"{ref} moved: source ({ox},{oy},{orot}) -> board ({nx},{ny},{nrot})")
        checked += 1
    for src_ref in sorted(FIXED_DRIVER):
        ox, oy, orot = src_at(driver_src[src_ref])
        nx, ny, nrot = pcb[src_ref]["at"]
        if (abs(nx - (ox + DRIVER_SHIFT[0])) > TOL or abs(ny - (oy + DRIVER_SHIFT[1])) > TOL
                or abs(nrot - orot) > TOL):
            fails.append(f"{src_ref} moved: source ({ox},{oy},{orot}) -> board ({nx},{ny},{nrot})")
        checked += 1
    print(f"fixed parts: {checked} checked against their source-board coordinates")

    print()
    if fails:
        print(f"{len(fails)} PROBLEM(S):")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS - the board matches the schematic, and every part that was meant to "
          "keep its position is exactly where it was.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
