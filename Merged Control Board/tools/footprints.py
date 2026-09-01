"""Extract the motor control board's embedded footprints into a project library."""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJ, MOTOR_PCB

SRC = MOTOR_PCB
OUT = os.path.join(PROJ, "MaslowMerged.pretty")
os.makedirs(OUT, exist_ok=True)

txt = open(SRC, encoding='utf-8').read()
VERSION = re.search(r'\(version (\d+)\)', txt).group(1)

def close(text, s):
    d = 0; i = s; instr = False
    while i < len(text):
        c = text[i]
        if instr:
            if c == '\\': i += 2; continue
            if c == '"': instr = False
        else:
            if c == '"': instr = True
            elif c == '(': d += 1
            elif c == ')':
                d -= 1
                if d == 0: return i + 1
        i += 1
    raise ValueError

def children(block):
    """(name, start, end) of every direct child node of an s-expression block."""
    i = block.index('(') + 1
    while i < len(block) and block[i] not in ' \t\n()':
        i += 1
    out = []
    d = 1; instr = False
    while i < len(block):
        c = block[i]
        if instr:
            if c == '\\': i += 2; continue
            if c == '"': instr = False
            i += 1; continue
        if c == '"':
            instr = True
        elif c == '(':
            if d == 1:
                e = close(block, i)
                j = i + 1
                while j < len(block) and block[j] not in ' \t\n()': j += 1
                out.append((block[i+1:j], i, e))
                i = e; continue
            d += 1
        elif c == ')':
            d -= 1
            if d == 0: break
        i += 1
    return out

DROP = {'at', 'uuid', 'path', 'sheetname', 'sheetfile', 'component_classes'}
written = []
seen = set()
for m in re.finditer(r'^\t\(footprint "', txt, re.M):
    s = m.start()
    block = txt[s:close(txt, s)]
    name = re.match(r'\t\(footprint "([^"]+)"', block).group(1)
    if name in seen:
        continue
    seen.add(name)
    block = re.sub(r'^\t', '', block, flags=re.M)      # dedent one level

    keep = []
    for cname, cs, ce in children(block):
        if cname in DROP:
            continue
        chunk = block[cs:ce]
        if cname == 'property':
            pname = re.match(r'\(property "([^"]*)"', chunk).group(1)
            if pname == 'Reference':
                chunk = re.sub(r'\(property "Reference" "[^"]*"', '(property "Reference" "REF**"', chunk, count=1)
            elif pname == 'Value':
                chunk = re.sub(r'\(property "Value" "[^"]*"',
                               '(property "Value" "%s"' % name.replace('"', ''), chunk, count=1)
            # strip per-item uuids inside properties so the library has none
        chunk = re.sub(r'\n\s*\(uuid "[^"]*"\)', '', chunk)
        keep.append(chunk)

    body = "\n\t".join(keep)
    out = (f'(footprint "{name}"\n'
           f'\t(version {VERSION})\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
           f'\t{body}\n)\n')
    open(os.path.join(OUT, name.replace('/', '_') + '.kicad_mod'), 'w', encoding='utf-8').write(out)
    written.append(name)

print(f"extracted {len(written)} footprints (pcb file format version {VERSION})")
