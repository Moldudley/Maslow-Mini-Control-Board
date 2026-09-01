"""Prove the merged schematic differs from the two source boards ONLY in the
ways this project declares.

Nets are compared as a PARTITION of (reference, pin) nodes, so net *naming* is
irrelevant - what has to match is which pins end up electrically common.

Expected connectivity comes straight from the sources:
  * driver section  <- the original driver board schematic, via kicad-cli
  * motor section   <- the motor control board's PCB (it has no schematic)

then every intentional change is applied to that expectation, in two groups:
the merge itself, and the redundancy consolidation.  Anything else that moved
shows up as a mismatch.

    python3 tools/verify_netlist.py
"""
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJ, DRIVER_SCH, MOTOR_PCB, kicad_cli, load_pcb_footprints

MERGED_SCH = os.path.join(PROJ, "Maslow Mini Merged Board.kicad_sch")
REF_OFFSET = 100          # motor-section designators are the originals + 100

# ---------------------------------------------------------------- the merge
DROP_DRIVER = {"H1"}      # 2x5 board-to-board header
DROP_MOTOR = {"H1"}

# ------------------------------------------------- redundancy consolidation
# the driver board's 0.5 A MP2459 buck and everything that only served it
DROP_DRIVER |= {"U2", "L3", "D2", "D6", "C80", "C81", "R61", "R62", "R63"}
# EN cap: the motor side's 1 uF survives as the single RC for both MCUs
DROP_DRIVER |= {"C30"}
# EN pull-up: the driver side's R28 serves both MCUs
DROP_MOTOR |= {"R28"}
# power-on LED: the driver side's LED2 + R17 is kept
DROP_MOTOR |= {"D1", "R15"}


def netlist(sch, workdir):
    out = os.path.join(workdir, os.path.basename(sch) + ".xml")
    subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadxml",
                    "-o", out, sch], check=True, capture_output=True, text=True)
    nets = {}
    for net in ET.parse(out).getroot().find("nets").findall("net"):
        nodes = {(n.get("ref"), n.get("pin")) for n in net.findall("node")
                 if not n.get("ref").startswith("#")}
        if nodes:
            nets[net.get("name")] = nodes
    return nets


def bump(ref):
    m = re.match(r"([A-Za-z_]+)(\d+)$", ref)
    return f"{m.group(1)}{int(m.group(2)) + REF_OFFSET}"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        driver = netlist(DRIVER_SCH, tmp)
        actual = netlist(MERGED_SCH, tmp)

    gone = {r for r in DROP_DRIVER} | {bump(r) for r in DROP_MOTOR}

    expected = {}
    for name, nodes in driver.items():
        keep = {n for n in nodes if n[0] not in DROP_DRIVER}
        if keep:
            expected[("D", name)] = keep
    for ref, f in load_pcb_footprints(MOTOR_PCB).items():
        if ref in DROP_MOTOR:
            continue
        for pad, info in f["pad_nets"].items():
            expected.setdefault(("M", info["net"]), set()).add((bump(ref), pad))

    def union(a, b):
        merged = expected.pop(a, set()) | expected.pop(b, set())
        if merged:
            expected[a] = merged

    # --- the merge: BoardCom crossover the mated H1 headers used to make,
    #     plus the rails H1 carried becoming shared
    union(("M", "BOARDCOM1"), ("D", "BOARDCOM2"))   # -> BOARDCOM_A
    union(("M", "BOARDCOM2"), ("D", "BOARDCOM1"))   # -> BOARDCOM_B
    union(("M", "VCC"), ("D", "VIN"))               # shared rail, was H1 6/8/10
    union(("M", "GND"), ("D", "GND"))               # shared ground, was H1 5/7/9

    # --- consolidation: one 3.3 V regulator, one reset RC, one buck input
    union(("M", "3V3"), ("D", "3V3"))               # -> +3V3, fed by the LM2596
    union(("M", "MCU_RST"), ("D", "RST"))           # -> RST, one button for both MCUs
    union(("M", "U16_1"), ("D", "VIN_BUCK"))        # -> VIN_BUCK; D7 ORs in here now

    # --- the LM2596's TO-263 tab was floating on the source PCB and is
    #     internally GND, so the merged schematic bonds it
    expected[("M", "GND")].add((bump("U16"), "6"))

    exp = {frozenset(v) for v in expected.values() if len(v) > 1}
    act = {frozenset(v) for v in actual.values() if len(v) > 1}
    exp_name = {frozenset(v): k for k, v in expected.items()}
    act_name = {frozenset(v): k for k, v in actual.items()}

    print(f"declared deletions: {len(gone)} parts  {sorted(gone)}")
    print(f"expected multi-pin nets: {len(exp)}   actual: {len(act)}")
    missing, extra = exp - act, act - exp
    if not missing and not extra:
        print("\nEXACT MATCH - every remaining source net is reproduced, "
              "and nothing beyond the declared changes was altered.")
    for f in sorted(missing, key=lambda s: str(exp_name.get(s))):
        print(f"\nMISSING (source net {exp_name.get(f)}): {sorted(f)}")
        best = max(act, key=lambda a: len(a & f), default=frozenset())
        if best & f:
            print(f"   nearest merged net '{act_name.get(best)}':"
                  f"  extra {sorted(best - f)}   absent {sorted(f - best)}")
    for f in sorted(extra, key=lambda s: str(act_name.get(s))):
        if any(f & m for m in missing):
            continue
        print(f"\nEXTRA (merged net {act_name.get(f)}): {sorted(f)}")

    exp_nodes = {n for v in expected.values() for n in v}
    act_nodes = {n for v in actual.values() for n in v}
    stale = {n for n in act_nodes if n[0] in gone}
    print(f"\nnodes: expected {len(exp_nodes)}, in merged schematic {len(act_nodes)}")
    print("deleted parts still present (must be empty):", sorted(stale))
    print("only in merged schematic (pads left unconnected on the source PCB):",
          sorted(act_nodes - exp_nodes))
    only_src = sorted(exp_nodes - act_nodes)
    print("only in the sources (must be empty):", only_src)
    return 0 if not missing and not extra and not only_src and not stale else 1


if __name__ == "__main__":
    sys.exit(main())
