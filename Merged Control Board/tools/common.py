"""Shared helpers for the merged-board generators."""
import hashlib, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ROOT = os.path.dirname(PROJ)

MOTOR_PCB = os.path.join(
    ROOT, "Motor Controller Board",
    "Four Motor Control Board M5_fbc631ad57bc4ffbb8f9b332692f9e33.kicad_pcb")
DRIVER_SCH = os.path.join(
    ROOT, "KiCad Boards", "ProPrj_Driver Board to share_2026-08-01.kicad_sch")

NS = "maslow-merged-control-board"


def kicad_cli():
    for c in ("kicad-cli", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
              "/usr/bin/kicad-cli", "/usr/local/bin/kicad-cli"):
        if os.path.sep not in c:
            from shutil import which
            p = which(c)
            if p:
                return p
        elif os.path.exists(c):
            return c
    raise SystemExit("kicad-cli not found")


def uid(*parts):
    """Deterministic UUID so regenerating the project keeps stable identities."""
    h = hashlib.sha1((NS + "|" + "|".join(str(p) for p in parts)).encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-4{h[13:16]}-a{h[17:20]}-{h[20:32]}"


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


# ----------------------------------------------------------- s-expression bits
def close_paren(text, s):
    """Index just past the ')' that closes the '(' at `s`."""
    d = 0; i = s; instr = False
    while i < len(text):
        c = text[i]
        if instr:
            if c == "\\": i += 2; continue
            if c == '"': instr = False
        else:
            if c == '"': instr = True
            elif c == "(": d += 1
            elif c == ")":
                d -= 1
                if d == 0: return i + 1
        i += 1
    raise ValueError("unbalanced parentheses")


def top_blocks(text, keyword, indent="\t"):
    """Every (keyword ...) node at the given indent, as (start, end, body)."""
    pat = re.compile(r"^%s\(%s[\s\"]" % (re.escape(indent), re.escape(keyword)), re.M)
    for m in pat.finditer(text):
        s = m.start() + len(indent)
        e = close_paren(text, s)
        yield s, e, text[s:e]


# -------------------------------------------------- symbol library inspection
def _pin_nodes(block):
    for m in re.finditer(r"\(pin\s+\w+\s+\w+\s*\n", block):
        s = m.start()
        yield block[s:close_paren(block, s)]


def load_lib_pins(path):
    """symbol name -> {pin number: (x, y, angle)}"""
    txt = open(path, encoding="utf-8").read()
    out = {}
    for s, e, blk in top_blocks(txt, "symbol"):
        name = re.match(r'\(symbol "([^"]+)"', blk).group(1)
        pins = {}
        for p in _pin_nodes(blk):
            at = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", p)
            num = re.search(r'\(number "([^"]*)"', p)
            if at and num:
                pins[num.group(1)] = (float(at.group(1)), float(at.group(2)), float(at.group(3)))
        if pins:
            out[name] = pins
    return out


def load_lib_body(path):
    """symbol name -> (minx, maxx, miny, maxy) of its drawn body."""
    txt = open(path, encoding="utf-8").read()
    out = {}
    for s, e, blk in top_blocks(txt, "symbol"):
        name = re.match(r'\(symbol "([^"]+)"', blk).group(1)
        xs, ys = [], []
        for tag in ("start", "end", "center", "xy"):
            for m in re.finditer(r"\(%s ([-\d.]+) ([-\d.]+)\)" % tag, blk):
                xs.append(float(m.group(1))); ys.append(float(m.group(2)))
        for m in re.finditer(r"\(radius ([-\d.]+)\)", blk):
            r = float(m.group(1)); xs += [min(xs) - r, max(xs) + r] if xs else []
        if xs:
            out[name] = (min(xs), max(xs), min(ys), max(ys))
    return out


# --------------------------------------------------------- .kicad_pcb reading
def load_pcb_footprints(path=MOTOR_PCB):
    """reference -> {value, footprint, pad_nets: {pad: {'net': name}}}

    Read straight out of the board file, so the generators depend on the source
    board and not on any intermediate analysis output.
    """
    txt = open(path, encoding="utf-8").read()
    out = {}
    for s, e, blk in top_blocks(txt, "footprint"):
        fp = re.match(r'\(footprint "([^"]+)"', blk).group(1)
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk)
        val = re.search(r'\(property "Value" "([^"]*)"', blk)
        pads = {}
        for m in re.finditer(r'\(pad "([^"]*)"', blk):
            ps = m.start()
            pad = blk[ps:close_paren(blk, ps)]
            n = re.search(r'\(net (?:\d+ )?"([^"]*)"\)', pad)
            if n:
                pads[m.group(1)] = {"net": n.group(1)}
        if ref:
            out[ref.group(1)] = {"value": val.group(1) if val else "",
                                 "footprint": fp, "pad_nets": pads}
    return out
