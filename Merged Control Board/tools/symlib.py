"""Generate MaslowMerged.kicad_sym - symbols for the Motor Controller Board parts.

Pin geometry convention used by the schematic generator:
  * 2-pin passives are vertical: pin 1 at (0, +3.81), pin 2 at (0, -3.81)
  * IC pins live on the left (angle 0) and right (angle 180) of a body rectangle,
    on a 2.54 mm pitch, starting at +Y and stepping down.
"""

GRID = 2.54


def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


def prop(name, value, x, y, rot=0, hide=False, size=1.27, justify=None):
    j = f"\n\t\t\t\t(justify {justify})" if justify else ""
    h = "\n\t\t\t(hide yes)" if hide else ""
    return (f'\t\t(property "{esc(name)}" "{esc(value)}"\n'
            f'\t\t\t(at {x} {y} {rot}){h}\n'
            f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size {size} {size})\n\t\t\t\t){j}\n\t\t\t)\n'
            f'\t\t)')


def pin(number, name, etype, x, y, angle, length=2.54, nsize=1.27, num_size=1.27):
    return (f'\t\t\t(pin {etype} line\n'
            f'\t\t\t\t(at {x} {y} {angle})\n'
            f'\t\t\t\t(length {length})\n'
            f'\t\t\t\t(name "{esc(name)}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size {nsize} {nsize})\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n'
            f'\t\t\t\t(number "{esc(number)}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size {num_size} {num_size})\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n'
            f'\t\t\t)')


def rect(x1, y1, x2, y2, fill="background"):
    return (f'\t\t\t(rectangle\n\t\t\t\t(start {x1} {y1})\n\t\t\t\t(end {x2} {y2})\n'
            f'\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
            f'\t\t\t\t(fill\n\t\t\t\t\t(type {fill})\n\t\t\t\t)\n\t\t\t)')


def polyline(pts, width=0.254, fill="none"):
    p = "\n".join(f'\t\t\t\t\t(xy {x} {y})' for x, y in pts)
    return (f'\t\t\t(polyline\n\t\t\t\t(pts\n{p}\n\t\t\t\t)\n'
            f'\t\t\t\t(stroke\n\t\t\t\t\t(width {width})\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
            f'\t\t\t\t(fill\n\t\t\t\t\t(type {fill})\n\t\t\t\t)\n\t\t\t)')


def circle(cx, cy, r, width=0.254, fill="none"):
    return (f'\t\t\t(circle\n\t\t\t\t(center {cx} {cy})\n\t\t\t\t(radius {r})\n'
            f'\t\t\t\t(stroke\n\t\t\t\t\t(width {width})\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
            f'\t\t\t\t(fill\n\t\t\t\t\t(type {fill})\n\t\t\t\t)\n\t\t\t)')


def symbol(name, ref_prefix, value, footprint, datasheet, description, body, ref_at, val_at,
           pin_names_offset=0.508, hide_pin_names=False, hide_pin_numbers=False, extends=None):
    hpn = "\n\t\t(pin_names\n\t\t\t(offset %s)%s\n\t\t)" % (
        pin_names_offset, "\n\t\t\t(hide yes)" if hide_pin_names else "")
    hnum = "\n\t\t(pin_numbers\n\t\t\t(hide yes)\n\t\t)" if hide_pin_numbers else ""
    out = [f'\t(symbol "{esc(name)}"{hnum}{hpn}\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)']
    out.append(prop("Reference", ref_prefix, ref_at[0], ref_at[1], justify="left bottom"))
    out.append(prop("Value", value, val_at[0], val_at[1], justify="left top"))
    out.append(prop("Footprint", footprint, 0, 0, hide=True))
    out.append(prop("Datasheet", datasheet, 0, 0, hide=True))
    out.append(prop("Description", description, 0, 0, hide=True))
    out.append(f'\t\t(symbol "{esc(name)}_0_1"')
    out.extend(body["graphics"])
    out.append('\t\t)')
    out.append(f'\t\t(symbol "{esc(name)}_1_1"')
    out.extend(body["pins"])
    out.append('\t\t)')
    out.append('\t\t(embedded_fonts no)')
    out.append('\t)')
    return "\n".join(out)


# ---------------------------------------------------------------- IC builder

