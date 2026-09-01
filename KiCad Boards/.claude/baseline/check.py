#!/usr/bin/env python3
"""Compare the working schematic against the last verified baseline.

Answers one question: did anything ELECTRICAL change?

Moving symbols, wires and labels around is safe by definition as long as the
netlist is identical.  Every hazard of rearranging -- a dragged pin landing on
another pin, a wire endpoint snapping onto the wrong pin, a label dropped on a
neighbouring pin, a wire pulled off a pin -- shows up as a netlist difference,
so a clean netlist diff is a complete electrical check, not a partial one.

Usage:
    python3 .claude/baseline/check.py
    python3 .claude/baseline/check.py --accept    # promote current -> baseline
"""
import glob
import json
import os
import subprocess
import sys
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
ANALYZER = os.path.join(PROJ, ".claude/skills/kicad/scripts/analyze_schematic.py")

sch = glob.glob(os.path.join(PROJ, "*.kicad_sch"))
sch = [s for s in sch if "baseline" not in s]
assert len(sch) == 1, f"expected 1 schematic, found {sch}"
SCH = sch[0]

BASE_JSON = os.path.join(HERE, "verified.json")
BASE_ERC = os.path.join(HERE, "verified_erc.rpt")
BASE_SCH = os.path.join(HERE, "verified.kicad_sch")

TMP = "/tmp/_kicad_check"
os.makedirs(TMP, exist_ok=True)
CUR_JSON = os.path.join(TMP, "cur.json")
CUR_ERC = os.path.join(TMP, "cur_erc.rpt")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def netmap(d):
    """net name -> sorted tuple of ref.pin, ignoring auto-generated placeholder names."""
    return {
        k: tuple(sorted(f"{p['component']}.{p['pin_number']}" for p in v.get("pins", [])))
        for k, v in d["nets"].items()
        if not k.startswith("__unnamed")
    }


def pinmap(d):
    """ref.pin -> net name, for every pin including placeholder nets."""
    m = {}
    for net, v in d["nets"].items():
        for p in v.get("pins", []):
            m[f"{p['component']}.{p['pin_number']}"] = net
    return m


def parts(d):
    return {
        c["reference"]: (c.get("value"), c.get("footprint"))
        for c in d["components"]
        if c.get("reference") and not c["reference"].startswith("#")
    }


def erc_counts(path):
    txt = open(path, encoding="utf-8").read()
    from collections import Counter
    return Counter(re.findall(r"\[([a-z_]+)\]:", txt))


if "--accept" in sys.argv:
    run([sys.executable, ANALYZER, SCH, "--output", CUR_JSON])
    run([CLI, "sch", "erc", "--output", CUR_ERC, "--severity-all", SCH])
    import shutil
    shutil.copy(CUR_JSON, BASE_JSON)
    shutil.copy(CUR_ERC, BASE_ERC)
    shutil.copy(SCH, BASE_SCH)
    print("baseline updated to current schematic")
    sys.exit(0)

r = run([sys.executable, ANALYZER, SCH, "--output", CUR_JSON])
if r.returncode != 0:
    print("ANALYZER FAILED:\n", r.stderr[-2000:])
    sys.exit(2)
run([CLI, "sch", "erc", "--output", CUR_ERC, "--severity-all", SCH])

base = json.load(open(BASE_JSON))
cur = json.load(open(CUR_JSON))

problems = 0

# ---- 1. netlist ------------------------------------------------------------
nb, nc = netmap(base), netmap(cur)
added = sorted(set(nc) - set(nb))
removed = sorted(set(nb) - set(nc))
changed = sorted(k for k in set(nb) & set(nc) if nb[k] != nc[k])

print("=" * 68)
print("NETLIST")
print("=" * 68)
if not (added or removed or changed):
    print(f"  IDENTICAL  ({len(nc)} named nets, "
          f"{sum(len(v) for v in nc.values())} pin connections)")
else:
    problems += 1
    for k in removed:
        print(f"  NET REMOVED  {k}: {nb[k]}")
    for k in added:
        print(f"  NET ADDED    {k}: {nc[k]}")
    for k in changed:
        lost = set(nb[k]) - set(nc[k])
        got = set(nc[k]) - set(nb[k])
        print(f"  NET CHANGED  {k}")
        if lost:
            print(f"      lost:   {sorted(lost)}")
        if got:
            print(f"      gained: {sorted(got)}")

# ---- 2. per-pin movement (catches pin hopping between nets) ----------------
pb, pc = pinmap(base), pinmap(cur)
moved = [
    (k, pb.get(k), pc.get(k))
    for k in sorted(set(pb) | set(pc))
    if pb.get(k) != pc.get(k)
    and not (str(pb.get(k)).startswith("__unnamed") and str(pc.get(k)).startswith("__unnamed"))
]
print()
print("=" * 68)
print("PIN -> NET")
print("=" * 68)
print(f"  pins: {len(pb)} -> {len(pc)}")
if moved:
    problems += 1
    for k, a, b in moved:
        print(f"  MOVED  {k}: {a} -> {b}")
else:
    print("  no pin changed net")

# ---- 3. components ---------------------------------------------------------
qb, qc = parts(base), parts(cur)
print()
print("=" * 68)
print("COMPONENTS")
print("=" * 68)
print(f"  count: {len(qb)} -> {len(qc)}")
diff = False
for r_ in sorted(set(qb) | set(qc)):
    if qb.get(r_) != qc.get(r_):
        print(f"  {r_}: {qb.get(r_)} -> {qc.get(r_)}")
        diff = True
if diff:
    problems += 1
if not diff:
    print("  all values/footprints unchanged")

# ---- 4. ERC ----------------------------------------------------------------
eb, ec = erc_counts(BASE_ERC), erc_counts(CUR_ERC)
print()
print("=" * 68)
print("ERC")
print("=" * 68)
print(f"  {'rule':<28}{'base':>7}{'now':>7}")
worse = False
for k in sorted(set(eb) | set(ec), key=lambda k: -max(eb.get(k, 0), ec.get(k, 0))):
    d = ec.get(k, 0) - eb.get(k, 0)
    flag = ""
    if d > 0:
        flag = f"   +{d}  <-- NEW"
        worse = True
    elif d < 0:
        flag = f"   {d}  (improved)"
    print(f"  {k:<28}{eb.get(k,0):>7}{ec.get(k,0):>7}{flag}")
print(f"  {'TOTAL':<28}{sum(eb.values()):>7}{sum(ec.values()):>7}")
if worse:
    problems += 1

print()
print("=" * 68)
if problems == 0:
    print("RESULT: CLEAN - rearrangement changed nothing electrical.")
else:
    print(f"RESULT: {problems} area(s) differ - review the lines marked above.")
print("=" * 68)
sys.exit(1 if problems else 0)
