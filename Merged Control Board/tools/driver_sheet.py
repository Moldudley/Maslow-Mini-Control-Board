"""Turn the standalone Driver Board schematic into the Driver Section sub-sheet
of the merged board.

Edits, and nothing else:
  1. delete H1 (2x5 board-to-board header) and the ten global labels that sat on
     its pins (BOARDCOM1/2, VIN x3, GND x3)
  2. the surviving BOARDCOM1/BOARDCOM2 labels at the ESP32 become hierarchical
     pins.  The crossover from the old H1 mating is preserved:
        driver BOARDCOM1 (IO39) -> BOARDCOM_B
        driver BOARDCOM2 (IO38) -> BOARDCOM_A
  3. 3V3 -> +3V3_DRV and BOOT -> BOOT_DRV so they do not merge with the motor
     section's rails of the same name.  VIN and GND deliberately DO merge -
     those are the rails H1 used to carry between the boards.
  4. re-target symbol instance paths at the new project / sheet.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import uid, esc, PROJ, DRIVER_SCH

SRC = DRIVER_SCH
DEST = os.path.join(PROJ, "driver_section.kicad_sch")

OLD_ROOT_UUID = "d47c1592-85aa-4594-b513-aeb672840812"
OLD_PROJECT = "ProPrj_Driver Board to share_2026-08-01"
PROJECT = "Maslow Mini Merged Board"
SHEET_UUID = uid("sheetfile", "driver_section")
ROOT_UUID = uid("sheetfile", "root")
SHEET_INST = uid("sheetsym", "driver")

txt = open(SRC, encoding='utf-8').read()

def blocks(text, keyword):
    """Yield (start, end) of every top-level (keyword ...) node."""
    for m in re.finditer(r'^\t\(%s[\s"]' % re.escape(keyword), text, re.M):
        s = m.start()
        depth = 0; i = s; instr = False
        while i < len(text):
            c = text[i]
            if instr:
                if c == '\\': i += 2; continue
                if c == '"': instr = False
            else:
                if c == '"': instr = True
                elif c == '(': depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0: i += 1; break
            i += 1
        yield s, i

# --------------------------------------------------------------- 1. drop H1
cuts = []
for s, e in blocks(txt, 'symbol'):
    blk = txt[s:e]
    if re.search(r'\(property "Reference" "H1"', blk):
        cuts.append((s, e))
assert len(cuts) == 1, cuts

# H1 pin coordinates - the ten labels that sat directly on them
H1_LABEL_POINTS = {
    (574.04, 43.18), (591.82, 38.1), (591.82, 35.56), (591.82, 40.64),
    (574.04, 33.02), (574.04, 38.1), (591.82, 43.18), (574.04, 40.64),
    (591.82, 33.02), (574.04, 35.56),
}
removed_labels = []
for s, e in blocks(txt, 'global_label'):
    blk = txt[s:e]
    m = re.search(r'\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', blk)
    pt = (float(m.group(1)), float(m.group(2)))
    if pt in H1_LABEL_POINTS:
        cuts.append((s, e))
        removed_labels.append((re.match(r'\t\(global_label "([^"]+)"', blk).group(1), pt))
assert len(removed_labels) == 10, removed_labels

# ------------------------------------- 2. BOARDCOM -> hierarchical sheet pins
HIER = {'BOARDCOM1': ('BOARDCOM_B', 'bidirectional'),
        'BOARDCOM2': ('BOARDCOM_A', 'bidirectional')}
rewrites = []
for s, e in blocks(txt, 'global_label'):
    if any(s == cs for cs, ce in cuts):
        continue
    blk = txt[s:e]
    name = re.match(r'\t\(global_label "([^"]+)"', blk).group(1)
    if name in HIER:
        new, shape = HIER[name]
        m = re.search(r'\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', blk)
        x, y, a = m.group(1), m.group(2), m.group(3)
        just = "left" if float(a) in (0.0, 90.0) else "right"
        repl = (f'\t(hierarchical_label "{new}"\n\t\t(shape {shape})\n'
                f'\t\t(at {x} {y} {a})\n'
                f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.5748 1.5748)\n\t\t\t)\n'
                f'\t\t\t(justify {just})\n\t\t)\n'
                f'\t\t(uuid "{uid("hier", "driver", new)}")\n\t)')
        rewrites.append((s, e, repl))

# ---------------------------------------------- apply cuts and rewrites
edits = sorted([(s, e, None) for s, e in cuts] + rewrites, key=lambda t: -t[0])
for s, e, repl in edits:
    if repl is None:
        end = e
        while end < len(txt) and txt[end] in ' \t': end += 1
        if end < len(txt) and txt[end] == '\n': end += 1
        txt = txt[:s] + txt[end:]
    else:
        txt = txt[:s] + repl + txt[e:]

# ------------------------------------------------ 3. rail renames (labels only)
for old, new in (('3V3', '+3V3_DRV'), ('BOOT', 'BOOT_DRV')):
    before = txt.count(f'(global_label "{old}"')
    txt = txt.replace(f'(global_label "{old}"', f'(global_label "{new}"')
    print(f'  renamed {before} x global_label {old} -> {new}')

# --------------------------------------- 4. project / sheet path re-targeting
txt = txt.replace(f'(project "{OLD_PROJECT}"', f'(project "{PROJECT}"')
txt = txt.replace(f'(path "/{OLD_ROOT_UUID}"', f'(path "/{ROOT_UUID}/{SHEET_INST}"')
txt = txt.replace(f'\t(uuid "{OLD_ROOT_UUID}")', f'\t(uuid "{SHEET_UUID}")', 1)
txt = txt.replace('(generator "eeschema")', '(generator "eeschema")', 1)
txt = re.sub(r'\t\(sheet_instances\n\t\t\(path "/"\n\t\t\t\(page "1"\)\n\t\t\)\n\t\)',
             '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "3")\n\t\t)\n\t)', txt)

# a short note so the sheet says where it came from and what changed
NOTE_LINES = [
    ("DRIVER SECTION", 4.0, True),
    ("Imported unchanged from \"ProPrj_Driver Board to share_2026-08-01\", except:", 1.8, False),
    ("  - H1 (2x5 board-to-board header) deleted; BOARDCOM1/2 at U12 are now hierarchical "
     "pins BOARDCOM_B / BOARDCOM_A", 1.8, False),
    ("  - 3V3 -> +3V3_DRV and BOOT -> BOOT_DRV, to stay distinct from the motor section", 1.8, False),
    ("  - VIN and GND unchanged, and now merge with the motor section (they are what H1 "
     "pins 6/8/10 and 5/7/9 carried)", 1.8, False),
]
note = ""
y = 17.0
for line, size, bold in NOTE_LINES:
    note += (f'\t(text "{esc(line)}"\n\t\t(at 556 {y} 0)\n'
             '\t\t(effects\n\t\t\t(font\n'
             f'\t\t\t\t(size {size} {size})' + ('\n\t\t\t\t(bold yes)' if bold else '') + '\n\t\t\t)\n'
             '\t\t\t(justify left bottom)\n\t\t)\n'
             f'\t\t(uuid "{uid("txt", "driver-note", line)}")\n\t)\n')
    y += size * 1.55 + 1.4
txt = txt.replace('\t(sheet_instances', note + '\t(sheet_instances', 1)

open(DEST, 'w', encoding='utf-8').write(txt)
print("wrote", DEST)
print("  removed H1 and labels:", removed_labels)
print("  hierarchical pins:", [(r[2].split('"')[1]) for r in rewrites])