def ic(name, ref_prefix, value, footprint, datasheet, description,
       left, right, bottom=(), half_width=7.62, pin_len=5.08, name_size=1.016, num_size=1.016):
    """left/right: sequences of (number, name, etype) laid top-down on a 2.54 pitch."""
    n = max(len(left), len(right))
    height = (n + 1) * GRID
    top = height / 2
    graphics = [rect(-half_width, top, half_width, -top)]
    pins = []
    for i, (num, pname, et) in enumerate(left):
        y = top - GRID * (i + 1)
        pins.append(pin(num, pname, et, -half_width - pin_len, y, 0, pin_len, name_size, num_size))
    for i, (num, pname, et) in enumerate(right):
        y = top - GRID * (i + 1)
        pins.append(pin(num, pname, et, half_width + pin_len, y, 180, pin_len, name_size, num_size))
    for i, (num, pname, et) in enumerate(bottom):
        x = -half_width + GRID * (i + 1)
        pins.append(pin(num, pname, et, x, -top - pin_len, 90, pin_len, name_size, num_size))
    return symbol(name, ref_prefix, value, footprint, datasheet, description,
                  {"graphics": graphics, "pins": pins},
                  ref_at=(-half_width, top + 1.27), val_at=(-half_width, -top - 1.27))


# ------------------------------------------------------------ passive builder

def two_pin(name, ref_prefix, value, footprint, datasheet, description, graphics,
            p1=("1", "1", "passive"), p2=("2", "2", "passive"), hide_names=True):
    pins = [pin(p1[0], p1[1], p2 and p1[2], 0, 3.81, 270, 1.27),
            pin(p2[0], p2[1], p2[2], 0, -3.81, 90, 1.27)]
    return symbol(name, ref_prefix, value, footprint, datasheet, description,
                  {"graphics": graphics, "pins": pins},
                  ref_at=(2.032, 1.27), val_at=(2.032, -1.27),
                  hide_pin_names=hide_names, hide_pin_numbers=True)


R_GFX = [rect(-1.016, 2.54, 1.016, -2.54)]
C_GFX = [polyline([(-2.032, 0.508), (2.032, 0.508)], 0.508),
         polyline([(-2.032, -0.508), (2.032, -0.508)], 0.508)]
CP_GFX = [polyline([(-2.032, 0.762), (2.032, 0.762)], 0.508),
          polyline([(-2.032, -0.508), (2.032, -0.508)], 0.508),
          polyline([(-1.778, 1.778), (-0.762, 1.778)], 0.254),
          polyline([(-1.27, 2.286), (-1.27, 1.27)], 0.254)]
L_GFX = [polyline([(0, 2.54), (0, 1.27)], 0.254),
         polyline([(0, -2.54), (0, -1.27)], 0.254),
         circle(0, 1.905 - 1.27, 0.635), circle(0, 0.635 - 1.27, 0.635),
         circle(0, -0.635 - 1.27 + 1.27, 0.635)]

def led_gfx():
    return [polyline([(-1.27, 1.27), (1.27, 1.27), (0, -1.27), (-1.27, 1.27)], 0.254, "none"),
            polyline([(-1.27, -1.27), (1.27, -1.27)], 0.254),
            polyline([(1.524, 1.778), (2.794, 2.794)], 0.15),
            polyline([(2.794, 2.794), (2.286, 2.032)], 0.15),
            polyline([(2.794, 2.794), (2.032, 2.286)], 0.15)]

def diode_gfx():
    return [polyline([(-1.27, 1.27), (1.27, 1.27), (0, -1.27), (-1.27, 1.27)], 0.254, "none"),
            polyline([(-1.27, -1.27), (1.27, -1.27)], 0.254),
            polyline([(-1.27, -1.27), (-1.27, -1.905)], 0.254),
            polyline([(1.27, -1.27), (1.27, -0.635)], 0.254)]


syms = []

# ---- generic passives (anode/cathode conventions match the source PCB netlist)
syms.append(two_pin("R", "R", "R", "", "", "Resistor", R_GFX))
syms.append(two_pin("C", "C", "C", "", "", "Unpolarized capacitor", C_GFX))
syms.append(two_pin("C_Polarized", "C", "C", "", "", "Polarized (bulk) capacitor", CP_GFX,
                    p1=("1", "+", "passive"), p2=("2", "-", "passive"), hide_names=False))
syms.append(two_pin("L", "L", "L", "", "", "Inductor", L_GFX))
# LED with pin 1 = anode  (footprints LED0603-R-RD / LED0603_RED on this board)
syms.append(two_pin("LED_A1K2", "D", "LED", "", "", "LED, pin 1 = anode, pin 2 = cathode",
                    [polyline([(-1.27, 1.27), (1.27, 1.27), (0, -1.27), (-1.27, 1.27)], 0.254),
                     polyline([(-1.27, -1.27), (1.27, -1.27)], 0.254)] + led_gfx()[2:],
                    p1=("1", "A", "passive"), p2=("2", "K", "passive"), hide_names=False))
# LED with pin 1 = cathode (footprint LED0603-RD on this board)
syms.append(two_pin("LED_K1A2", "D", "LED", "", "", "LED, pin 1 = cathode, pin 2 = anode",
                    [polyline([(-1.27, -1.27), (1.27, -1.27), (0, 1.27), (-1.27, -1.27)], 0.254),
                     polyline([(-1.27, 1.27), (1.27, 1.27)], 0.254)] + led_gfx()[2:],
                    p1=("1", "K", "passive"), p2=("2", "A", "passive"), hide_names=False))
# Schottky, pin 1 = cathode (SMA footprints on this board)
syms.append(two_pin("D_Schottky_K1A2", "D", "D", "", "", "Schottky diode, pin 1 = cathode, pin 2 = anode",
                    [polyline([(-1.27, -1.27), (1.27, -1.27), (0, 1.27), (-1.27, -1.27)], 0.254),
                     polyline([(-1.27, 1.27), (1.27, 1.27)], 0.254),
                     polyline([(-1.27, 1.27), (-1.27, 1.905)], 0.254),
                     polyline([(1.27, 1.27), (1.27, 0.635)], 0.254)],
                    p1=("1", "K", "passive"), p2=("2", "A", "passive"), hide_names=False))

# ---- DRV8876 brushed-DC motor driver, HTSSOP-16 with thermal pad
syms.append(ic(
    "DRV8876PWPR", "U", "DRV8876PWPR",
    "MaslowMerged:HTSSOP-16_L5.0-W4.4-P0.65-LS6.4-BL-EP",
    "https://www.ti.com/lit/ds/symlink/drv8876.pdf",
    "H-bridge brushed DC motor driver, 4.5-37 V, integrated current sense (IPROPI)",
    left=[("1", "IN1", "input"), ("2", "IN2", "input"), ("3", "nSLEEP", "input"),
          ("4", "nFAULT", "open_collector"), ("5", "VREF", "input"), ("6", "IPROPI", "output"),
          ("7", "GND", "power_in"), ("8", "OUT1", "output")],
    right=[("16", "IMODE", "input"), ("15", "PGND", "power_in"), ("14", "CPL", "passive"),
           ("13", "CPH", "passive"), ("12", "VCP", "passive"), ("11", "VM", "power_in"),
           ("10", "OUT2", "output"), ("9", "PGND", "power_in")],
    bottom=[("17", "PAD", "passive")], half_width=11.43))

# ---- TCA9546A 4-channel I2C switch
syms.append(ic(
    "TCA9546A", "U", "TCA9546A",
    "MaslowMerged:SOP-16_L5.0-W4.4-P0.65-LS6.4-BL",
    "https://www.ti.com/lit/ds/symlink/tca9546a.pdf",
    "4-channel I2C bus switch with reset",
    left=[("1", "A0", "input"), ("2", "A1", "input"), ("3", "VCC", "power_in"),
          ("4", "SD0", "bidirectional"), ("5", "SC0", "bidirectional"),
          ("6", "SD1", "bidirectional"), ("7", "SC1", "bidirectional"), ("8", "GND", "power_in")],
    right=[("16", "nRESET", "input"), ("15", "SDA", "bidirectional"), ("14", "SCL", "bidirectional"),
           ("13", "A2", "input"), ("12", "SC3", "bidirectional"), ("11", "SD3", "bidirectional"),
           ("10", "SC2", "bidirectional"), ("9", "SD2", "bidirectional")], half_width=10.16))

# ---- ZDSD01GLGEAG SD NAND (SD interface in LGA-8)
syms.append(ic(
    "ZDSD01GLGEAG", "U", "ZDSD01GLGEAG",
    "MaslowMerged:LGA-8_L6.0-W8.0-P1.27-BL",
    "https://www.zettadevice.com/",
    "1 Gbit SD NAND flash, SD/SPI interface, LGA-8",
    left=[("1", "DAT1", "bidirectional"), ("2", "DAT3/nCS", "input"),
          ("3", "CLK", "input"), ("4", "VSS", "power_in")],
    right=[("8", "VDD", "power_in"), ("7", "DAT2", "bidirectional"),
           ("6", "DAT0/DO", "output"), ("5", "CMD/DI", "input")], half_width=10.16))

# ---- LM2596 fixed 3.3 V buck regulator, TO-263-5 (tab = pad 6)
syms.append(ic(
    "LM2596R-3.3", "U", "LM2596R-3.3",
    "MaslowMerged:TO-263-5_L10.2-W8.6-P1.70-LS14.4-TL",
    "https://www.ti.com/lit/ds/symlink/lm2596.pdf",
    "3 A step-down switching regulator, fixed 3.3 V output",
    left=[("1", "+VIN", "power_in"), ("5", "nON/OFF", "input"),
          ("3", "GND", "power_in"), ("6", "TAB", "passive")],
    right=[("2", "OUTPUT", "power_out"), ("4", "FEEDBACK", "input")], half_width=10.16))

# ---- Connectors
syms.append(ic(
    "XT60PB-M", "J", "XT60PB-M",
    "MaslowMerged:CONN-TH_XT60PB-M", "", "XT60 board-mount power inlet",
    left=[("1", "+", "passive"), ("2", "-", "passive")], right=[], half_width=3.81))
syms.append(ic(
    "B2B-PH-K-S", "J", "B2B-PH-K-S",
    "MaslowMerged:CONN-TH_B2B-PH-K-S", "", "JST PH 2.0 mm 2-pin through-hole header",
    left=[("1", "1", "passive"), ("2", "2", "passive")], right=[], half_width=3.81))
syms.append(ic(
    "B4B-PH-K-S", "J", "B4B-PH-K-S",
    "MaslowMerged:CONN-TH_B4B-PH-K-S", "", "JST PH 2.0 mm 4-pin through-hole header",
    left=[("1", "1", "passive"), ("2", "2", "passive"), ("3", "3", "passive"),
          ("4", "4", "passive")], right=[], half_width=3.81))

# ---- USB-C receptacle, 16 pin
syms.append(ic(
    "KH-TYPE-C-16P", "J", "KH-TYPE-C-16P",
    "MaslowMerged:USB-C-SMD_KH-TYPE-C-16P", "", "USB Type-C receptacle, 16 pin, USB 2.0",
    left=[("A1", "GND", "power_in"), ("A4", "VBUS", "power_in"), ("A5", "CC1", "bidirectional"),
          ("A6", "DP1", "bidirectional"), ("A7", "DN1", "bidirectional"),
          ("A8", "SBU1", "passive"), ("A9", "VBUS", "power_in"), ("A12", "GND", "power_in")],
    right=[("B1", "GND", "power_in"), ("B4", "VBUS", "power_in"), ("B5", "CC2", "bidirectional"),
           ("B6", "DP2", "bidirectional"), ("B7", "DN2", "bidirectional"),
           ("B8", "SBU2", "passive"), ("B9", "VBUS", "power_in"), ("B12", "GND", "power_in"),
           ("1", "SHELL", "passive"), ("2", "SHELL", "passive"), ("3", "SHELL", "passive"),
           ("4", "SHELL", "passive")], half_width=10.16))

# ---- 4-pin tactile switch (1-2 common, 3-4 common)
syms.append(symbol(
    "SW_Push_4P", "SW", "SW_Push_4P", "MaslowMerged:SW-SMD_4P-L6.2-W6.4-P4.00-LS7.2", "",
    "SPST momentary tactile switch, 4 terminals (1-2 and 3-4 internally common)",
    {"graphics": [polyline([(-2.54, 1.27), (-2.54, -1.27)], 0.254),
                  polyline([(2.54, 1.27), (2.54, -1.27)], 0.254),
                  polyline([(-2.54, 0), (-1.905, 0)], 0.254),
                  polyline([(1.905, 0), (2.54, 0)], 0.254),
                  circle(-1.524, 0, 0.381), circle(1.524, 0, 0.381),
                  polyline([(-1.27, 0.508), (1.27, 1.524)], 0.254),
                  polyline([(0, 1.27), (0, 2.54)], 0.254),
                  polyline([(-1.27, 2.54), (1.27, 2.54)], 0.254)],
     "pins": [pin("1", "1", "passive", -5.08, 1.27, 0, 2.54),
              pin("2", "2", "passive", -5.08, -1.27, 0, 2.54),
              pin("3", "3", "passive", 5.08, 1.27, 180, 2.54),
              pin("4", "4", "passive", 5.08, -1.27, 180, 2.54)]},
    ref_at=(-5.08, 4.318), val_at=(-5.08, -3.81)))

# ---- Power flag, used to tell ERC that a rail is driven
syms.append(symbol(
    "PWR_FLAG", "#FLG", "PWR_FLAG", "", "", "Marks a net as power-driven for ERC",
    {"graphics": [polyline([(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54),
                            (1.016, 1.905), (0, 1.27)], 0.254)],
     "pins": [pin("1", "pwr", "power_out", 0, 0, 90, 0)]},
    ref_at=(0, 3.556), val_at=(0, -0.762), hide_pin_names=True, hide_pin_numbers=True))

header = ('(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "maslow-merge")\n'
          '\t(generator_version "10.0")\n')
out = header + "\n".join(syms) + "\n)\n"
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJ
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, "MaslowMerged.kicad_sym")
open(dest, "w", encoding="utf-8").write(out)
print("wrote", dest, len(syms), "symbols")
